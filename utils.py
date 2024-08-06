"""Utils functions for various tasks."""

import argparse
import json
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

from plugins import (
    caikit_client_plugin,
    caikit_embedding_plugin,
    dummy_plugin,
    hf_tgi_plugin,
    openai_plugin,
    tgis_grpc_plugin,
)

import yaml

os.environ["OPENBLAS_NUM_THREADS"] = "1"


class customEncoder(json.JSONEncoder):
    """Return an encoder."""

    def default(self, obj):
        """Get default object."""
        if isinstance(obj, np.int64):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(customEncoder, self).default(obj)


def parse_args(args):
    """Parse the CLI parameters."""
    log_levels = {
        "warn": logging.WARNING,
        "warning": logging.WARNING,
        "info": logging.INFO,
        "debug": logging.DEBUG,
    }

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        action="store",
        default="config.yaml",
        help="config YAML file name",
    )
    parser.add_argument(
        "-log",
        "--log_level",
        default="info",
        choices=log_levels.keys(),
        help="Provide logging level. Example --log_level debug, default=warning",
    )
    args = parser.parse_args(args)

    args.log_level = log_levels[args.log_level]
    return args


def parse_config(config):
    """Parse the config file."""
    logging.info("dataset config: %s", config["dataset"])
    logging.info("load_options config: %s", config["load_options"])

    load_options = config.get("load_options")
    concurrency = load_options.get("concurrency")
    duration = load_options.get("duration")

    plugin_type = config.get("plugin")
    if plugin_type == "openai_plugin":
        plugin = openai_plugin.OpenAIPlugin(
            config.get("plugin_options")
        )
    elif plugin_type == "caikit_client_plugin":
        plugin = caikit_client_plugin.CaikitClientPlugin(config.get("plugin_options"))
    elif plugin_type == "caikit_embedding_plugin":
        plugin = caikit_embedding_plugin.CaikitEmbeddingPlugin(config.get("plugin_options"))
    elif plugin_type == "tgis_grpc_plugin":
        plugin = tgis_grpc_plugin.TGISGRPCPlugin(config.get("plugin_options"))
    elif plugin_type == "hf_tgi_plugin":
        plugin = hf_tgi_plugin.HFTGIPlugin(config.get("plugin_options"))
    elif plugin_type == "dummy_plugin":
        plugin = dummy_plugin.DummyPlugin(config.get("plugin_options"))
    else:
        logging.error("Unknown plugin type %s", plugin_type)
        raise ValueError(f"Unknown plugin type {plugin_type}")

    return concurrency, duration, plugin


def yaml_load(file):
    """Load a yaml file."""
    if not Path(file).is_file():
        raise FileNotFoundError(file)
    with open(file, "r", encoding="utf-8") as stream:
        try:
            return yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise RuntimeError(f"Could not parse {file}") from exc

def get_summary(df: pd.DataFrame, output_obj: dict, summary_key: str):
    """Get the summary."""
    output_obj["summary"][summary_key] = {}
    output_obj["summary"][summary_key]["min"] = df[summary_key].min()
    output_obj["summary"][summary_key]["max"] = df[summary_key].max()
    output_obj["summary"][summary_key]["median"] = df[summary_key].median()
    output_obj["summary"][summary_key]["mean"] = df[summary_key].mean()
    output_obj["summary"][summary_key]["percentile_80"] = df[summary_key].quantile(0.80)
    output_obj["summary"][summary_key]["percentile_90"] = df[summary_key].quantile(0.90)
    output_obj["summary"][summary_key]["percentile_95"] = df[summary_key].quantile(0.95)
    output_obj["summary"][summary_key]["percentile_99"] = df[summary_key].quantile(0.99)
    return output_obj
