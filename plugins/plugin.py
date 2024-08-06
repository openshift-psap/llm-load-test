import json
import logging
from pathlib import Path

import pandas as pd

import utils

class Plugin:
    def __init__(self, args):
        self.args = args

    def request_http(self, query, user_id):
        pass

    def streaming_request_http(self, query, user_id):
        pass

    def request_grpc(self, query, user_id):
        pass

    def streaming_request_grpc(self, query, user_id):
        pass

    def write_output(self, config, results_list):
        """Write the results."""
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

        if "ttft" in df:
            # Streaming
            summary_df = df[
                [
                    "tt_ack",
                    "ttft",
                    "itl",
                    "tpot",
                    "response_time",
                    "output_tokens",
                    "output_tokens_before_timeout",
                    "input_tokens",
                ]
            ].mean(numeric_only=True)
        else:
            # Non-streaming, no TTFT or ITL
            summary_df = df[
                [
                    "tpot",
                    "response_time",
                    "output_tokens",
                    "output_tokens_before_timeout",
                    "input_tokens",
                ]
            ].mean(numeric_only=True)
        print(summary_df)

        # Only consider requests that were completed within the duration of the test for
        # calculating the summary statistics on tpot, ttft, itl, tt_ack
        df_test_duration = df[df["output_tokens"] == df["output_tokens_before_timeout"]]
        req_completed_within_test_duration = len(df_test_duration)

        # Time per output token summary
        output_obj = utils.get_summary(df_test_duration, output_obj, "tpot")

        if "ttft" in df:
            # Time to first token summary
            output_obj = utils.get_summary(df_test_duration, output_obj, "ttft")

            # Inter-token latency summary
            output_obj = utils.get_summary(df_test_duration, output_obj, "itl")

            # Time to ack summary
            output_obj = utils.get_summary(df_test_duration, output_obj, "tt_ack")

        # response time summary
        output_obj = utils.get_summary(df, output_obj, "response_time")

        # output tokens summary
        output_obj = utils.get_summary(df, output_obj, "output_tokens")

        # output tokens summary
        output_obj = utils.get_summary(df, output_obj, "output_tokens_before_timeout")

        # input tokens summary
        output_obj = utils.get_summary(df, output_obj, "input_tokens")

        # CALCULATE REAL DURATION NOT TARGET DURATION
        true_end = df["end_time"].max()
        true_start = df["start_time"].min()
        full_duration = true_end - true_start
        throughput_full_duration = df["output_tokens"].sum() / full_duration
        print(
            f"Total true throughput across all users: {throughput_full_duration} tokens / sec, for duration {full_duration}"
        )

        throughput = df["output_tokens_before_timeout"].sum() / duration
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

