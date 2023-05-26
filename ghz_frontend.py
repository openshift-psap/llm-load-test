# pylint: disable=too-few-public-methods,empty-docstring,too-many-arguments,too-many-instance-attributes
"""
"""

import argparse
import datetime
import json
import os
import time
import subprocess
import uuid


from ansible_wisdom_query_generator import AnsibleWisdomQueryGenerator
from base import Base
from demo import DatasetDemo, S3Demo
from s3storage import S3Storage

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
        self.storage_config = {}
        self.command_config = {}
        self.input_dataset = {}
        self.test_conditions = {}
        base_path = os.getenv("CONFIG_PATH")
        config_file = os.getenv("CONFIG_FILENAME")
        if base_path is None:
            base_path = os.path.dirname(os.path.realpath(__file__))
        if config_file is None:
            config_file = "config.json"
        try:
            config_full_path = os.path.join(base_path, config_file)
            print(f"Using config file from: {config_full_path}")
            self.config = super()._json_load(config_full_path)
        except (FileNotFoundError, RuntimeError) as msg:
            super()._exit_failure("Could not open/parse " + str(msg))
        self.__parse_storage_config()
        self.__parse_command_config()
        self.__parse_test_conditions()
        self.warmup = self.config.get("warmup")

    def get_complete_config(self):
        """
        Deprecated
        """
        return self.config

    def get_storage_config(self):
        """
        Returns a dictionary of the storage configuration.
        Currently only S3 buckets are supported.
        """
        return self.storage_config

    def __parse_storage_config(self):
        """
        Meant to be called at config load time e.g. constructor.
        Only supports S3 atm.
        """
        if self.config.get("storage").get("type") == "s3":
            self.storage_config["type"] = "s3"
            subconfig = self.config.get("storage").get("s3_params")
            self.storage_config["host"] = subconfig.get("s3_host")
            self.storage_config["use_https"] = subconfig.get("s3_use_https")
            self.storage_config["s3_access_key"] = subconfig.get("s3_access_key")
            self.storage_config["s3_secret_key"] = subconfig.get("s3_secret_key")
            self.storage_config["s3_bucket"] = subconfig.get("s3_bucket")
            self.storage_config["s3_region"] = subconfig.get("s3_region")

            s3_separator = subconfig.get("s3_separator")
            s3_base_path = subconfig.get("s3_base_path")
            s3_component = subconfig.get("s3_component")
            s3_sub_component = subconfig.get("s3_sub_component")
            s3_sub_comp_version = subconfig.get("s3_sub_comp_version")
            self.storage_config["s3_result_path"] = s3_separator.join([
                s3_base_path,
                s3_component,
                s3_sub_component,
                s3_sub_comp_version
            ])
            # self.storage_config[""] = ""

    def __parse_command_config(self):
        """
        Meant to be called at config load time e.g. constructor
        Only supports ghz atm.
        """
        if self.config.get("launcher").get("type") == "ghz":
            self.command_config["type"] = "ghz"
            subconfig = self.config.get("launcher").get("ghz_params")
            self.command_config["host"] = subconfig.get("host")
            self.command_config["insecure"] = subconfig.get("insecure")
            self.command_config["proto_path"] = subconfig.get("proto_path")
            self.command_config["call"] = subconfig.get("call")
            self.command_config["vmodel_id"] = subconfig.get("vmodel_id")
            self.command_config["query"] = subconfig.get("query")
            self.command_config["context"] = subconfig.get("context")
            self.command_config["concurrency"] = subconfig.get("concurrency")
            self.command_config["requests"] = subconfig.get("requests")
            # self.command_config[""] = ""
            launcher_dataset_config = self.config.get("launcher").get("input_dataset")
            self.input_dataset["filename"] = launcher_dataset_config.get("filename")
            self.input_dataset["max_size"] = launcher_dataset_config.get("max_size")
            # self.input_dataset[""] = ""

    def __parse_test_conditions(self):
        """
        Meant to be called at config load time e.g. constructor
        Used for any extra metadata which will be attached to results,
        that is not already apart of the ghz / storage config.
        """
        test_conditions = self.config.get("test_conditions")

        # S3 metadata needs to be strings
        for keys in test_conditions:
            test_conditions[keys] = str(test_conditions[keys])
        self.test_conditions = test_conditions

    def get_command_config(self):
        """
        Returns a dictionary of the command configuration.
        Currently only GHZ commands are supported (type: ghz)
        """
        return self.command_config

    def get_input_dataset(self):
        """
        Returns a dictionary of the dataset configuration.
        """
        return self.input_dataset
    

    def get_warmup(self):
        """
        Returns boolean, whether warm up is enabled
        """
        return self.warmup
    
    def get_test_conditions(self):
        """
        Returns a dictionary of the test condition metadata
        """
        return self.test_conditions


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
        # grpcurl can only search for protos in current dir
        self.proto_dir = os.path.dirname(params.get("proto_path"))
        self.proto_file = os.path.basename(params.get("proto_path"))
        self.current_directory = os.getcwd()

    def run(self):
        """
        """
        data_obj = {"prompt": self.query, "context": self.context}

        command = ["grpcurl",
                   "-plaintext",
                   "-proto",
                   f"{self.proto_file}",
                   "-d",
                   json.dumps(data_obj),
                   "-H",
                   f"mm-vmodel-id: {self.vmodel_id}",
                   f"{self.host}",
                   f"{self.call}",
                   ]
        print(command)

        # grpcurl can only search for protos in current dir
        os.chdir(os.path.join(self.proto_dir))
        rcode, output, _ = super()._run_command(command, verbose=False)
        os.chdir(self.current_directory)
        if rcode != 0:
            raise RuntimeError

        self.test_output = ''.join([byte_array.decode('utf-8') for byte_array in output])
        output_obj = json.loads(self.test_output)
        # output_text = output_obj.get("text")
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
        self.proto_path = params.get("proto_path")

    def run(self):
        """
        """
        command = self.get_command()

        print(command)
        start_time = datetime.datetime.now().isoformat()
        # TODO check rcode, output, error
        rcode, _, _ = super()._run_command(command, verbose=False)
        if rcode != 0:
            raise RuntimeError
        end_time = datetime.datetime.now().isoformat()

        self.test_output = super()._json_load("./temp.json")
        self.test_output["start_time"] = start_time
        self.test_output["end_time"] = end_time
        self.test_output["prompt"] = self.query
        self.test_output["context"] = self.context

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
                   f"{self.proto_path}",
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
                   "-t",
                   "240s",
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

    def __init__(self, storage_config, command_config, input_dataset, test_conditions, warmup):
        """
        """
        # do we need an abstraction layer here?
        self.storage_config = storage_config
        self.command_config = command_config
        self.test_conditions = test_conditions
        self.warmup = warmup

        self.ghz_instance = GhzRunner(
            params={
                "concurrency": self.command_config.get("concurrency"),
                "requests": self.command_config.get("requests"),
                "host": self.command_config.get("host"),
                "query": "temp",
                "context": "temp",
                "insecure": self.command_config.get("insecure"),
                "call": self.command_config.get("call"),
                "vmodel_id": self.command_config.get("vmodel_id"),
                "proto_path": self.command_config.get("proto_path")
            }
        )

        self.grpcurl_instance = GRPCurlRunner(
            params={
                "host": self.command_config.get("host"),
                "query": "",
                "context": "",
                "insecure": self.command_config.get("insecure"),
                "call": self.command_config.get("call"),
                "vmodel_id": self.command_config.get("vmodel_id"),
                "proto_path": self.command_config.get("proto_path")
            }
        )

        self.dataset_gen = AnsibleWisdomQueryGenerator(
            input_dataset.get("filename"),
            input_dataset.get("max_size")
        )

        self.storage = S3Storage(
            region=self.storage_config.get("s3_region"),
            bucket=self.storage_config.get("s3_bucket")
        )

    def s3_result_path(self):
        """
        Temporary hack for our planned file structure in S3.
        This path should depend on the config / param input to the experiment.
        """
        date_day = datetime.datetime.today().strftime('%Y-%m-%d')
        base_path = self.storage_config.get("s3_result_path")
        path = f"{base_path}/{date_day}"
        return path
    
    def upload_to_s3(self, obj, metadata):
            path = self.s3_result_path()
            s3_json_obj_name = "{}-ghz-results.json".format(str(uuid.uuid4()))
            self.storage.upload_object_with_metadata(
                body=json.dumps(obj),
                object_name=f"{path}/{s3_json_obj_name}",
                metadata=metadata
            )

            obj_content = self.storage.retrieve_object_body(f"{path}/{s3_json_obj_name}")
            obj_metadata = self.storage.retrieve_object_metadata(f"{path}/{s3_json_obj_name}")
            print("#################")
            print(f'Object body: {obj_content}')
            print("#################")
            print(f'Object metadata: {obj_metadata.get("Metadata")}')

    def run_tests(self, dataset, save_output=True):
        for query in dataset:
            time.sleep(15) # Sleep to show a break in CPU/GPU utilization metrics between runs
            print(f"###### Running GRPCURL/GHZ with query: \n{query}")
            self.grpcurl_instance.set_input(query.get("prompt"), query.get("context"))
            self.grpcurl_instance.run()
            output_tokens = self.grpcurl_instance.get_output_tokens()
            grpcurl_result = self.grpcurl_instance.get_output()
            print(f"GRPCURL Result tokens: {output_tokens}, response: {grpcurl_result}")

            self.ghz_instance.set_input(query.get("prompt"), query.get("context"))
            self.ghz_instance.run()

            test_metadata = self.ghz_instance.get_metadata()
            output_obj = self.ghz_instance.get_output()

            # Insert test_conditions metadata into test_metadata and output_obj
            test_metadata.update(self.test_conditions)
            output_obj.update(self.test_conditions)

            output_obj["output_tokens"] = f"{output_tokens}"
            test_metadata["output_tokens"] = f"{output_tokens}"
            
            # TODO delete this local copy?
            start_time = test_metadata.get("start_time")
            super()._json_dump(output_obj, f"ghz-test-{start_time}.json")
           
            if save_output:
                self.upload_to_s3(output_obj, test_metadata)


    def run(self):
        """
        """
        dataset = self.dataset_gen.get_dataset()
        if self.warmup:
            save_concurrency = self.ghz_instance.ghz_concurrency
            save_requests = self.ghz_instance.total_requests
            # fill the queues but avoid overload errors 
            self.ghz_instance.ghz_concurrency = 4*self.ghz_instance.ghz_concurrency
            self.ghz_instance.total_requests = 200*save_concurrency

            print("############ DOING WARMUP RUNS ##############")
            # Warmup with only first entry in dataset 
            self.run_tests(dataset[1:2], save_output=False)
            self.ghz_instance.ghz_concurrency = save_concurrency
            self.ghz_instance.total_requests = save_requests
        
        print("############ WARMUP PHASE COMPLETE ##############")
        print("############  RUNNING LOAD TESTS   ##############")
        self.run_tests(dataset, save_output=True)
        


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
        test = AnsibleWisdomExperimentRunner(
            storage_config=config.get_storage_config(),
            command_config=config.get_command_config(),
            input_dataset=config.get_input_dataset(),
            warmup=config.get_warmup(),
            test_conditions=config.get_test_conditions(),
        )
        test.run()


if __name__ == "__main__":
    main()
