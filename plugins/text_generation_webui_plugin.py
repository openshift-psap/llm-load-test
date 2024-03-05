import json
import logging
import time

import requests
import urllib3

from plugins import plugin
from result import RequestResult

urllib3.disable_warnings()
"""
Example plugin config.yaml:

plugin: "text_generation_webui_plugin"
plugin_options:
  streaming: True
  host: "http://127.0.0.1:5000/v1/completions"
"""

required_args = ["host", "streaming"]

logger = logging.getLogger("user")

# TODO:
# - Add error handling to requests
# - Add configurable timeout for requests


class TextGenerationWebUIPlugin(plugin.Plugin):
    def __init__(self, args):
        self._parse_args(args)

    def _parse_args(self, args):
        for arg in required_args:
            if arg not in args:
                logger.error("Missing plugin arg: %s", arg)

        if args["streaming"]:
            self.request_func = self.streaming_request_http
        else:
            logger.error("option streaming: %s not yet implemented", args["streaming"])

        self.host = args["host"]

    def streaming_request_http(self, query, user_id):
        headers = {"Content-Type": "application/json"}

        data = {
            "prompt": query["text"],
            "max_tokens": query["output_tokens"],  # min tokens??
            "temperature": 1.0,
            "top_p": 0.9,
            "seed": 10,
            "stream": True,
        }

        result = RequestResult(user_id, query.get("input_id"), query.get("input_tokens"))

        tokens = []
        result.start_time = time.time()

        response = requests.post(
            self.host, headers=headers, json=data, verify=False, stream=True
        )

        logger.debug("response: %s", response)
        for line in response.iter_lines():
            _, found, data = line.partition(b"data:")
            if found:
                try:
                    message = json.loads(data)
                    token = message["choices"][0]["text"]
                except json.JSONDecodeError:
                    logger.error("response line could not be json decoded: %s", line)
                except KeyError:
                    logger.error(
                        "KeyError, unexpected response format in line: %s", line
                    )
            else:
                continue

            # First token is not a token, just an acknowledgement of connection
            if not result.ack_time:
                result.ack_time = time.time()
                tokens.append(token)
                continue
            # First non empty token is the first token
            if not result.first_token_time and token != "":
                result.first_token_time = time.time()
            tokens.append(token)

        # Full response received, return
        result.end_time = time.time()
        result.output_text = "".join(tokens)
        result.output_tokens = len(tokens)

        result.calculate_results()
        return result
