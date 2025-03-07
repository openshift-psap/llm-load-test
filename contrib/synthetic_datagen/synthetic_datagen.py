#!/usr/bin/env python

from abc import ABC
import os
from typing import IO, Any, Iterator, Optional
from tokenizers import Tokenizer
import random
import numpy as np
import json
import logging
from glob import glob
from copy import deepcopy

logger = logging.getLogger("synthetic-datagen")
logging.basicConfig(level=logging.INFO)

# TODO: Data distribution visualization

CORPUS_GLOB=f"{os.path.dirname(os.path.realpath(__file__))}/corpus/*.txt"

METADATA_DICT: dict[str, Any] = {
    "name": "synthetic-data", 
    "version": "0.1.1", 
    "license": "MIT License\n\nCopyright (c) [year] [fullname]\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the \"Software\"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\ncopies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE.\n"
}


class Distribution(ABC):
    _samples: list

    def __init__(self, samples: int, generator: np.random.Generator, *args) -> None:
        self.n = samples
        self.argv = args

    def __iter__(self) -> Iterator[int]:
        return iter(self._samples)

    def __getitem__(self, key) -> int:
        return self._samples[key]

    def __len__(self) -> int:
        return len(self._samples)

    @property
    def description(self) -> dict:
        return dict(
            distribution=type(self).__name__,
            args=self.argv,
            n=self.n,
        )


class NormalDist(Distribution):
    def __init__(
            self,
            samples: int,
            generator: np.random.Generator,
            mean: int,
            stdev: int,
            range_min: Optional[int] = None,
            range_max: Optional[int] = None
    ) -> None:
        self._samples = []

        if range_min is None:
            range_min = mean - 3*stdev
        range_min = max(1, range_min)

        if range_max is None:
            range_max = mean + 3*stdev

        if range_min > range_max:
            raise ValueError("Minimum value must be less than maximum value")

        discarded = 0
        while len(self._samples) < samples:
            sample = int(generator.normal(loc=mean, scale=stdev))
            if sample < range_min or sample > range_max:
                discarded += 1
            else:
                self._samples.append(sample)

        if discarded > 0:
            logger.warning(f"Replaced {discarded} of {samples} samples which were outside range [{range_min}, {range_max}]")

        super().__init__(samples, generator, mean, stdev)


class UniformDist(Distribution):
    def __init__(self, samples: int, generator: np.random.Generator, minimum: int, maximum: int) -> None:
        self._samples = generator.uniform(low=minimum, high=maximum, size=samples).astype(dtype=int).tolist()
        super().__init__(samples, generator, minimum, maximum)


class EqualDist(Distribution):
    def __init__(self, samples: int, generator: np.random.Generator, length: int) -> None:
        self._samples = generator.normal(loc=length, scale=0, size=samples).astype(dtype=int).tolist()
        super().__init__(samples, generator, length)


def read_files(files: list[IO[str]]):
    for f in files:
        for line in f:
            yield line


def write_dataset(dataset: list[dict], f: IO[str]):
    dataset_str = "\n".join(map(json.dumps, dataset))
    f.write(dataset_str)
    f.write("\n")

    logger.info(f"Dataset saved to : {f.name}")


def calculate_offsets(model, corpus):
    if os.path.isfile(f"{model}/tokenizer.json"):
        tokenizer = Tokenizer.from_file(f"{model}/tokenizer.json")
    else:
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


def make_dataset(model: str, samples: int, input_dist: Distribution, output_dist: Distribution, corpus: str):
    dataset_info = {
        'tokenizer': model,
        'n': samples,
        'input': input_dist.description,
        'output': output_dist.description,
    }

    # Make the metadata header
    metadata = deepcopy(METADATA_DICT)
    metadata['dataset_info'] = dataset_info

    offsets = calculate_offsets(model, corpus)
    logger.info(f"Found {len(offsets)} tokens in corpus")

    dict_items = [ metadata ]
    for si, (input_len, output_len) in enumerate(zip(input_dist, output_dist)):
        sample = make_one_sample(corpus, offsets, input_len)
        logger.debug(f"Sample : {sample}")
        dict_items.append({
            "index": si,
            "question": sample,
            "tok_input_length": input_len,
            "tok_output_length": output_len,
            "system_prompt": "",
            "output_tokens" : output_len # to maintain consistency with existing sample dataset
        })

    return dict_items


if __name__ == "__main__":
    import argparse
    def positive_int(value):
        ivalue = int(value)
        if ivalue <= 0:
            raise ValueError(f"{value} must be positive")
        return ivalue

    parser = argparse.ArgumentParser(
        description="Create Synthetic Datasets for use with llm-load-test",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=80)
    )
    parser.add_argument(
        "-m", "--model",
        help="HuggingFace model name or path to model",
        required=True,
    )
    parser.add_argument(
        "-o", "--dataset",
        metavar="FILE",
        required=True,
        type=argparse.FileType('w', encoding='UTF-8'),
        help="path to output file",
    )
    parser.add_argument(
        "-i", "--corpus",
        metavar="FILE",
        nargs="+",
        default=[argparse.FileType('r')(f) for f in glob(CORPUS_GLOB)],
        type=argparse.FileType('r'),
        help="path to corpus file(s)",
    )
    parser.add_argument(
        "-c", "--samples",
        metavar="COUNT",
        type=positive_int,
        required=True,
        help="number of samples to generate",
    )
    parser.add_argument(
        "-s", "--seed",
        metavar="INT",
        type=int,
        default=42,
        help="random sample seed",
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input-equal",
        metavar="LEN",
        type=positive_int,
        nargs=1,
        help="equal distribution for input tokens",
    )
    input_group.add_argument(
        "--input-normal",
        metavar=("MEAN", "SD"),
        type=positive_int,
        nargs=2,
        help="normal distribution for input tokens",
    )
    input_group.add_argument(
        "--input-uniform",
        metavar=("MIN", "MAX"),
        type=positive_int,
        nargs=2,
        help="uniform distribution for input tokens",
    )

    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument(
        "--output-equal",
        metavar="LEN",
        type=positive_int,
        nargs=1,
        help="equal distribution for output tokens",
    )
    output_group.add_argument(
        "--output-normal",
        metavar=("MEAN", "SD"),
        type=positive_int,
        nargs=2,
        help="normal distribution for output tokens",
    )
    output_group.add_argument(
        "--output-uniform",
        metavar=("MIN", "MAX"),
        type=positive_int,
        nargs=2,
        help="uniform distribution for output tokens",
    )

    args = parser.parse_args()

    # Init random number generators
    random.seed(args.seed) # We use python random for sampling corpus
    rand = np.random.default_rng(seed=args.seed)

    # Set the correct arguments based on specified distribution
    if args.input_uniform != None:
        input_dist = UniformDist(args.samples, rand, *args.input_uniform)
    elif args.input_normal != None:
        input_dist = NormalDist(args.samples, rand, *args.input_normal)
    elif args.input_equal != None:
        input_dist = EqualDist(args.samples, rand, *args.input_equal)
    else:
        raise RuntimeError(f"Unknown distribution requested for input")

    if args.output_uniform != None:
        output_dist = UniformDist(args.samples, rand, *args.output_uniform)
    elif args.output_normal != None:
        output_dist = NormalDist(args.samples, rand, *args.output_normal)
    elif args.output_equal != None:
        output_dist = EqualDist(args.samples, rand, *args.output_equal)
    else:
        raise RuntimeError(f"Unknown distribution requested for output")

    # Load corpus
    corpus = "".join(read_files(args.corpus))
    logger.info(f"Loaded corpus")

    dataset = make_dataset(args.model, args.samples, input_dist, output_dist, corpus)

    write_dataset(dataset, args.dataset)
