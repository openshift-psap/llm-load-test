
import time
import json
import logging
import requests
import urllib3
from plugins import plugin
urllib3.disable_warnings()
"""
Example plugin config.yaml:

plugin: "text_generation_webui_plugin"
plugin_options:
  streaming: True
  route: "http://127.0.0.1:5000/v1/completions"
"""

required_args = ["route", "streaming"]

logger = logging.getLogger("user")

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
            logger.error("option streaming: %s not yet implemented", args['streaming'])

        self.route = args["route"] 

    def streaming_request_http(self, query, user_id):
        headers = {
            "Content-Type": "application/json"
        }

        data = {
            "prompt": query['text'],
            "max_tokens": query['max_new_tokens'], #min tokens??
            "temperature": 1.0,
            "top_p": 0.9,
            "seed": 10,
            "stream": True,
        }

        chunks = []
        ack_time = 0
        first_token_time=0
        start_time = time.time()

        # TODO add configurable timeout to requests
        response = requests.post(self.route, headers=headers, json=data, verify=False, stream=True)
        logger.debug("response: %s", response)
        for line in response.iter_lines():
            _, found, data = line.partition(b"data:")
            if found:
                try:
                    message = json.loads(data)
                    chunk = message['choices'][0]['text']
                except json.JSONDecodeError:
                    logger.error("response line could not be json decoded: %s", line)
                except KeyError:
                    logger.error("KeyError, unexpected response format in line: %s", line)
            else:
                continue

            # First chunk is not a token, just an acknowledgement of connection
            if not ack_time:
                ack_time = time.time()
                chunks.append(chunk)
                continue
            # First non empty chunk is the first token
            if not first_token_time and chunk != "":
                first_token_time=time.time()
            chunks.append(chunk)


        end_time = time.time()

        return self._calculate_results_stream(start_time,
                                              ack_time,
                                              first_token_time,
                                              end_time,
                                              chunks,
                                              user_id,
                                              query)
