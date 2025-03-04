"""Abstract class for plugin."""


class Plugin:
    """Abstract class for plugin."""

    def __init__(self, args):
        """Initialize the plugin."""
        self.args = args

    def request_http(self, query, user_id):
        """Make a syncronous HTTP request."""
        pass

    def streaming_request_http(self, query, user_id):
        """Make a streaming HTTP request."""
        pass

    def request_grpc(self, query, user_id):
        """Make a syncronous gRPC request."""
        pass

    def streaming_request_grpc(self, query, user_id):
        """Make a streaming gRPC request."""
        pass
