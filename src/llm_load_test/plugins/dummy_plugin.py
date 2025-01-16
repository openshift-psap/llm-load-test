import time

from llm_load_test.plugins import plugin
from llm_load_test.result import RequestResult

"""
Example plugin config.yaml:

plugin: "dummy"
plugin_options:
  streaming: True
"""


class DummyPlugin(plugin.Plugin):
    def __init__(self, args):
        self._parse_args(args)

    def _parse_args(self, args):
        if args["streaming"]:
            self.request_func = self.streaming_request_http
        else:
            self.request_func = self.request_http

    def request_http(self, query, user_id, test_end_time: float=0):
        result = RequestResult(user_id, query.get("input_id"), query.get("input_tokens"))
        result.start_time = time.time()

        # Fake response is just the input backwards
        result.output_text = query.get("text")[::-1]
        result.output_tokens = query["output_tokens"]
        result.output_tokens_before_timeout = result.output_tokens

        time.sleep(1)

        result.end_time = time.time()

        result.calculate_results()

        return result

    def streaming_request_http(self, query, user_id, test_end_time: float=0):
        result = RequestResult(user_id, query.get("input_id"), query.get("input_tokens"))
        result.start_time = time.time()
        time.sleep(0.1)

        result.ack_time = time.time()
        time.sleep(0.1)

        result.first_token_time = time.time()
        time.sleep(1)

        result.end_time = time.time()

        # Fake response is just the input backwards
        tokens = query.get("text", "")[::-1].split(" ")

        # Response received, return
        result.end_time = time.time()
        result.output_text = "".join(tokens)
        result.output_tokens = len(tokens)

        # TODO: Calculate correct output tokens before test timeout duration for streaming requests
        result.output_tokens_before_timeout = result.output_tokens

        result.calculate_results()
        return result
