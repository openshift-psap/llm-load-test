#!/usr/bin/env python3

from glob import glob
import logging
import random
from enum import Enum
from pathlib import Path
import numpy as np

import synthetic_datagen

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class Profiles(Enum):
    SMALL = "S"
    MEDIUM = "M"
    LARGE = "L"
    XLARGE = "XL"

PROFILES = {
    # Profile: (mean, stdev)
    Profiles.SMALL: (128, 32),
    Profiles.MEDIUM: (512, 128),
    Profiles.LARGE: (2048, 512),
    Profiles.XLARGE: (10240, 2048),
}
SEED = 42
SAMPLES = 4000


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate llm-load-test profile based datasets",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=80)
    )
    parser.add_argument(
        "model",
        help="HuggingFace model name or path to model",
    )
    parser.add_argument(
        "input",
        type=Profiles,
        help="input profile",
    )
    parser.add_argument(
        "output",
        type=Profiles,
        help="output profile",
    )

    args = parser.parse_args()

    # Init random number generators
    random.seed(SEED) # We use python random for sampling corpus
    rand = np.random.default_rng(seed=SEED)
    input_dist = synthetic_datagen.NormalDist(SAMPLES, rand, *PROFILES[args.input])
    output_dist = synthetic_datagen.NormalDist(SAMPLES, rand, *PROFILES[args.output])

    # Load corpus
    in_files = [argparse.FileType('r')(f) for f in glob(synthetic_datagen.CORPUS_GLOB)]
    corpus = "".join(synthetic_datagen.read_files(in_files))

    dataset = synthetic_datagen.make_dataset(args.model, SAMPLES, input_dist, output_dist, corpus)

    model_name = Path(args.model).name
    dataset_dest = f"{args.input.value}I{args.output.value}O_normal_{model_name}.jsonl"
    with open(dataset_dest, 'w') as f:
        synthetic_datagen.write_dataset(dataset, f)
