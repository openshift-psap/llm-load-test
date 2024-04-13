import json
import logging
import time

import requests
import urllib3

from plugins import plugin
from result import RequestResult

urllib3.disable_warnings()

required_args = ["host", "model_name"]

logger = logging.getLogger("user")

"""
Example plugin config.yaml:

plugin: "vllm_plugin"
plugin_options:
  interface: "http"
  streaming: True
  model_name: "Llama-2-7b-hf"
  host: "http://myhost"
  port: 80
"""

# TODO:
# - Add configurable timeout for requests
class VLLMPlugin(plugin.Plugin):
    def __init__(self, args):
        self._parse_args(args)

    def _parse_args(self, args):
        for arg in required_args:
            if arg not in args:
                logger.error("Missing plugin arg: %s", arg)

        endpoint = "/v1/completions"
        self.request_func = self.request_http
        self.host = args["host"] + endpoint
        self.model_name = args["model_name"]

    def request_http(self, query, user_id, test_end_time: float=0):

        headers = {"Content-Type": "application/json"}

        data = {
            "prompt": query["text"],
            "model": self.model_name,
            "max_tokens": 700,
            "temperature": 0,
            "stream": "True"
        }

        result = RequestResult(user_id, query.get("input_id"), query.get("input_tokens"))

        tokens = []
        result.start_time = time.time()
        response = None
        try:
            response = requests.post(
                self.host, headers=headers, json=data, verify=False, stream=True
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as err:
            result.end_time = time.time()
            result.error_text = repr(err)
            if response is not None:
                result.error_code = response.status_code
            return result
        except requests.exceptions.HTTPError as err:
            result.end_time = time.time()
            result.error_text = repr(err)
            if response is not None:
                result.error_code = response.status_code
            return result

        logger.debug("response: %s", response)
        for line in response.iter_lines():
            _, found, data = line.partition(b"data:")
            if found:
                try:
                    message = json.loads(data)
                    error = message.get("error")
                    if error is None:
                        token = message["choices"][0]["text"]
                        logger.debug("Token: %s", token)
                    else:
                        result.error_code = response.status_code
                        result.error_text = error
                        logger.error("Error received in response message: %s", error)
                        break
                except json.JSONDecodeError:
                    logger.error("response line could not be json decoded: %s", line)
                    continue
                except KeyError:
                    logger.error(
                        "KeyError, unexpected response format in line: %s", line
                    )
                    continue
            else:
                continue

            tokens.append(token)

        # Response received, return
        result.end_time = time.time()
        result.output_text = "".join(tokens)
        result.output_tokens = len(tokens)

        # TODO: Calculate correct output tokens before test timeout duration for streaming requests
        result.output_tokens_before_timeout = result.output_tokens

        result.calculate_results()
        return result
