import argparse
import json
import os
from pathlib import Path
import yaml
import pandas as pd


def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="increase output verbosity")
    parser.add_argument("-c", "--config", action="store", default="config.yaml",
                        help="config YAML file name")
    return parser.parse_args(args)


def yaml_load(file):
    if not os.path.isfile(file):
        raise FileNotFoundError(file)
    with open(file, 'r', encoding="utf-8") as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError:
            raise RuntimeError(f"Could not parse {file}")
        
def write_output(config, results_list):
    output_options = config.get("output")
    output_path = output_options.get("dir")
    path = Path(output_path)
    if not (path.exists() and path.is_dir()):
        print(f"Output path {path} does not exist, creating it!")
        path.mkdir(parents=True, exist_ok=True)
    
    outfile = path / Path(output_options.get("file"))
    output_obj = {"results": results_list, "config": config}
    with outfile.open('w') as f:
        json.dump(output_obj, f)

    print(f"Length of results: {len(results_list)}")
    df = pd.DataFrame(results_list)    
    df.head()
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df)
    print(df[["TT_ack", "TTFT", "TPOT", "response_time", "output_tokens", "input_tokens"]].mean(numeric_only=True))