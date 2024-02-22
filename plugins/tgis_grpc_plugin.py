import logging
import time

import grpc

import generation_pb2_grpc
from plugins import plugin
from result import RequestResult

logger = logging.getLogger("user")

required_args = ["model_name", "host", "port", "streaming"]

"""
This plugin currently only supports grpc requests for a standalone TGI server.

Example plugin config.yaml:

plugin: "tgis_grpc_plugin"
plugin_options:
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

        if args["streaming"]:
            self.request_func = self.make_request_stream
        else:
            self.request_func = self.make_request

    def make_request(self, query: dict, user_id: int):
        grpc_channel = grpc.insecure_channel(self.connection)
        generation_service_stub = generation_pb2_grpc.GenerationServiceStub(
            grpc_channel
        )

        result = RequestResult(user_id, query.get("text"), query.get("input_tokens"))
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
                    max_new_tokens=query["max_new_tokens"],
                    min_new_tokens=query["min_new_tokens"],
                ),
            ),
        )
        result.start_time = time.time()
        response = generation_service_stub.Generate(request=request)
        result.end_time = time.time()
        result.output_tokens = query["max_new_tokens"]
        result.output_text = response.responses[0].text

        result.calculate_results()
        return result

    def make_request_stream(self, query: dict, user_id: int):
        grpc_channel = grpc.insecure_channel(self.connection)
        generation_service_stub = generation_pb2_grpc.GenerationServiceStub(
            grpc_channel
        )
        result = RequestResult(user_id, query.get("text"), query.get("input_tokens"))
        tokens = []
        request = generation_pb2_grpc.generation__pb2.SingleGenerationRequest(
            model_id=self.model_name,
            request=generation_pb2_grpc.generation__pb2.GenerationRequest(
                text=query.get("text")
            ),
            params=generation_pb2_grpc.generation__pb2.Parameters(
                method=generation_pb2_grpc.generation__pb2.GREEDY,
                stopping=generation_pb2_grpc.generation__pb2.StoppingCriteria(
                    max_new_tokens=query["max_new_tokens"],
                    min_new_tokens=query["min_new_tokens"],
                ),
                response=generation_pb2_grpc.generation__pb2.ResponseOptions(
                    generated_tokens=True
                ),
            ),
        )
        result.start_time = time.time()
        resp_stream = generation_service_stub.GenerateStream(request=request)
        for resp in resp_stream:
            # the first response is not a token, just an acknowledgement
            if not result.ack_time and not resp.tokens:
                result.ack_time = time.time()
            if resp.tokens:
                if not result.first_token_time and resp.tokens[0].text != "":
                    result.first_token_time = time.time()
                tokens.append(resp.tokens[0].text)

        result.end_time = time.time()
        result.output_text = "".join(tokens)
        result.output_tokens = len(tokens)

        result.calculate_results()
        return result
