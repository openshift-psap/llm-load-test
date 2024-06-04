import tiktoken

class Plugin:
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


    def num_tokens_from_string(self,input_string) -> int:
        """Returns the number of tokens in a text string."""
        encoding = tiktoken.get_encoding("cl100k_base")
        num_tokens = len(encoding.encode(input_string))
        return num_tokens

