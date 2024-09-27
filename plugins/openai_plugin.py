import json
import logging
import time
from typing import Optional

import requests
import urllib3

from plugins import plugin
from result import RequestResult
from utils import deepget

urllib3.disable_warnings()
"""
Example plugin config.yaml:

plugin: "openai_plugin"
plugin_options:
  streaming: True/False
  host: "http://127.0.0.1:5000/v1/completions"
  model_name: "/mnt/model/"
  endpoint: "/v1/completions" # "/v1/chat/completions"
"""

required_args = ["host", "streaming", "endpoint"]
APIS = ["legacy", "chat"]

logger = logging.getLogger("user")

# This plugin is written primarily for testing vLLM, though it can be made
# to work for other runtimes which conform to the OpenAI API, as required.
class OpenAIPlugin(plugin.Plugin):
    def __init__(self, args):
        self._parse_args(args)

    def _parse_args(self, args):
        for arg in required_args:
            if arg not in args:
                logger.error("Missing plugin arg: %s", arg)

        if args["streaming"]:
            self.request_func = self.streaming_request_http
        else:
            self.request_func = self.request_http

        self.host = args.get("host") + args.get("endpoint")

        logger.debug("Host: %s", self.host)

        self.model_name = args.get("model_name")

        logger.debug("Model name: %s", self.model_name)

        self.api = args.get('api')

        if not self.api:
            self.api = 'chat' if "/v1/chat/completions" in self.host else 'legacy'

        if self.api not in APIS:
            logger.error("Invalid api type: %s", self.api)

    def _process_resp(self, resp: bytes) -> Optional[dict]:
        try:
            _, found, data = resp.partition(b"data: ")
            if not found:
                return None
            message = json.loads(data)
            logger.debug("Message: %s", message)
            return message
        except json.JSONDecodeError:
            logger.exception("Response line could not be json decoded: %s", resp)
        except KeyError:
            logger.exception(
                "KeyError, unexpected response format in line: %s", resp
            )

    def request_http(self, query: dict, user_id: int, test_end_time: float = 0):

        result = RequestResult(user_id, query.get("text"), query.get("input_tokens"))

        result.start_time = time.time()

        headers = {"Content-Type": "application/json"}

        if self.api == 'chat':
            data = {
                "messages": [
                    {"role": "user", "content": query["text"]}
                ],
                "max_tokens": query["output_tokens"],
                "temperature": 0.1,
            }
        else: # self.api == 'legacy'
            data = {
                "prompt": query["text"],
                "max_tokens": query["output_tokens"],
                "min_tokens": query["output_tokens"],
                "temperature": 1.0, # FIXME: This seems wrong
                "top_p": 0.9, # FIXME: Standardize on something
                "seed": 10, # FIXME: Standardize on something
            }
        if self.model_name is not None:
            data["model"] = self.model_name

        response = None
        try:
            response = requests.post(self.host, headers=headers, json=data, verify=False)
            response.raise_for_status()
        except requests.exceptions.ConnectionError as err:
            result.end_time = time.time()
            result.error_text = repr(err)
            if response is not None:
                result.error_code = response.status_code
            logger.exception("Connection error")
            return result
        except requests.exceptions.HTTPError as err:
            result.end_time = time.time()
            result.error_text = repr(err)
            if response is not None:
                result.error_code = response.status_code
            logger.exception("HTTP error")
            return result

        result.end_time = time.time()

        ###########################################
        # DO NOT CALL time.time BEYOND THIS POINT #
        ###########################################

        logger.debug("Response: %s", json.dumps(response.text))

        try:
            message = json.loads(response.text)
            error = message.get("error")
            if error is None:
                if self.api == 'chat':
                    result.output_text = deepget(message, "choices", 0, 'delta', 'content')
                else: # self.api == 'legacy'
                    result.output_text = deepget(message, "choices", 0, 'text')

                result.output_tokens = deepget(message, "usage", "completion_tokens")
                result.input_tokens = deepget(message, "usage", "prompt_tokens")
                result.stop_reason =  deepget(message, "choices", 0, "finish_reason")
            else:
                result.error_code = response.status_code
                result.error_text = error
                logger.error("Error received in response message: %s", error)
        except json.JSONDecodeError:
            logger.exception("Response could not be json decoded: %s", response.text)
            result.error_text = f"Response could not be json decoded {response.text}"
        except KeyError:
            logger.exception("KeyError, unexpected response format: %s", response.text)
            result.error_text = f"KeyError, unexpected response format: {response.text}"

        # For non-streaming requests we are keeping output_tokens_before_timeout and output_tokens same.
        result.output_tokens_before_timeout = result.output_tokens
        result.calculate_results()

        return result


    def streaming_request_http(self, query: dict, user_id: int, test_end_time: float):
        headers = {"Content-Type": "application/json"}

        data = {
            "max_tokens": query["output_tokens"],
            "temperature": 0.1,
            "stream": True,
            "stream_options": {
                "include_usage": True
            }
        }

        if self.api == 'chat':
            data["messages"] = [
                { "role": "user", "content": query["text"] }
            ]
        else: # self.api == 'legacy'
            data["prompt"] = query["text"],
            data["min_tokens"] = query["output_tokens"]

        # some runtimes only serve one model, won't check this.
        if self.model_name is not None:
            data["model"] = self.model_name

        result = RequestResult(user_id, query.get("input_id"))

        response = None
        result.start_time = time.time()
        try:
            response = requests.post(
                self.host, headers=headers, json=data, verify=False, stream=True
            )
            response.raise_for_status()
        except (
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError
        ) as err:
            result.end_time = time.time()
            result.error_text = repr(err)
            if response is not None:
                result.error_code = response.status_code
            logger.exception("Connection error")
            return result

        resps = []
        try:
            for line in response.iter_lines():
                recv_time = time.time() # Record time asap
                # Only record lines with data
                if line:
                    logger.debug("response line: %s", line)
                    resps.append(dict(
                        time = recv_time,
                        data = line
                    ))
            # Full response received
            result.end_time = time.time()
        except requests.exceptions.ChunkedEncodingError as err:
            result.end_time = time.time()
            result.error_text = repr(err)
            #result.output_text = "".join([])
            result.output_tokens = len(resps)
            if response is not None:
                result.error_code = response.status_code
            logger.exception("ChunkedEncodingError while streaming response")
            return result

        ###########################################
        # DO NOT CALL time.time BEYOND THIS POINT #
        ###########################################

        # If no data was received return early
        if not resps:
            result.output_tokens = 0
            result.error_code = response.status_code
            return result

        # Check for end of request marker
        if resps[-1]['data'] == b"data: [DONE]":
            result.end_time = resps[-1]['time']
            resps.pop() # Drop the end indicator
        else:
            # TODO This signals that the request is incomplete
            pass

        # Check for usage statistics
        message = self._process_resp(resps[-1]['data'])
        # If stream_options.include_usage == True then the final
        # message contains only token stats
        if message and not message.get("choices") and message.get('usage'):
            result.output_tokens = deepget(message, "usage", "completion_tokens")
            result.input_tokens = deepget(message, "usage", "prompt_tokens")
            # We don't want to record this message
            resps.pop()

        # Iterate through all responses
        tokens = []
        prev_time = 0
        for resp in resps:
            message = self._process_resp(resp['data'])
            if not message:
                # TODO: This may be bad
                continue

            if message.get('error'):
                result.error_code = response.status_code
                result.error_text = message['error']
                logger.error("Error received in response message: %s", result.error_text)

            token = {}
            token['time'] = resp['time']
            token['lat'] = token['time'] - prev_time
            prev_time = token['time']

            if self.api == 'chat':
                token["text"] = deepget(message, "choices", 0, 'delta', 'content')
            else: # self.api == 'legacy'
                token["text"] = deepget(message, "choices", 0, 'text')

            # Skip blank tokens
            if not token['text']:
                continue

            # Append our vaild token
            tokens.append(token)

        # First chunk may not be a token, just a connection ack
        result.ack_time = resps[0]['time']

        # First non empty token is the first token
        result.first_token_time = tokens[0]['time']

        # If the current token time is outside the test duration, record the total tokens received before
        # the current token.
        tokens_before_timeout = [t for t in tokens if t['time'] <= test_end_time]
        result.output_tokens_before_timeout = len(tokens_before_timeout)

        # Last token comes with finish_reason set.
        result.stop_reason = deepget(resps[-1], "choices", 0, "finish_reason")

        # Full response received, return
        result.output_text = "".join([token['text'] for token in tokens])

        if not result.input_tokens:
            logger.warning("Input token count not found in response, using dataset input_tokens")
            result.input_tokens = query.get("input_tokens")

        if not result.output_tokens:
            logger.warning("Output token count not found in response, length of token list")
            result.output_tokens = len(tokens)

        # If test duration timeout didn't happen before the last token is received, 
        # total tokens before the timeout will be equal to the total tokens in the response.
        if not result.output_tokens_before_timeout:
            result.output_tokens_before_timeout = result.output_tokens

        result.calculate_results()
        return result
