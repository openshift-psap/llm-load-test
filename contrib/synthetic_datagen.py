import os
import pickle
import transformers
import random
import json

SYS_PROMPT = "You are an AI assistant that helps people find information. User will you give you a question. Your task is to answer as faithfully as you can. While answering think step-bystep and justify your answer."

metadata_dict = {
    "name": "openorca-subset", 
    "version": "0.1.1", 
    "license": "MIT License\n\nCopyright (c) [year] [fullname]\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the \"Software\"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\ncopies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE.\n"
}

def make_one_sample(vocab, tokenizer, sys_prompt_length, req_sample_size, max_dev = 0):
    tokens = random.sample(vocab, req_sample_size - sys_prompt_length)
    return tokenizer.decode(tokens).replace("<|begin_of_text|>", ""), len(tokens)

def make_dataset(model, num_samples, input_min, input_max, output_min, output_max):

    tokenizer = transformers.AutoTokenizer.from_pretrained(model)
    vocab = list(range(0, tokenizer.vocab_size))

    sys_prompt_length = len(tokenizer(SYS_PROMPT)["input_ids"])
    dict_items = []
    for si in range(num_samples):
        input_len = random.randint(input_min, input_max)
        output_len = random.randint(output_min, output_max)
        sample = make_one_sample(vocab, tokenizer, sys_prompt_length, input_len)
        dict_items.append({
            "index": "custom-"+model+"-data-" + str(si),
            "question": sample,
            "tok_input_length": input_len,
            "tok_output_length": output_len,
            "output_tokens" : output_len,
            "system_prompt": SYS_PROMPT
        })

    return dict_items

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser("Create Synthetic Datasets for use with llm-load-test")
    parser.add_argument("--model")
    parser.add_argument("--dataset_name")
    parser.add_argument("--num_samples", type = int)
    parser.add_argument("--input_min", type = int)
    parser.add_argument("--input_max", type = int, default=None)
    parser.add_argument("--output_min", type = int)
    parser.add_argument("--output_max", type = int, default=None)

    args = parser.parse_args()

    # No variance allowed if max is not specified. Min will be treated as the target length
    if not args.input_max:
        args.input_max = args.input_min
    
    if not args.output_max:
        args.output_max = args.output_min

    dataset = make_dataset(args.model, args.num_samples, args.input_min, args.input_max, args.output_min, args.output_max)

    with open(args.dataset_name + "_synthetic.jsonl", "w") as f:
        json.dump(metadata_dict, f)
        f.write("\n")
        for item in dataset:
            json.dump(item, f)
            f.write("\n")

