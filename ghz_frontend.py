# pylint: disable=too-few-public-methods,empty-docstring,too-many-arguments
"""
"""

import argparse
import datetime
import json
import os
import subprocess
import uuid

from ansible_wisdom_query_generator import AnsibleWisdomQueryGenerator
from base import Base
from demo import DatasetDemo, S3Demo
from s3storage import S3Storage

CONFIG_PATH = "IS_LOAD_TEST_CONFIG_PATH"
CONFIG_FILENAME = "IS_LOAD_TEST_CONFIG_FILENAME"


class CommandRunner(Base):
    """
    """

    def _run_command(self, command, verbose=True):
        """
        """

        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE
        ) as process:
            full_output = []
            full_error = []
            error = ""
            while True:
                try:
                    output = process.stdout.readline()
                except:
                    pass
                try:
                    error = process.stderr.readline()
                except:
                    pass
                if process.poll() is not None:
                    break
                if output:
                    full_output.append(output)
                    if verbose:
                        print(output.strip())
                if error:
                    full_error.append(output)
                    if verbose:
                        print(error.strip())
            rcode = process.poll()
        return rcode, full_output, full_error


class Config(Base):
    """
    """

    def __init__(self):
        """
        """
        base_path = os.getenv(CONFIG_PATH)
        config_file = os.getenv(CONFIG_FILENAME)
        if base_path is None:
            base_path = os.path.dirname(os.path.realpath(__file__))
        if config_file is None:
            config_file = "config.json"
        try:
            self.config = super()._json_load(
                os.path.join(base_path, config_file)
            )
        except (FileNotFoundError, RuntimeError) as msg:
            super()._exit_failure("Could not open/parse " + str(msg))

    def get_complete_config(self):
        """
        """
        return self.config


class GRPCurlRunner(CommandRunner, Base):
    """
    """

    def __init__(self, params):
        """
        """
        self.call = params.get("call")
        self.test_output = None
        self.output_tokens = 0
        self.test_metadata = {}
        self.host = params.get("host")
        self.query = params.get("query")
        self.context = params.get("context")
        self.vmodel_id = params.get("vmodel_id")

    def run(self):
        """
        """
        data_obj = {"prompt": self.query, "context": self.context}
        command = ["grpcurl",
                   "-plaintext",
                   "-proto",
                   "common-service.proto",
                   "-d",
                   json.dumps(data_obj),
                   "-H",
                   f"mm-vmodel-id: {self.vmodel_id}",
                   f"{self.host}",
                   f"{self.call}",
                   ]

        print(command)
        rcode, output, error = super()._run_command(command, verbose=False)
        self.test_output = ''.join([byte_array.decode('utf-8') for byte_array in output])
        output_obj = json.loads(self.test_output)
        output_text = output_obj.get("text")
        self.output_tokens = output_obj.get("generatedTokenCount")

    def get_output(self):
        """
        """
        return self.test_output

    def get_output_tokens(self):
        """
        """
        return self.output_tokens

    def set_input(self, prompt, context):
        """
        """
        self.query = prompt
        self.context = context


class GhzRunner(CommandRunner, Base):
    """
    """

    def __init__(self, params):
        """
        """
        self.test_output = None
        self.test_metadata = {}
        self.ghz_concurrency = params.get("concurrency")
        self.total_requests = params.get("requests")
        self.host = params.get("host")
        self.query = params.get("query")
        self.context = params.get("context")
        self.insecure = "--insecure" if params.get("insecure") else None
        self.call = params.get("call")
        self.vmodel_id = params.get("vmodel_id")

    def run(self):
        """
        """
        command = self.get_command()

        print(command)
        start_time = datetime.datetime.now().isoformat()
        # TODO check rcode, output, error
        rcode, output, error = super()._run_command(command, verbose=False)
        if rcode != 0:
            raise RuntimeError
        end_time = datetime.datetime.now().isoformat()

        self.test_output = super()._json_load("./temp.json")
        self.test_output["start_time"] = start_time
        self.test_output["end_time"] = end_time

        result = super()._json_load("./temp.json")
        self.test_metadata["date"] = result.get("date")
        self.test_metadata["start_time"] = start_time
        self.test_metadata["end_time"] = end_time
        self.test_metadata["throughput"] = str(self.test_output.get("rps"))
        self.test_metadata["min_latency"] = str(float(self.test_output.get("fastest"))/(10**9))
        self.test_metadata["prompt"] = self.query
        self.test_metadata["ghz_concurrency"] = str(self.ghz_concurrency)
        self.test_metadata["ghz_max_requests"] = str(self.total_requests)

    def get_command(self):
        """
        """
        data_obj = {"prompt": self.query, "context": self.context}
        command = ["ghz",
                   self.insecure,
                   "--disable-template-data",
                   "--proto",
                   "./protos/common-service.proto",
                   "--call",
                   f"{self.call}",
                   "-d",
                   json.dumps(data_obj),
                   f"{self.host}",
                   "--metadata",
                   f"{{\"mm-vmodel-id\":\"{self.vmodel_id}\"}}",
                   "-c",
                   f"{self.ghz_concurrency}",
                   "--total",
                   f"{self.total_requests}",
                   "-O",
                   "json",
                   "-o",
                   "./temp.json",
                   ]
        return command

    def get_output(self):
        """
        """
        return self.test_output

    def get_metadata(self):
        """
        """
        return self.test_metadata

    def set_input(self, prompt, context):
        """
        """
        self.query = prompt
        self.context = context


class AnsibleWisdomExperimentRunner(Base):
    """
    """

    def __init__(self):
        """
        """
        self.ghz_instance = GhzRunner(
            params={
                "concurrency": 4,
                "requests": 128,
                "host": "localhost:8033",
                "query": "temp",
                "context": "temp",
                "insecure": True,
                "call": "watson.runtime.wisdom_ext.v0.WisdomExtService.AnsiblePredict",
                "vmodel_id": "gpu-version-inference-service-v02"

            }
        )

        self.grpcurl_instance = GRPCurlRunner(
            params={
                "host": "localhost:8033",
                "query": "install httpd on rhel",
                "context": "",
                "insecure": True,
                "call": "watson.runtime.wisdom_ext.v0.WisdomExtService.AnsiblePredict",
                "vmodel_id": "gpu-version-inference-service-v02"
            }
        )

        self.dataset_gen = AnsibleWisdomQueryGenerator(
            "sorted_dataset.json", max_size=5)

        self.storage = S3Storage(
            region='us-east-1',
            bucket="wisdom-perf-data-test"
        )

    def s3_result_path(self):
        """
        Temporary hack for our planned file structure in S3.
        This path should depend on the config / param input to the experiment.
        """
        date_day = datetime.datetime.today().strftime('%Y-%m-%d')
        path = f"InferenceResults/ModelMesh/WatsonRuntime/Wisdom_v0.0.8/{date_day}"
        return path

    def run(self):
        """
        """
        dataset = self.dataset_gen.get_dataset()
        for query in dataset:
            print("#################")
            print(f"###### Running GRPCURL/GHZ with query: \n{query}")
            self.grpcurl_instance.set_input(query.get("prompt"), query.get("context"))
            self.grpcurl_instance.run()
            output_tokens = self.grpcurl_instance.get_output_tokens()

            self.ghz_instance.set_input(query.get("prompt"), query.get("context"))
            self.ghz_instance.run()

            test_metadata = self.ghz_instance.get_metadata()
            test_metadata["output_tokens"] = f"{output_tokens}"

            start_time = test_metadata.get("start_time")

            output_obj = self.ghz_instance.get_output()
            output_obj["output_tokens"] = f"{output_tokens}"

            # TODO Should NOT be hardcoded
            test_metadata["modelmesh_pods_per_node"] = "4"
            test_metadata["nodes"] = "1"
            output_obj["modelmesh_pods_per_node"] = "4"
            output_obj["nodes"] = "1"

            # TODO delete this local copy
            super()._json_dump(output_obj, f"ghz-test-{start_time}-.json")

            path = self.s3_result_path()
            s3_json_obj = "{}-ghz-results.json".format(str(uuid.uuid4()))
            self.storage.upload_object_with_metadata(
                body=json.dumps(output_obj),
                object_name=f"{path}/{s3_json_obj}",
                metadata=test_metadata
            )

            obj_content = self.storage.retrieve_object_body(f"{path}/{s3_json_obj}")
            obj_metadata = self.storage.retrieve_object_metadata(f"{path}/{s3_json_obj}")
            print("#################")
            print(f'Object body: {obj_content}')
            print("#################")
            print(f'Object metadata: {obj_metadata.get("Metadata")}')


class GHZDemo():
    """
    """

    def __init__(self):
        """
        """
        self.ghz_instance = GhzRunner(
            params={
                "concurrency": 3,
                "requests": 9,
                "host": "localhost:8033",
                "query": "install httpd on rhel",
                "context": "",
                "insecure": True,
                "call": "watson.runtime.wisdom_ext.v0.WisdomExtService.AnsiblePredict",
                "vmodel_id": "gpu-version-inference-service-v02"
            }
        )
        self.storage = S3Storage(
            region='default',
            access_key="myuser",
            secret_key="25980928",
            s3_endpoint="http://localhost:9000",
            bucket="mybucket"
        )

    def run(self):
        """
        """
        self.ghz_instance.run()
        print("#################")
        print("Uploading a test file")
        test_date = self.ghz_instance.get_output().get("date")
        self.storage.upload_object_with_metadata(
            body=self.ghz_instance.get_output(),
            object_name=f"data/test-{test_date}.json",
            metadata={
                'date': test_date
            }
        )
        obj_content = self.storage.retrieve_object_body(
            f"data/test-{test_date}.json")
        obj_metadata = self.storage.retrieve_object_metadata(
            f"data/test-{test_date}.json")
        print("#################")
        print(f'Object body: {obj_content}')
        print("#################")
        print(f'Object metadata: {obj_metadata.get("Metadata")}')


def main():
    """
    CLI.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="increase output verbosity")
    parser.add_argument("--ghz", action="store_true",
                        help="use ghz")
    parser.add_argument("--s3demo", action="store_true",
                        help="S3 Demo")
    parser.add_argument("--dataset_demo", action="store_true",
                        help="Dataset Demo")
    parser.add_argument("--wisdom_experiment", action="store_true",
                        help="Ansible Wisdom model experiment")
    args = parser.parse_args()
    config = Config()
    if args.verbose:
        print(config.get_complete_config())
    if args.s3demo:
        S3Demo()
    if args.dataset_demo:
        DatasetDemo()
    if args.ghz:
        demo = GHZDemo()
        demo.run()
    if args.wisdom_experiment:
        test = AnsibleWisdomExperimentRunner()
        test.run()


if __name__ == "__main__":
    main()
