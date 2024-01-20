import argparse
import json
import logging
from pathlib import Path
import sys
import pandas as pd
import yaml

from plugins import caikit_client_plugin, text_generation_webui_plugin


def parse_args(args):
    log_levels = {
        'warn': logging.WARNING,
        'warning': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG
    }

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="increase output verbosity")
    parser.add_argument("-c", "--config", action="store", default="config.yaml",
                        help="config YAML file name")
    parser.add_argument( '-log', '--log_level',
                     default='info',
                     choices=log_levels.keys(),
                     help='Provide logging level. Example --loglevel debug, default=warning' )
    args = parser.parse_args(args)

    args.log_level = log_levels[args.log_level]
    return args

def parse_config(config):
    logger = logging.getLogger()
    logger.info("dataset config: %s", config['dataset'])
    logger.info("load_options config: %s", config['load_options'])

    load_options = config.get("load_options")
    concurrency = load_options.get("concurrency")
    duration = load_options.get("duration")

    plugin_type = config.get("plugin")
    if plugin_type == "text_generation_webui_plugin":
        plugin = text_generation_webui_plugin.TextGenerationWebUIPlugin(config.get("plugin_options"))
    elif plugin_type == "caikit_client_plugin":
        plugin = caikit_client_plugin.CaikitClientPlugin(config.get("plugin_options"))
    else:
        logging.error("Unknown plugin type %s", plugin_type)
        raise ValueError(f"Unknown plugin type {plugin_type}")

    return concurrency, duration, plugin

def yaml_load(file):
    if not Path(file).is_file():
        raise FileNotFoundError(file)
    with open(file, 'r', encoding="utf-8") as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise RuntimeError(f"Could not parse {file}") from exc
        
def write_output(config, results_list):
    output_options = config.get("output")
    output_path = output_options.get("dir")

    logging.info("Writing output to %s", output_path)
    path = Path(output_path)
    if not (path.exists() and path.is_dir()):
        logging.warning("Output path %s does not exist, creating it!", path)
        path.mkdir(parents=True, exist_ok=True)
    
    outfile = path / Path(output_options.get("file"))
    output_obj = {"results": results_list, "config": config}
    with outfile.open('w') as f:
        json.dump(output_obj, f)

    logging.info("Length of results: %d", len(results_list))

    #TODO, should this be output using logging?
    df = pd.DataFrame(results_list)    
    df.head()
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(df)
    print(f"\n---\nFull results in {outfile}. Results summary:")
    if "ttft" in df:
        print(df[["tt_ack", "ttft", "tpot", "response_time", "output_tokens", "input_tokens"]].mean(numeric_only=True))
    else:
        print(df[["tpot", "response_time", "output_tokens", "input_tokens"]].mean(numeric_only=True))

    load_options = config.get("load_options")
    duration = load_options.get("duration")
    throughput = df["output_tokens"].sum() / duration
    print(f"Total throughput across all users: {throughput} tokens / sec")
