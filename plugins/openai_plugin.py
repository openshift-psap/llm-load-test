import json
import logging
import time
from typing import Any, Optional, Union

import requests
import urllib3

from plugins import plugin
from result import RequestResult

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

def deepget(obj: Union[dict, list], *path: Any, default: Any = None) -> Any:
    """
    Acts like .get() but for nested objects.

    Each item in path is recusively indexed on obj. For path of length N,
      obj[path[0]][path[1]]...[path[N-1]][path[N]]

    :param obj: root object to index
    :param path: ordered list of keys to index recursively
    :param default: the default value to return if an indexing fails
    :returns: result of final index or default if Key/Index Error occurs
    """
    current = obj
    for pos in path:
        try:
            current = current[pos]
        except (KeyError, IndexError):
            return default
    return current


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

        # TODO Make this configurable
        self.request_defaults = dict(
            temperature = 0.0,
            seed = 42,
        )

        self.authorization = args.get("authorization")

    def _process_resp(self, resp: bytes) -> Optional[dict]:
        try:
            _, found, data = resp.partition(b"data: ")
            if not found:
                return None
            message = json.loads(data)
            logger.debug("Message: %s", message)
        except json.JSONDecodeError:
            logger.exception("Response line could not be json decoded: %s", resp)
            return None

        return message

    def request_http(self, query: dict, user_id: int, test_end_time: float = 0):

        result = RequestResult(user_id, query.get("text"), query.get("input_tokens"))

        result.start_time = time.time()

        headers = {"Content-Type": "application/json"}
        
        if self.authorization: 
            headers["Authorization"] = f"Bearer {self.authorization}"

        request = {
            "max_tokens": query["output_tokens"],
            "min_tokens": query["output_tokens"],
        }

        if self.api == 'chat':
            request["messages"] = [
                { "role": "user", "content": query["text"] }
            ]
        else: # self.api == 'legacy'
            request["prompt"] = query["text"],

        if self.model_name is not None:
            request["model"] = self.model_name

        # Merge request and defaults
        data = self.request_defaults | request

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

        # For non-streaming requests we are keeping output_tokens_before_timeout and output_tokens same.
        result.output_tokens_before_timeout = result.output_tokens
        result.calculate_results()

        return result


    def streaming_request_http(self, query: dict, user_id: int, test_end_time: float):

        headers = {"Content-Type": "application/json"}
        
        if self.authorization: 
            headers["Authorization"] = f"Bearer {self.authorization}"

        request = {
            "max_tokens": query["output_tokens"],
            "min_tokens": query["output_tokens"],
            "stream": True,
            "stream_options": {
                "include_usage": True
            }
        }

        if self.api == 'chat':
            request["messages"] = [
                { "role": "user", "content": query["text"] }
            ]
        else: # self.api == 'legacy'
            request["prompt"] = query["text"],

        # some runtimes only serve one model, won't check this.
        if self.model_name is not None:
            request["model"] = self.model_name

        # Merge request and defaults
        data = self.request_defaults | request

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
            logger.warning("End of response marker missing, response may be incomplete")

        # Check for usage statistics
        message = self._process_resp(resps[-1]['data'])
        # If stream_options.include_usage == True then the final
        # message contains only token stats
        expected_output_tokens = None
        if message and not message.get("choices") and message.get('usage'):
            # We want to count output tokens ourselves, but we can check our work with usage data.
            expected_output_tokens = deepget(message, "usage", "completion_tokens")
            result.input_tokens = deepget(message, "usage", "prompt_tokens")
            # We don't want to record this message
            resps.pop()
        else:
            logger.warning("Usage statistics are missing, token count will be inaccurate")

        # Iterate through all responses
        # Responses can have more than one token in certain scenarios
        # such as speculative decoding, thus an item in this list
        # represents one or more tokens
        tokens = []
        prev_time = 0
        total_usage = 0
        for resp in resps:
            message = self._process_resp(resp['data'])
            if not message:
                result.error_code = response.status_code
                result.error_text = 'bad_response'
                logger.error("Skipping a token that failed to parse, this may be bad")
                continue

            if message.get('error'):
                result.error_code = response.status_code
                result.error_text = message['error']
                logger.error("Error received in response message: %s", result.error_text)
                continue

            token = {}

            if self.api == 'chat':
                token["text"] = deepget(message, "choices", 0, 'delta', 'content')
            else: # self.api == 'legacy'
                token["text"] = deepget(message, "choices", 0, 'text')

            # If the message has the current usage then record the number of
            # tokens, otherwise assume 1 token
            current_usage = deepget(message, "usage", "completion_tokens")
            if current_usage != None:
                token['count'] = current_usage - total_usage
            else:
                token['count'] = 1

            # Omit responses that don't have
            # tokens (or somehow negative tokens)
            if token['count'] < 1:
                logger.debug("Omiting response '%s' because it contains %d tokens",
                             token["text"], token['count'])
                continue

            # Update the total token count
            total_usage += token['count']

            token['time'] = resp['time']
            token['lat'] = token['time'] - prev_time
            prev_time = token['time']

            # Find the last response with finish_reason set.
            if deepget(message, "choices", 0, "finish_reason"):
                result.stop_reason = deepget(message, "choices", 0, "finish_reason")

            # Append our valid token
            tokens.append(token)

        # First chunk may not be a token, just a connection ack
        result.ack_time = resps[0]['time']

        # First non empty token is the first token
        result.first_token_time = tokens[0]['time']

        # If the current token time is outside the test duration, record the total tokens received before
        # the current token.
        result.output_tokens_before_timeout = sum(t['count'] for t in tokens if t['time'] <= test_end_time)

        # Full response received, return
        result.output_text = "".join([token['text'] for token in tokens])

        if not result.input_tokens:
            logger.warning("Input token count not found in response, using dataset input_tokens")
            result.input_tokens = query.get("input_tokens")

        result.output_tokens = total_usage # Just reuse our count from the loop
        if expected_output_tokens and result.output_tokens != expected_output_tokens:
            logger.warning(f"Received {result.output_tokens} tokens but expected {expected_output_tokens} tokens")

        result.calculate_results()
        return result
