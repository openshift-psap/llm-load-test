# SPDX-FileCopyrightText: Copyright (c) 2022-2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-FileCopyrightText: Copyright (c) 2024 Red Hat Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import time
import argparse
import pandas as pd
import pickle
import json
from tqdm import tqdm
tqdm.pandas()
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from transformers import LlamaTokenizerFast
from typing import Dict


def is_english(s):
    for c in s:
        allowed = c.isascii()
        allowed = allowed or (c in ['’', '–', '“', '”', '—'])  # Taken from Habana: Unicode quotes and hyphens
        if not allowed:
            return False
    return True


def _tokenize_helper(x, llama_tokenizer=None, append_response_init_token=False):
    if not isinstance(x, str):
        return []

    tokens = llama_tokenizer(x)["input_ids"]

    if append_response_init_token:
        # Workaround to enable cheat checking for first token: Llama always outputs token 29871 first
        # It is possible for submitters to just immediately output this token to achieve a very fast TTFT.
        tokens.append(29871)
    return tokens


@dataclass
class Keyphrase:
    col: str
    phrase: str
    startswith: bool = False
    case: bool = False


class OpenOrcaDatasetGenerator:
    def __init__(self,
                 pq_path: os.PathLike,
                 model_dir: os.PathLike,
                 io_token_limit: int,
                 output_json_file: str,
                 calibration_subset_size: int = 1000
                 ):
        self.pq_path = Path(pq_path)
        self.model_dir = Path(model_dir)
        self.io_token_limit = io_token_limit
        self.keyphrases = []
        self.calibration_subset_size = calibration_subset_size

    def load_parquet(self, parquet_elements=None) -> pd.DataFrame:
        df = pd.read_parquet(self.pq_path)
        df.rename(columns={'response': 'output'}, inplace=True)
        if parquet_elements is not None:
            return df[:parquet_elements]
        return df

    def get_token_lengths(self, df) -> pd.DataFrame:
        print(f"Tokenizing input")

        llama_tokenizer = LlamaTokenizerFast.from_pretrained(self.model_dir)

        tik = time.time()

        input_tokenizer = partial(_tokenize_helper, llama_tokenizer=llama_tokenizer)
        output_tokenizer = partial(_tokenize_helper, llama_tokenizer=llama_tokenizer, append_response_init_token=False)
        df['tok_input'] = df['question'].progress_apply(input_tokenizer)
        df['tok_output'] = df['output'].progress_apply(output_tokenizer)
        tok = time.time()
        print(f"Tokenized in {tok-tik} sec.")
        return df

    def filter_english(self, df: pd.DataFrame) -> pd.DataFrame:
        df['input_english'] = df['question'].apply(is_english)
        df['output_english'] = df['output'].apply(is_english)
        df['all_english'] = df['input_english'] & df['output_english']

        # Filter based on english tokens
        df = df[df['all_english']].drop(["input_english", "output_english", "all_english"], axis=1)
        return df.reset_index(drop=True)

    def filter_seqlen_oob(self, df: pd.DataFrame) -> pd.DataFrame:
        df['tok_input_length'] = df['tok_input'].apply(lambda x: len(x))
        df['tok_output_length'] = df['tok_output'].apply(lambda x: len(x))

        # Filter based on sequence length (2048, 2048)
        df = df[df["tok_input_length"] < self.io_token_limit]
        df = df[df["tok_output_length"] < self.io_token_limit]
        return df.reset_index(drop=True)
    
    def filter_output_oob(self, df: pd.DataFrame, output_limit: int=4096) -> pd.DataFrame:
        df = df[df["tok_output_length"] < output_limit]

        return df.reset_index(drop=True)

    def filter_short_expected_response(self, df: pd.DataFrame) -> pd.DataFrame:
        # We have found that short expected responses (such as for yes/no and true/false questions, or multiple choice
        # questions where the expected response is just the choice, i.e. (B)), disproportionately have lower Rouge1
        # scores (< 0.02).

        # Filter out 1 and 2 word expected responses. We've seen best results when this is filtered to >= 6, but it is
        # hard to justify removing that many samples.
        df = df[df["tok_output_length"] >= 3]
        return df.reset_index(drop=True)

    def filter_bad_prompts(self, df: pd.DataFrame, only_niv_t0: bool = True) -> pd.DataFrame:
        # Some prompts underperform and cause very bad Rouge scores for a significant percentage of samples with these
        # prompts. See Jupyter notebook for analysis.
        # These generally only affect NIV and t0 and do not exist in flan or cot.
        # Set 'only_niv_t0' to True to explicitly only remove these prompts from niv and t0 samples.
        bad_prompts = ['',
                       'You are an AI assistant that follows instruction extremely well. Help as much as you can.',
                       'You are an AI assistant. Provide a detailed answer so user don’t need to search outside to understand the answer.',
                       "You are an AI assistant. Provide a detailed answer so user don't need to search outside to understand the answer.",
                       'User will you give you a task with some instruction. Your job is follow the instructions as faithfully as you can. While answering think step-by-step and justify your answer.',
                       'Explain how you used the definition to come up with the answer.',
                       ]
        for prompt in bad_prompts:
            criteria = (df.system_prompt == prompt)
            if only_niv_t0:
                criteria = criteria & ((df.origin == "niv") | (df.origin == "t0"))
            df = df[~criteria]

        return df.reset_index(drop=True)

    def set_origins(self, df: pd.DataFrame) -> pd.DataFrame:
        get_sample_origin = lambda x: x.split(".")[0]
        df['origin'] = df['id'].apply(get_sample_origin)
        return df

    def _get_sampling(self, df, N, rng_seed: int = 1337):
        _N = min(df.shape[0], N)
        if _N < N:
            raise RuntimeError(f"Not enough samples. Requires {N - _N} more.")
        return df.sample(n=_N, random_state=rng_seed)


    def _get_distributed_subset(self, df, step_size: int = 64, rng_seed: int = 1337):
        outputs=[]
        for input_lower in range(0, 12288, step_size):
            input_upper = input_lower + step_size
            for output_lower in range(0, 12288, step_size):
                output_upper = output_lower + step_size
                
                data_subset = df[(df['tok_input_length'] > input_lower) & (df['tok_input_length'] < input_upper) & (df['tok_output_length'] > output_lower) & (df['tok_output_length'] < output_upper)]
                elements_in_region = len(data_subset)
                if elements_in_region > 0:
                    # If there are 4 or fewer elements in the region, just take all of them
                    # otherwise take fourth root+3 of the elements in the region
                    if elements_in_region < 5:
                        subset_sample_size = elements_in_region
                    else:
                        subset_sample_size = 3 + ((elements_in_region - 3))**(1/4)
                    print(f"In tile: {input_lower}:{input_upper}, {output_lower}:{output_upper}, subset_sample_size: {subset_sample_size}")
                    #subset_sample=max(1, (len(data_subset))**(1./3.))
                    # sample from the subset
                    sample = data_subset.sample(n=int(subset_sample_size), random_state=rng_seed)
                    outputs.append(sample)

        return pd.concat(outputs, ignore_index=True).reset_index(drop=True)

    def _write_to_json_and_jsonl(self, df, output_name):
            df = df.drop('tok_input', axis=1)
            df = df.drop('tok_output', axis=1)
            df = df.rename(columns={"output": "expected_output"})
            df = df.sort_values(by=['tok_input_length', 'tok_output_length'])
            df = df.reset_index(drop=True).reset_index()
            print(df.head())

            metadata = {"name": "openorca-subset", 
                        "version": "0.1.1", 
                        "license": "MIT License\n\nCopyright (c) [year] [fullname]\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the \"Software\"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\ncopies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE.\n"}
            ### .json file
            json_obj = {"dataset": df.to_dict(), "metadata": metadata}
                        
            with open(f"{output_name}.json", 'w') as f:
                json.dump(json_obj, f, indent=4)
            

            ### jsonl file
            list_of_dicts = df.to_dict('records')
            list_of_dicts.insert(0, metadata)
            with open(f"{output_name}.jsonl", 'w') as f:
                for d in list_of_dicts:
                    json.dump(d, f)
                    f.write('\n')
            #df.to_json("openorca_large_subset_011.jsonl", orient='records', lines=True)
            #df.to_json("openorca_large_subset_011.json", orient='records', lines=False)

    def generate(self,
                 export_dir: os.PathLike,
                 n_samples: int = 24576,
                 use_cached: bool = True,
                 calib_rng_seed: int = 12345,
                 output_json_file: str = "openorca_large_subset_011"
    ):
        export_dir = Path(export_dir)
        if not export_dir.exists():
            print(f"Creating {export_dir}")
            export_dir.mkdir(parents=True)
        if export_dir.is_file():
            raise ValueError(f"Cannot export to file {export_dir}. Must be a directory.")

        full_fpath = export_dir / f"open_orca_gpt4_tokenized_llama.full.pkl"
        if full_fpath.exists() and use_cached:
            print(f"{full_fpath} exists, reading from pickle file")
            df = pd.read_pickle(full_fpath)
        else:
            df = self.load_parquet()
            df = self.set_origins(df)

            # Apply filters
            df = self.filter_english(df)
            df = self.filter_bad_prompts(df)

            print("df length: {}".format(len(df)))
            df = self.get_token_lengths(df)
            df = self.filter_seqlen_oob(df)
            df = self.filter_output_oob(df)
            df = self.filter_short_expected_response(df)
            #df = self._get_sampling(df, n_samples)
            #df = self.filter_keyphrases(df)
            df.to_pickle(full_fpath)
            print(df.head())
        
        df = self._get_distributed_subset(df)

        print(len(df))
        df.to_pickle(export_dir / f"open_orca_gpt4_tokenized_llama.sampled.pkl")

        self._write_to_json_and_jsonl(df, output_json_file)
 

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset_pq_path', type=str,
                        default='/raid/data/mlperf-llm/OpenOrca/1M-GPT4-Augmented.parquet',
                        help="the path to the open_orca GPT4 parquet.")
    parser.add_argument('--model_dir', type=str, default='/raid/data/mlperf-llm/Llama-2-70b-chat-hf')
    parser.add_argument('--seqlen_limit', type=int, default=1024, help="Upper limit of the input/output sequence lengths")
    parser.add_argument('--export_dir', type=str,
                        default="/raid/data/mlperf-llm/OpenOrca/llama/filtered",
                        help="Path to the output pkl file.")
    parser.add_argument('--num_total_samples', type=int, default=24576, help="Number of samples to generate")
    parser.add_argument('--output_json_file', type=str, default="openorca_large_subset_011", help="Number of samples to generate")
    parser.add_argument('--calibration_subset_size', type=int, default=1000, help="Number of samples for calibration subset")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    ds_gen = OpenOrcaDatasetGenerator(
        pq_path=args.dataset_pq_path,
        model_dir=args.model_dir,
        io_token_limit=args.seqlen_limit,
        calibration_subset_size=args.calibration_subset_size,
        output_json_file=args.output_json_file
    )
    ds_gen.generate(
        export_dir=args.export_dir,
        n_samples=args.num_total_samples,
    )
    

    # Sample command to run:
    # python3 processorca.py --dataset_pq_path=/raid/data/mlperf-llm/OpenOrca/1M-GPT4-Augmented.parquet --model_dir=/raid/data/mlperf-llm/Llama-2-70b-chat-hf --seqlen_limit=1024 --export_dir=/raid/data/mlperf-llm/OpenOrca/llama/filtered --num_total_samples=24576]