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
    # Profile: (mean, stdev, min, max)
    Profiles.SMALL: dict(mean=128, stdev=32, range_min=0, range_max=256),
    Profiles.MEDIUM: dict(mean=512, stdev=128, range_min=256, range_max=1024),
    Profiles.LARGE: dict(mean=2048, stdev=512, range_min=1024, range_max=3072),
    Profiles.XLARGE: dict(mean=10240, stdev=2048, range_min=4096, range_max=16384),
}
SEED = 42
SAMPLES = 4000


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate llm-load-test profile based datasets",
        epilog=f"Profiles are one of {', '.join(p.value for p in Profiles)}.",
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
    input_dist = synthetic_datagen.NormalDist(SAMPLES, rand, **PROFILES[args.input])
    output_dist = synthetic_datagen.NormalDist(SAMPLES, rand, **PROFILES[args.output])

    # Load corpus
    in_files = [argparse.FileType('r')(f) for f in glob(synthetic_datagen.CORPUS_GLOB)]
    corpus = "".join(synthetic_datagen.read_files(in_files))

    dataset = synthetic_datagen.make_dataset(args.model, SAMPLES, input_dist, output_dist, corpus)

    model_name = Path(args.model).name
    dataset_dest = f"{args.input.value}I{args.output.value}O_normal_{model_name}.jsonl"
    with open(dataset_dest, 'w') as f:
        synthetic_datagen.write_dataset(dataset, f)
