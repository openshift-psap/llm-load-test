import os
import pickle
import transformers
import random
import numpy as np
import json
import sys

sys.path.append(os.getcwd())

import logging
import logging.handlers

import logging_utils

metadata_dict = {
    "name": "synthetic-data", 
    "version": "0.1.1", 
    "license": "MIT License\n\nCopyright (c) [year] [fullname]\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the \"Software\"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\ncopies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE.\n"
}

# Types of distributions we want
# Equal     - No change in lengths
# Uniform   - Uniform distribution across the min_max intervals
# Normal    - Standard normal distribution centered over the mean

def gen_io_lengths(num_samples :  int, distribution : str, other_args):

    seed = 42
    if "DATA_RANDOM_SEED" in os.environ:
        seed = int(os.environ["DATA_RANDOM_SEED"])
    
    random_generator = np.random.default_rng(seed=seed)

    if distribution == "uniform":
        return (
            random_generator.uniform(low=other_args["input_min"], high=other_args["input_max"], size=num_samples),
            random_generator.uniform(low=other_args["output_min"], high=other_args["output_max"], size=num_samples),
        )
    elif distribution == "normal":
        return (
            random_generator.normal(loc=other_args["input_mean"], scale=other_args["input_sd"], size=num_samples),
            random_generator.normal(loc=other_args["output_mean"], scale=other_args["output_sd"], size=num_samples),
        )
    elif distribution == "equal":
        return (
            random_generator.normal(loc=other_args["input_len"], scale=0, size=num_samples),
            random_generator.normal(loc=other_args["output_len"], scale=0, size=num_samples),
        )
    else:
        raise RuntimeError("Unknown distribution requested : " + str(args.distribution))

def make_one_sample(vocab, tokenizer, req_sample_size, max_dev=0):
    tokens = random.sample(vocab, req_sample_size)
    return tokenizer.decode(tokens).replace("<|begin_of_text|>", ""), len(tokens)

def make_dataset(args):

    print(args)

    # model, num_samples, input_min, input_max, output_min, output_max, distribution="normal"
    model = args['model']
    num_samples = args['num_samples']

    tokenizer = transformers.AutoTokenizer.from_pretrained(model)
    vocab = list(range(0, tokenizer.vocab_size))

    input_lengths, output_lengths = gen_io_lengths(
        num_samples=num_samples, 
        distribution=args['distribution'],
        other_args=args
        )

    input_lengths, output_lengths = input_lengths.astype(dtype=int).tolist(), output_lengths.astype(dtype=int).tolist()
    
    print(input_lengths, output_lengths)

    dict_items = []
    for si, (input_len, output_len) in enumerate(zip(input_lengths, output_lengths)):
        sample, _ = make_one_sample(vocab, tokenizer, int(input_len))
        dict_items.append({
            "index": "custom-"+model+"-data-" + str(si),
            "question": sample,
            "tok_input_length": input_len,
            "tok_output_length": output_len,
            "output_tokens" : output_len
        })

    return dict_items

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser("Create Synthetic Datasets for use with llm-load-test")
    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset_name", required=True)
    parser.add_argument("--num_samples", type = int, default=100)
    parser.add_argument("--distribution", choices=["normal", "uniform", "equal"], required=True)

    # Equal length Params
    parser.add_argument("--input_len", type=int)
    parser.add_argument("--output_len", type=int)

    # Normal Distribution Params
    parser.add_argument("--input_mean", type=int)
    parser.add_argument("--input_sd", type=int)
    parser.add_argument("--output_mean", type=int)
    parser.add_argument("--output_sd", type=int)

    # Uniform Distribution Params
    parser.add_argument("--input_min", type = int)
    parser.add_argument("--input_max", type = int, default=None)
    parser.add_argument("--output_min", type = int)
    parser.add_argument("--output_max", type = int, default=None)

    args = parser.parse_args()

    arg_vars = vars(args)

    if args.distribution == "uniform":
        uniform_params = ("input_min", "input_max", "output_min", "output_max")
        if not all(arg_vars[k] != None for k in uniform_params):
            parser.error("Missing fields : " + str([k for k in uniform_params if arg_vars[k] is None]))
    elif args.distribution == "normal":
        normal_params = ("input_mean", "input_sd", "output_mean", "output_sd")
        if not all(arg_vars[k] != None for k in normal_params):
            parser.error("Missing fields : " + str([k for k in normal_params if arg_vars[k] is None]))
    elif args.distribution == "equal":
        equal_params = ("input_len", "output_len")
        if not all(arg_vars[k] != None for k in equal_params):
            parser.error("Missing fields : " + str([k for k in equal_params if arg_vars[k] is None]))
    else:
        raise RuntimeError("Unknown distribution requested : " + str(args.distribution))

    print(args)

    # No variance allowed if max is not specified. Min will be treated as the target length
    if not args.input_max:
        args.input_max = args.input_min
    
    if not args.output_max:
        args.output_max = args.output_min

    dataset = make_dataset(arg_vars)

    with open(args.dataset_name + "_synthetic.jsonl", "w") as f:
        metadata_dict["tokenizer"] = args.model
        json.dump(metadata_dict, f)
        f.write("\n")
        for item in dataset:
            json.dump(item, f)
            f.write("\n")

    