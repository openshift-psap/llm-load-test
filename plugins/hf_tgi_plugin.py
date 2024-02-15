import json
import logging
import time

import requests
import urllib3

from plugins import plugin
from result import RequestResult

urllib3.disable_warnings()

required_args = ["host", "streaming"]

logger = logging.getLogger("user")


# TODO:
# - Add configurable timeout for requests
class HFTGIPlugin(plugin.Plugin):
    def __init__(self, args):
        self._parse_args(args)

    def _parse_args(self, args):
        for arg in required_args:
            if arg not in args:
                logger.error("Missing plugin arg: %s", arg)

        if args["streaming"]:
            endpoint = "/generate_stream"
            self.request_func = self.streaming_request_http
        else:
            endpoint = "/generate"
            logger.error("option streaming: %s not yet implemented", args["streaming"])

        self.host = args["host"] + endpoint

    def streaming_request_http(self, query, user_id):

        headers = {"Content-Type": "application/json"}

        data = {
            "inputs": query["text"],
            "parameters": {
                "max_new_tokens": query["max_new_tokens"],
                "temperature": 1.0,  # Just an example
                "details": False,
            },
        }

        result = RequestResult(user_id, query.get("text"), query.get("input_tokens"))

        tokens = []
        result.start_time = time.time()
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
                        token = message["token"]["text"]
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

            # First chunk is not a token, just an acknowledgement of connection
            if not result.ack_time:
                result.ack_time = time.time()
                tokens.append(token)
                continue

            # First non empty chunk is the first token
            if not result.first_token_time and token != "":
                result.first_token_time = time.time()
            tokens.append(token)

        # Response received, return
        result.end_time = time.time()
        result.output_text = "".join(tokens)
        result.output_tokens = len(tokens)

        result.calculate_results()
        return result
