import time
import json

from caikit_nlp_client import HttpClient
import time
import json
import requests
from plugins import plugin
requests.packages.urllib3.disable_warnings()


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
            self.request_func = self.make_streaming_request
        else:
            self.request_func = self.make_request
        
    def make_request(self, query, user_id):

        response = query.get('text')
        num_tokens = query['max_new_tokens']
        
        start_time = time.time()
        time.sleep(2)
        end_time = time.time()
    
        return self._calculate_results(start_time, end_time, response, num_tokens, user_id, query)

    def make_streaming_request(self, query, user_id):
        start_time = time.time()
        ack_time = 0
        first_token_time=0
    
        ack_time = time.time()
        time.sleep(1)
        first_token_time=time.time()
        time.sleep(1)
        end_time=time.time()
        chunks = query.get('text').split(' ')
        return self._calculate_results_streamcalculate_results_(start_time, ack_time, first_token_time, end_time, chunks, user_id, query)
    
