from caikit_nlp_client import HttpClient
import time
import json
import requests
requests.packages.urllib3.disable_warnings()

def make_streaming_request(query, user_id):
    host = "llama-2-7b-hf-isvc-predictor-dagray-test.apps.psap-watsonx-dgxa100.perf.lab.eng.bos.redhat.com"
    port=443
    model_name = "Llama-2-7b-hf"
    http_client = HttpClient(f"https://{host}:{port}", verify=False)
    
    chunks=[]
    start_time = time.time()
    ack_time = 0
    first_token_time=0
    
 
    for chunk in http_client.generate_text_stream(
            model_name, 
            query['text'],
            min_new_tokens=query['min_new_tokens'], max_new_tokens=query['max_new_tokens'], timeout=240
            ):
        # First chunk is not a token, just an acknowledgement of connection
        if not ack_time:
           ack_time = time.time()
        # First non empty chunk is the first token
        if not first_token_time and chunk != "":
            first_token_time=time.time()
        chunks.append(chunk)

    end_time = time.time()
    
    return calculate_results(start_time, ack_time, first_token_time, end_time, chunks, user_id, query)


def calculate_results(start_time, ack_time, first_token_time, end_time, chunks, user_id, query):
    resp_time = end_time - start_time
    TT_ack = 1000*(ack_time-start_time)
    TTFT = 1000*(first_token_time-start_time) # Time to first token in ms
    TPOT = ((1000*resp_time - TT_ack) / (len(chunks)-1)) # Time per output token in ms
    
    results = {
            'start': start_time,
            'end': end_time,
            'TT_ack': TT_ack,
            'TTFT': TTFT,
            'TPOT': TPOT,
            'response_time': resp_time,
            'output_tokens': len(chunks),
            'worker_id': user_id,
            'input_tokens': query.get('input_tokens'),
            'response_string': ''.join(chunks),
            'input_string': query.get('text')
            }
    
    return results

