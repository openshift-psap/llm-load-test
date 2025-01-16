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
