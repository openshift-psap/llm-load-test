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

    def request_grpc_embedding(self, query, user_id, test_end_time: float=0):
        """
        Not yet implemented as gRPC functionality is not yet implemented
        in caikit-nlp-client for the embeddings endpoints
        """
        grpc_client = GrpcClient(self.host, self.port, verify=False)

        result = EmbeddingRequestResult(user_id, query.get("input_id"), query.get("input_tokens"))

        result.start_time = time.time()
        response = grpc_client.generate_text(
            self.model_name,
            query["text"],
            min_new_tokens=query["output_tokens"],
            max_new_tokens=query["output_tokens"],
            # timeout=240 #Not supported, may need to contribute to caikit-nlp-client
        )

        logger.debug("Response: %s", json.dumps(response))
        result.end_time = time.time()

        result.output_tokens = query["output_tokens"]
        result.output_tokens_before_timeout = result.output_tokens
        result.output_text = response

        result.calculate_results()
        return result

    def request_http_embedding(self, query, user_id, test_end_time: float=0):
        http_client = HttpClient(self.host, verify=False)

        result = EmbeddingRequestResult(user_id, query.get("input_id"), query.get("input_tokens"))

        result.start_time = time.time()

        response = http_client.embedding(
            self.model_name,
            query["text"],
            parameters={
                "truncate_input_tokens": self.model_max_input_tokens
            }
        )

        logger.debug("Response: %s", json.dumps(response))
        result.end_time = time.time()

        result.input_tokens = response["input_token_count"]
        result.output_embeddings = str(response["result"]["data"]["values"])

        result.calculate_results()
        return result

    def request_http_sentence_similarity(self, query, user_id, test_end_time: float=0):
        http_client = HttpClient(self.host, verify=False)

        result = EmbeddingRequestResult(user_id, query.get("input_id"), query.get("input_tokens"))
        result.start_time = time.time()

        response = http_client.sentence_similarity(
            self.model_name,
            query["text"],
            list(query["text"] for _ in range(10)),
            parameters={
                "truncate_input_tokens": self.model_max_input_tokens
            }
        )

        logger.debug("Response: %s", json.dumps(response))
        result.end_time = time.time()

        result.output_tokens = response["input_token_count"]
        result.output_tokens_before_timeout = result.output_tokens
        result.output_text = str(response)

        result.calculate_results()
        return result

    def request_http_rerank(self, query, user_id, test_end_time: float=0):
        http_client = HttpClient(self.host, verify=False)

        result = EmbeddingRequestResult(user_id, query.get("input_id"), query.get("input_tokens"))
        result.start_time = time.time()

        response = http_client.rerank(
            self.model_name,
            [{query["text"]: i} for i in range(10)],
            query["text"],
            parameters={
                "truncate_input_tokens": self.model_max_input_tokens
            }
        )

        logger.debug("Response: %s", json.dumps(response))
        result.end_time = time.time()

        result.output_tokens = response["input_token_count"]
        result.output_tokens_before_timeout = result.output_tokens
        result.output_text = str(response)

        result.calculate_results()
        return result

    @staticmethod
    def write_output(config, results_list):
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
            ]
        ].mean(numeric_only=True)
        print(summary_df)

        # Only consider requests that were completed within the duration of the test for
        # calculating the summary statistics on tpot, ttft, itl, tt_ack
        req_completed_within_test_duration = len(df)

        # response time summary
        output_obj = utils.get_summary(df, output_obj, "response_time")

        # input tokens summary
        output_obj = utils.get_summary(df, output_obj, "input_tokens")

        # CALCULATE REAL DURATION NOT TARGET DURATION
        true_end = df["end_time"].max()
        true_start = df["start_time"].min()
        full_duration = true_end - true_start
        throughput_full_duration = df["input_tokens"].sum() / full_duration
        print(
            f"Total true throughput across all users: {throughput_full_duration} tokens / sec, for duration {full_duration}"
        )

        throughput = df["input_tokens"].sum() / duration
        print(
            f"Total throughput across all users bounded by the test duration: {throughput} tokens / sec, for duration {duration}"
        )

        output_obj["summary"]["throughput_full_duration"] = throughput_full_duration
        output_obj["summary"]["full_duration"] = full_duration
        output_obj["summary"]["throughput"] = throughput
        output_obj["summary"]["total_requests"] = req_count
        output_obj["summary"][
            "req_completed_within_test_duration"
        ] = req_completed_within_test_duration
        output_obj["summary"]["total_failures"] = error_count
        output_obj["summary"]["failure_rate"] = error_count / req_count * 100

        json_out = json.dumps(output_obj, cls=utils.customEncoder, indent=2)
        with outfile.open("w") as f:
            f.write(json_out)
