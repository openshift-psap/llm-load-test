import json
import logging
import time

from caikit_nlp_client import HttpClient
import urllib3

from plugins import plugin

urllib3.disable_warnings()


"""
Example plugin config.yaml:

plugin: "caikit_client_plugin"
plugin_options:
  interface: "http" # Some plugins like caikit-nlp-client should support grpc/http
  streaming: True
  model_name: "Llama-2-7b-hf"
  route: "https://llama-2-7b-hf-isvc-predictor-dagray-test.apps.modelserving.nvidia.eng.rdu2.redhat.com:443"
"""

logger = logging.getLogger("user")

required_args = ["model_name", "route", "interface", "streaming"]

class CaikitClientPlugin(plugin.Plugin):
    def __init__(self, args):
        self._parse_args(args)

    def _parse_args(self, args):
        for arg in required_args:
            if arg not in args:
                logger.error("Missing plugin arg: %s", arg)

        if args["interface"] == "http":
            if args["streaming"]:
                self.request_func = self.make_streaming_request
            else:
                self.request_func = self.make_request
        else:
            logger.error("Interface %s not yet implemented", args['interface'])

        self.model_name = args["model_name"]
        self.route = args["route"]

    def make_request(self, query, user_id):
        http_client = HttpClient(self.route, verify=False)

        num_tokens = query['max_new_tokens']

        start_time = time.time()
        response = http_client.generate_text(
                self.model_name, 
                query['text'],
                min_new_tokens=query['min_new_tokens'], 
                max_new_tokens=query['max_new_tokens'], 
                timeout=240
                )
        logger.debug("Response: %s", json.dumps(response))
        end_time = time.time()

        return self._calculate_results(start_time, end_time, response, num_tokens, user_id, query)

    def make_streaming_request(self, query, user_id):
        http_client = HttpClient(self.route, verify=False)

        tokens = []
        ack_time = 0
        first_token_time = 0
        start_time = time.time()
        for token in http_client.generate_text_stream(
                self.model_name,
                query['text'],
                min_new_tokens=query['min_new_tokens'],
                max_new_tokens=query['max_new_tokens'],
                timeout=240
                ):
            # First chunk is not a token, just an acknowledgement of connection
            if not ack_time:
                ack_time = time.time()
            # First non empty chunk is the first token
            if not first_token_time and token != "":
                first_token_time = time.time()
            tokens.append(token)
            logger.debug("Token: %s", token)


        end_time = time.time()
    
        return self._calculate_results_stream(start_time, ack_time, first_token_time, end_time, tokens, user_id, query)
    
