
import time
import json
import requests
from plugins import plugin
requests.packages.urllib3.disable_warnings()
"""
Example plugin config.yaml:

plugin: "text_generation_webui_plugin"
plugin_options:
  streaming: True
  route: "http://127.0.0.1:5000/v1/completions"
"""

required_args = ["route", "streaming"]

class TextGenerationWebUIPlugin(plugin.Plugin):
    def __init__(self, args):
        self._parse_args(args)

    def _parse_args(self, args):
        for arg in required_args:
            if not args[arg]:
                print(f"Missing plugin arg: {arg}") #throw error
    
        if args["streaming"]:
            self.request_func = self.make_streaming_request
        else:
            print(f"option streaming: {args['streaming']} not yet implemented") #throw error

        self.route = args["route"]
        

    def make_streaming_request(self, query, user_id):
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

        chunks=[]
        ack_time = 0
        first_token_time=0
        start_time = time.time()

        response = requests.post(self.route, headers=headers, json=data, verify=False, stream=True)
        print(f"Response: {response}")
        for line in response.iter_lines():
            if line and line[:5] == b"data:":
                try:
                    message = json.loads(line[6:])
                except json.JSONDecodeError:
                    print(f"unexpected model response could not be json decoded: {message}")
                chunk = message['choices'][0]['text']
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

            #print("".join(chunks))

        end_time = time.time()
    
        return self._calculate_results(start_time, ack_time, first_token_time, end_time, chunks, user_id, query)