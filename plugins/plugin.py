
class Plugin():
    def __init__(self, args):
        self.args = args

    def request_http(self, query, user_id):
        pass

    def streaming_request_http(self, query, user_id):
        pass

    def request_grpc(self, query, user_id):
        pass

    def streaming_request_grpc(self, query, user_id):
        pass

    def _calculate_results(self, start_time, end_time, response, num_tokens, user_id, query):
        resp_time = end_time - start_time
        tpot = (1000*resp_time) / num_tokens # Time per output token in ms
    
        results = {
            'start': start_time,
            'end': end_time,
            'tpot': tpot,
            'response_time': resp_time,
            'output_tokens': num_tokens,
            'worker_id': user_id,
            'input_tokens': query.get('input_tokens'),
            'response_string': response,
            'input_string': query.get('text')
            }
    
        return results

    def _calculate_results_stream(self, start_time, ack_time, first_token_time, end_time, tokens, user_id, query):
        resp_time = end_time - start_time
        tt_ack = 1000*(ack_time-start_time)
        ttft = 1000*(first_token_time-start_time) # Time to first token in ms
        tpot = (1000*resp_time - tt_ack) / (len(tokens)-1) # Time per output token in ms
    
        results = {
            'start': start_time,
            'end': end_time,
            'tt_ack': tt_ack,
            'ttft': ttft,
            'tpot': tpot,
            'response_time': resp_time,
            'output_tokens': len(tokens),
            'worker_id': user_id,
            'input_tokens': query.get('input_tokens'),
            'response_string': ''.join(tokens),
            'input_string': query.get('text')
            }
    
        return results
