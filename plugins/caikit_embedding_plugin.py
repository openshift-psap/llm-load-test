import json
import logging
import time

import urllib3
from caikit_nlp_client import GrpcClient, HttpClient
from pathlib import Path

import pandas as pd

import utils

from plugins import plugin
from result import EmbeddingRequestResult

urllib3.disable_warnings()


"""
Example plugin config.yaml:

plugin: "caikit_embedding_plugin"
plugin_options:
  interface: "http" # Some plugins like caikit-nlp-client should support grpc/http
  streaming: True
  model_name: "Llama-2-7b-hf"
  host: "https://llama-2-7b-hf-isvc-predictor-dagray-test.apps.modelserving.nvidia.eng.rdu2.redhat.com"
  port: 443
"""

logger = logging.getLogger("user")

required_args = ["model_name", "host", "port", "interface", "model_max_input_tokens", "task"]

class CaikitEmbeddingPlugin(plugin.Plugin):
    def __init__(self, args):
        self._parse_args(args)

    def _parse_args(self, args):
        for arg in required_args:
            if arg not in args:
                logger.error("Missing plugin arg: %s", arg)

        self.model_name = args["model_name"]
        self.host = args["host"]
        self.port = args["port"]
        self.model_max_input_tokens = args["model_max_input_tokens"]
        self.save_raw_output = True if "save_raw_output" not in args else args["save_raw_output"]
        self.only_summary = False if "only_summary" not in args else args["only_summary"]
        self.batch_size = 1 if "batch_size" not in args else args["batch_size"]

        if args["task"] == "embedding":
            if args["interface"] == "http":
                self.url = f"{self.host}:{self.port}"
                self.request_func = self.request_http_embedding
            else:
                logger.error("Interface %s not yet implemented for %s", args["interface"], args["task"])
        elif args["task"] == "sentence_similarity":
            if args["interface"] == "http":
                self.url = f"{self.host}:{self.port}"
                self.request_func = self.request_http_sentence_similarity
            else:
                logger.error("Interface %s not yet implemented for %s", args["interface"], args["task"])
        elif args["task"] == "rerank":
            if args["interface"] == "http":
                self.url = f"{self.host}:{self.port}"
                self.request_func = self.request_http_rerank
            else:
                logger.error("Interface %s not yet implemented for %s", args["interface"], args["task"])
        else:
            logger.error("Task %s not yet implemented", args["task"])

        if args["task"] != "embedding":
            if "objects_per_request" in args:
                self.objects_per_request = args["objects_per_request"]
            else:
                self.objects_per_request = 10

    def request_grpc_embedding(self, query, user_id, test_end_time: float=0):
        """
        Not yet implemented as gRPC functionality is not yet implemented
        in caikit-nlp-client for the embeddings endpoints
        """
        return {}

    def request_http_embedding(self, query, user_id, test_end_time: float=0):
        http_client = HttpClient(self.host, verify=False)

        result = EmbeddingRequestResult(user_id, query.get("input_id"), query.get("input_tokens"))

        result.start_time = time.time()

        response = http_client.embedding_tasks(
            self.model_name,
            [query["text"] for _ in range(self.batch_size)],
            parameters={
                "truncate_input_tokens": self.model_max_input_tokens
            }
        )

        logger.debug("Response: %s", json.dumps(response))
        result.end_time = time.time()

        result.input_tokens = response["input_token_count"]
        result.input_objects = 1
        if self.save_raw_output:
            result.output_object = str([result["data"]["values"] for result in response["results"]])

        result.calculate_results()
        return result

    def request_http_sentence_similarity(self, query, user_id, test_end_time: float=0):
        http_client = HttpClient(self.host, verify=False)

        result = EmbeddingRequestResult(user_id, query.get("input_id"), query.get("input_tokens"))
        result.start_time = time.time()

        num_objects = 10

        response = http_client.sentence_similarity_tasks(
            self.model_name,
            [query["text"] for _ in range(self.batch_size)],
            list(query["text"] for _ in range(num_objects)),
            parameters={
                "truncate_input_tokens": self.model_max_input_tokens
            }
        )

        logger.debug("Response: %s", json.dumps(response))
        result.end_time = time.time()

        result.input_tokens = response["input_token_count"]
        result.input_objects = num_objects
        if self.save_raw_output:
            result.output_object = str(response)

        result.calculate_results()
        return result

    def request_http_rerank(self, query, user_id, test_end_time: float=0):
        http_client = HttpClient(self.host, verify=False)

        result = EmbeddingRequestResult(user_id, query.get("input_id"), query.get("input_tokens"))
        result.start_time = time.time()

        num_objects = 10

        response = http_client.rerank_tasks(
            self.model_name,
            [{query["text"]: i} for i in range(num_objects)],
            [query["text"] for _ in range(self.batch_size)],
            parameters={
                "truncate_input_tokens": self.model_max_input_tokens
            }
        )

        logger.debug("Response: %s", json.dumps(response))
        result.end_time = time.time()
        result.input_tokens = response["input_token_count"]
        result.input_objects = num_objects
        if self.save_raw_output:
            result.output_object = str(response)

        result.input_queries = self.batch_size
        result.calculate_results()
        return result

    def write_output(self, config, results_list):
        """Write output for embedding results"""
        output_options = config.get("output")
        output_path = output_options.get("dir")

        logging.info("Writing output to %s", output_path)
        path = Path(output_path)
        if not (path.exists() and path.is_dir()):
            logging.warning("Output path %s does not exist, creating it!", path)
            path.mkdir(parents=True, exist_ok=True)

        concurrency, duration, _ = utils.parse_config(config)
        outfile_name = output_options.get("file").format(
            concurrency=concurrency, duration=duration
        )
        outfile = path / Path(outfile_name)
        results_list = [result.asdict() for result in results_list]
        if self.only_summary:
            output_obj = {
                "config": config,
                "summary": {},
            }
        else:
            output_obj = {
                "results": results_list,
                "config": config,
                "summary": {},
            }

        logging.info("Length of results: %d", len(results_list))

        # TODO, should this be output using logging?
        df = pd.DataFrame(results_list)
        df.head()

        with pd.option_context("display.max_rows", None, "display.max_columns", None):
            print(df)
        print(f"\n---\nFull results in {outfile}. Results summary:")

        error_count = len(df[~df["error_text"].isnull()])
        req_count = len(df)
        print(f"Error count: {error_count} of {req_count} total requests")

        # Ignore errors for summary results
        df = df[df["error_text"].isnull()]

        summary_df = df[
            [
                "response_time",
                "input_tokens",
                "input_objects",
                "input_queries",
            ]
        ].mean(numeric_only=True)
        print(summary_df)

        # Only consider requests that were completed within the duration of the test for
        # calculating the summary statistics on tpot, ttft, itl, tt_ack
        req_completed_within_test_duration = len(df)

        # summaries
        output_obj = utils.get_summary(df, output_obj, "response_time")

        output_obj = utils.get_summary(df, output_obj, "input_tokens")

        output_obj = utils.get_summary(df, output_obj, "input_objects")

        output_obj = utils.get_summary(df, output_obj, "input_queries")

        # CALCULATE REAL DURATION NOT TARGET DURATION
        true_end = df["end_time"].max()
        true_start = df["start_time"].min()
        full_duration = true_end - true_start
        throughput_full_duration = df["input_tokens"].sum() / full_duration
        throughput_per_object = df["input_objects"].sum() / full_duration
        throughput_tokens_per_doc_per_sec = (df["input_tokens"].sum() / df["input_objects"].sum()) / full_duration
        print(
            f"Total true throughput across all users: {throughput_full_duration} tokens / sec, for duration {full_duration}"
        )

        throughput = df["input_tokens"].sum() / duration
        print(
            f"Total throughput across all users bounded by the test duration: {throughput} tokens / sec, for duration {duration}"
        )

        output_obj["summary"]["throughput_full_duration"] = throughput_full_duration
        output_obj["summary"]["throughput_per_object"] = throughput_per_object
        output_obj["summary"]["throughput_tokens_per_document_per_second"] = throughput_tokens_per_doc_per_sec
        output_obj["summary"]["full_duration"] = full_duration
        output_obj["summary"]["throughput"] = throughput
        output_obj["summary"]["total_requests"] = req_count
        output_obj["summary"]["total_tokens"] = df["input_tokens"].sum()
        output_obj["summary"][
            "req_completed_within_test_duration"
        ] = req_completed_within_test_duration
        output_obj["summary"]["total_failures"] = error_count
        output_obj["summary"]["failure_rate"] = error_count / req_count * 100
        output_obj["summary"]["start_time"] = true_start

        json_out = json.dumps(output_obj, cls=utils.customEncoder, indent=2)
        with outfile.open("w") as f:
            f.write(json_out)
