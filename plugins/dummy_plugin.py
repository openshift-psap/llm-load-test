import time
import json

def make_streaming_request(query, user_id):
    start_time = time.time()
    ack_time = 0
    first_token_time=0
    
    ack_time = time.time()
    time.sleep(1)
    first_token_time=time.time()
    time.sleep(1)
    end_time=time.time()
    chunks = query.get('text').split(' ')
    return calculate_results(start_time, ack_time, first_token_time, end_time, chunks, user_id, query)


def calculate_results(start_time, ack_time, first_token_time, end_time, chunks, user_id, query):
    resp_time = end_time - start_time
    TT_ack = 1000*(ack_time-start_time)
    TTFT = 1000*(first_token_time-start_time) # Time to first token in ms
    TPOT = ((1000*resp_time - TT_ack) / (len(chunks)-1)) # Time per output token in ms
    
    results = {
            'TT_ack ': TT_ack,
            'TTFT': TTFT,
            'TPOT': TPOT,
            'response_time': resp_time,
            'output_tokens': len(chunks),
            'worker_id': user_id,
            'input_tokens': query.get('max_input_tokens'),
            'response_string': ''.join(chunks),
            'input_string': query.get('text')
            }
    
    return results

