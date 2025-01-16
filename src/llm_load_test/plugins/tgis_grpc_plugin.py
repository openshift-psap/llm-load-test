import logging
import time

import grpc
import socket
import ssl
import sys

from llm_load_test import generation_pb2_grpc
from llm_load_test.plugins import plugin
from llm_load_test.result import RequestResult

logger = logging.getLogger("user")

required_args = ["model_name", "host", "port", "streaming", "use_tls"]

"""
This plugin currently only supports grpc requests for a standalone TGI server.

Example plugin config.yaml:

plugin: "tgis_grpc_plugin"
plugin_options:
  use_tls: True/False
  streaming: True/False
  model_name: "Llama-2-7b-hf"
  host: "localhost"
  port: 8033
"""


class TGISGRPCPlugin(plugin.Plugin):
    def __init__(self, args):
        self._parse_args(args)
        self.connection = f"{self.host}:{self.port}"

    def _parse_args(self, args):
        for arg in required_args:
            if arg not in args:
                logger.error("Missing plugin arg: %s", arg)

        self.model_name = args["model_name"]
        self.host = args["host"]
        self.port = args["port"]
        self.use_tls = bool(args["use_tls"])

        if args["streaming"]:
            self.request_func = self.make_request_stream
        else:
            self.request_func = self.make_request

    def get_server_certificate(self, host: str, port: int) -> str:
        if sys.version_info >= (3, 10):
            # ssl.get_server_certificate supports TLS SNI only above 3.10
            # https://github.com/python/cpython/pull/16820
            return ssl.get_server_certificate((host, port))
        context = ssl.SSLContext()
        with socket.create_connection((host, port)) as sock, context.wrap_socket(
            sock, server_hostname=host
        ) as ssock:
            cert_der = ssock.getpeercert(binary_form=True)
        assert cert_der
        return ssl.DER_cert_to_PEM_cert(cert_der)

    def channel_credentials(self):
        cert = self.get_server_certificate(self.host, self.port).encode()
        credentials_kwargs: dict[str, bytes] = {}
        credentials_kwargs.update(root_certificates=cert)
        return grpc.ssl_channel_credentials(**credentials_kwargs)

    def make_request(self, query: dict, user_id: int, test_end_time: float = 0):
        if self.use_tls:
            grpc_channel = grpc.secure_channel(self.connection, self.channel_credentials())
        else:
            grpc_channel = grpc.insecure_channel(self.connection)

        generation_service_stub = generation_pb2_grpc.GenerationServiceStub(
            grpc_channel
        )

        result = RequestResult(
            user_id, query.get("input_id"), query.get("input_tokens")
        )
        request = generation_pb2_grpc.generation__pb2.BatchedGenerationRequest(
            model_id=self.model_name,
            requests=[
                generation_pb2_grpc.generation__pb2.GenerationRequest(
                    text=query.get("text")
                )
            ],
            params=generation_pb2_grpc.generation__pb2.Parameters(
                method=generation_pb2_grpc.generation__pb2.GREEDY,
                stopping=generation_pb2_grpc.generation__pb2.StoppingCriteria(
                    max_new_tokens=query["output_tokens"],
                    min_new_tokens=query["output_tokens"],
                ),
            ),
        )
        result.start_time = time.time()
        try:
            response = generation_service_stub.Generate(request=request)
        except grpc.RpcError as err:
            result.end_time = time.time()
            result.error_text = err.details()
            result.error_code = err.code().value[0]
            return result

        result.end_time = time.time()

        # Only doing one prompt per requests
        response = response.responses[0]
        result.input_tokens = response.input_token_count
        result.stop_reason = response.stop_reason
        result.output_text = response.text

        if response.generated_token_count:
            # For non-streaming requests we are keeping output_tokens_before_timeout and output_tokens same.
            result.output_tokens_before_timeout = (
                result.output_tokens
            ) = response.generated_token_count
        else:
            result.output_tokens = query["output_tokens"]

        result.calculate_results()
        return result

    def make_request_stream(self, query: dict, user_id: int, test_end_time: float):
        if self.use_tls:
            grpc_channel = grpc.secure_channel(self.connection, self.channel_credentials())
        else:
            grpc_channel = grpc.insecure_channel(self.connection)

        generation_service_stub = generation_pb2_grpc.GenerationServiceStub(
            grpc_channel
        )
        result = RequestResult(
            user_id, query.get("input_id"), query.get("input_tokens")
        )
        tokens = []
        request = generation_pb2_grpc.generation__pb2.SingleGenerationRequest(
            model_id=self.model_name,
            request=generation_pb2_grpc.generation__pb2.GenerationRequest(
                text=query.get("text")
            ),
            params=generation_pb2_grpc.generation__pb2.Parameters(
                method=generation_pb2_grpc.generation__pb2.GREEDY,
                stopping=generation_pb2_grpc.generation__pb2.StoppingCriteria(
                    max_new_tokens=query["output_tokens"],
                    min_new_tokens=query["output_tokens"],
                ),
                response=generation_pb2_grpc.generation__pb2.ResponseOptions(
                    generated_tokens=True
                ),
            ),
        )
        result.start_time = time.time()

        try:
            resp_stream = generation_service_stub.GenerateStream(request=request)
            for resp in resp_stream:
                # the first response is not a token, just an acknowledgement
                if not result.ack_time and not resp.tokens:
                    result.ack_time = time.time()
                    if resp.input_token_count:
                        result.input_tokens = resp.input_token_count
                if resp.tokens:
                    if not result.first_token_time and resp.tokens[0].text != "":
                        result.first_token_time = time.time()
                    # If the current token time is outside the test duration, record the total tokens received before
                    # the current token.
                    if (
                        not result.output_tokens_before_timeout
                        and time.time() > test_end_time
                    ):
                        result.output_tokens_before_timeout = len(tokens)
                    tokens.append(resp.text)
                if resp.stop_reason:
                    # Last resp
                    result.stop_reason = resp.stop_reason
                    result.output_tokens = resp.generated_token_count
                    # If test duration timeout didn't happen before the last token is received, total tokens before the
                    # timeout will be equal to the total tokens in the response.
                    if not result.output_tokens_before_timeout:
                        result.output_tokens_before_timeout = result.output_tokens
        except grpc.RpcError as err:
            result.end_time = time.time()
            result.error_text = err.details()
            result.error_code = err.code().value[0]
            return result

        result.end_time = time.time()
        result.output_text = "".join(tokens)

        if not result.input_tokens:
            logger.warning("Input token count not found in response, using dataset input_tokens")
            result.input_tokens = query.get("input_tokens")

        if not result.output_tokens:
            logger.warning("Output token count not found in response, using dataset expected output tokens")
            result.output_tokens = len(tokens)

        result.calculate_results()
        return result
