import io
import os
from tokenizers import Tokenizer
import random
import numpy as np
import json
import logging
import fileinput
from glob import glob

Logger = logging.getLogger("synthetic-datagen")
logging.basicConfig(level=logging.INFO)

# TODO: Data distribution visualization

DATA_RANDOM_SEED = int(os.environ.get("DATA_RANDOM_SEED", 42))
random.seed(DATA_RANDOM_SEED)
CORPUS_GLOB=f"{os.path.dirname(os.path.realpath(__file__))}/corpus/*.txt"

metadata_dict = {
    "name": "synthetic-data", 
    "version": "0.1.1", 
    "license": "MIT License\n\nCopyright (c) [year] [fullname]\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the \"Software\"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\ncopies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE.\n"
}

# Generate input and output lengths as 2 independant distributions
# Future item: Possible dependent distribution
def gen_io_lengths(num_samples :  int, input_distribution : str, output_distribution : str, other_args):
    Logger.debug(f"Data Random Seed : {DATA_RANDOM_SEED}")
    random_generator = np.random.default_rng(seed=DATA_RANDOM_SEED)

    # Types of distributions
    # Equal     - No change in lengths
    # Uniform   - Uniform distribution across the min_max intervals
    # Normal    - Standard normal distribution centered over the mean
    if input_distribution == "uniform":
        input = random_generator.uniform(low=other_args["input_min"], high=other_args["input_max"], size=num_samples)
    elif input_distribution == "normal":
        input = random_generator.normal(loc=other_args["input_mean"], scale=other_args["input_sd"], size=num_samples)
    elif input_distribution == "equal":
        # Using the library for consistency
        input = random_generator.normal(loc=other_args["input_len"], scale=0, size=num_samples)
    else:
        raise RuntimeError("Unknown distribution requested : " + str(input_distribution))

    if output_distribution == "uniform":
        output = random_generator.uniform(low=other_args["output_min"], high=other_args["output_max"], size=num_samples)
    elif output_distribution == "normal":
        output = random_generator.normal(loc=other_args["output_mean"], scale=other_args["output_sd"], size=num_samples)
    elif output_distribution == "equal":
        # Using the library for consistency
        output = random_generator.normal(loc=other_args["output_len"], scale=0, size=num_samples)
    else:
        raise RuntimeError("Unknown distribution requested : " + str(output_distribution))

    return input, output

def load_corpus():
    with fileinput.input(files=glob(CORPUS_GLOB), mode='r') as f:
        for line in f:
            yield line

def calculate_offsets(model, corpus):
    tokenizer = Tokenizer.from_pretrained(model)
    tokenized_corpus = tokenizer.encode(corpus)
    return tokenized_corpus.offsets


def make_one_sample(corpus, offsets, req_sample_size : int):
    start = random.randrange(len(offsets) - req_sample_size)
    end = start + req_sample_size # req_sample_size tokens from start
    start_idx = offsets[start][0]
    end_idx = offsets[end][0]
    tokens = corpus[start_idx:end_idx]
    return tokens

def make_dataset(args):

    model = args['model']
    num_samples = args['samples']

    dataset_info = {
        'model': model,
        'num_samples': num_samples,
        'input_distribution': args['input_distribution'],
        'output_distribution': args['output_distribution'],
    }

    input_lengths, output_lengths = gen_io_lengths(
        num_samples=num_samples, 
        input_distribution=dataset_info['input_distribution'],
        output_distribution=dataset_info['output_distribution'],
        other_args=args
        )

    # dtype conversion due to output type of random sampling
    input_lengths, output_lengths = input_lengths.astype(dtype=int).tolist(), output_lengths.astype(dtype=int).tolist()
    assert isinstance(input_lengths, list) # TODO
    assert isinstance(output_lengths, list) # TODO
    Logger.debug(f"Input and Output lengths : {list(zip(input_lengths, output_lengths))}")

    corpus = "".join(load_corpus())
    Logger.info(f"Loaded corpus")
    offsets = calculate_offsets(model, corpus)
    Logger.info(f"Found {len(offsets)} tokens in corpus")

    dict_items = []
    for si, (input_len, output_len) in enumerate(zip(input_lengths, output_lengths)):
        sample = make_one_sample(corpus, offsets, input_len)
        Logger.debug(f"Sample : {sample}")
        dict_items.append({
            "index": "custom-"+model+"-data-" + str(si),
            "question": sample,
            "tok_input_length": input_len,
            "tok_output_length": output_len,
            "system_prompt": "",
            "output_tokens" : output_len # to maintain consistency with existing sample dataset
        })

    return dict_items, dataset_info

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Create Synthetic Datasets for use with llm-load-test",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-m", "--model",
        help="Huggingface model name or path to model",
        required=True,
    )
    parser.add_argument("-o", "--dataset", metavar="FILE", required=True, type=argparse.FileType('w', encoding='UTF-8'))
    parser.add_argument("-c", "--samples", metavar="COUNT", type=int, default=100)

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input-equal", metavar="LEN", type=int, nargs=1)
    input_group.add_argument("--input-normal", metavar=("MEAN", "SD"), type=int, nargs=2)
    input_group.add_argument("--input-uniform", metavar=("MIN", "MAX"), type=int, nargs=2)

    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument("--output-equal", metavar="LEN", type=int, nargs=1)
    output_group.add_argument("--output-normal", metavar=("MEAN", "SD"), type=int, nargs=2)
    output_group.add_argument("--output-uniform", metavar=("MIN", "MAX"), type=int, nargs=2)

    args = parser.parse_args()

    arg_vars = vars(args)

    for i in ("input", "output"):
        if arg_vars.get(f"{i}_uniform") != None:
            params = ("min", "max")
            argv: list = arg_vars[f"{i}_uniform"]
            arg_vars[f"{i}_distribution"] = "uniform"
        elif arg_vars.get(f"{i}_normal") != None:
            params = ("mean", "sd")
            argv: list = arg_vars[f"{i}_normal"]
            arg_vars[f"{i}_distribution"] = "normal"
        elif arg_vars.get(f"{i}_equal") != None:
            params = ("len",)
            argv: list = arg_vars[f"{i}_equal"]
            arg_vars[f"{i}_distribution"] = "equal"
        else:
            raise RuntimeError(f"Unknown distribution requested for: {i}")
        arg_vars.update({f"{i}_{k}": v for k,v in zip(params, argv)})

    dataset, dataset_info = make_dataset(arg_vars)
    metadata_dict['dataset_info'] = dataset_info

    f: io.TextIOWrapper = args.dataset
    json.dump(metadata_dict, f)
    f.write("\n")
    for item in dataset:
        json.dump(item, f)
        f.write("\n")

    Logger.info(f"Dataset saved to : {f.name}")
