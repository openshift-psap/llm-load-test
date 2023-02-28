# pylint: disable=too-few-public-methods,empty-docstring,too-many-arguments
"""
"""

import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
import time
import uuid
import yaml

import boto3
import botocore.exceptions
import numpy as np

CONFIG_PATH = "IS_LOAD_TEST_CONFIG_PATH"
CONFIG_FILENAME = "IS_LOAD_TEST_CONFIG_FILENAME"


class Base():
    """
    Utility functions
    """

    def _exit_failure(self, msg):
        """
        """
        print(msg)
        sys.exit(1)

    def _create_temp_directory(self, working_directory=None):
        """
        """

        if not working_directory:
            sys.exit(1)
        temp_dir = os.path.join(working_directory, str(uuid.uuid4()))
        try:
            os.mkdir(temp_dir)
        except FileExistsError:
            print("Proposed working directory already exists, exiting")
            sys.exit(1)
        except FileNotFoundError:
            print("No such directory")
            sys.exit(1)
        return temp_dir

    def _yaml_load(self, file):
        """
        Simple YAML loader
        """
        if not os.path.isfile(file):
            raise FileNotFoundError(file)
        with open(file, 'r', encoding="utf-8") as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError:
                raise RuntimeError(f"Could not parse {file}") \
                    # pylint: disable=raise-missing-from

    def _json_load(self, file):
        """
        Simple JSON loader
        """
        if not os.path.isfile(file):
            raise FileNotFoundError(file)
        with open(file, "r", encoding="utf-8") as stream:
            try:
                return json.load(stream)
            except json.JSONDecodeError:
                raise RuntimeError(f"Could not parse {file}") \
                    # pylint: disable=raise-missing-from

    def _json_dump(self, dictionary, file):
        """
        Simple JSON file writer
        #TODO error checking
        """
        json_object = json.dumps(dictionary, indent=4)
 
        with open(file, "w") as outfile:
            outfile.write(json_object)  


class AnsibleWisdomQueryGenerator(Base):
    """
    Parses an input file containing one json object per line (Gold Dataset)
    and chooses a subset of input prompts / contexts
    to be used as input to the load generator querying the model.

    If max_size is defined, dataset will be a subset of max_size which are
    equally spaced from the full sorted dataset.
    """

    def __init__(self, file, max_size):
        input_json = self._json_load(file)
        self.dataset = input_json["dataset"]
        if max_size is not None:
            self.dataset = self._get_subset(max_size)

        self.dataset_version = input_json["metadata"]["version"]
        self.next_query = 0

    """
    Get the next query. Iterates through the dataset in a round-robin.
    """

    def get_next_query(self):
        ret_idx = self.next_query
        self.next_query = (self.next_query+1) % len(self.dataset)
        return self.dataset[ret_idx]

    """
    Access current dataset
    """

    def get_dataset(self):
        return self.dataset

    """
    Returns a subset of n queries, equally spaced from current self.queries
    """

    def _get_subset(self, max_size):
        query_list_length = len(self.dataset)
        indices = np.round(np.linspace(
            0, query_list_length - 1, max_size)).astype(int)
        return ([self.dataset[i] for i in indices])


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
            error=""
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


class S3Storage():
    """
    """

    def __init__(self, region, bucket, access_key=None, secret_key=None, s3_endpoint=None):
        """
        """
        try:
            session = boto3.Session(profile_name='default')
            region = region
            s3_client = session.client(
                service_name='s3',
                region_name=region,
                endpoint_url=s3_endpoint
            )
            # location = {'LocationConstraint': region}
        except botocore.exceptions.ClientError as err:
            logging.error(err)
            return
        self.s3_client = s3_client
        self.bucket = bucket

    def list_buckets(self):
        """
        """
        bucket_list = []
        try:
            response = self.s3_client.list_buckets()
            for bucket in response.get('Buckets'):
                # print(f'  {bucket["Name"]}')
                bucket_list.append(bucket)
        except botocore.exceptions.ClientError as err:
            logging.error(err)
            return None
        except TypeError:
            return None
        return bucket_list

    def upload_object_with_metadata(self, object_name, body, metadata):
        """
        """
        try:
            # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_object
            self.s3_client.put_object(
                Bucket=self.bucket,
                Body=str(body),
                Metadata=metadata,
                Key=object_name,
            )
        except botocore.exceptions.ClientError as err:
            logging.error(err)
            return

    def upload_file_with_metadata(self, filename, object_name, metadata):
        """
        """
        try:
            with open(filename, encoding="utf-8") as file:
                contents = file.read()
            # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.put_object
            self.s3_client.put_object(
                Bucket=self.bucket,
                Body=contents,
                Metadata=metadata,
                Key=object_name,
            )
        except botocore.exceptions.ClientError as err:
            logging.error(err)
            return

    def list_objects_paginated(self, prefix, delimiter):
        """
        """
        obj_list = []
        try:
            paginator = self.s3_client.get_paginator('list_objects')
            operation_parameters = {
                'Bucket': self.bucket,
                'Prefix': prefix,
                'Delimiter': delimiter
            }
            iterator = paginator.paginate(**operation_parameters)
            for response in iterator:
                for obj in response.get('Contents'):
                    # print(f'  {obj.get("Key")}')
                    obj_list.append(obj)
        except botocore.exceptions.ClientError as err:
            logging.error(err)
        except TypeError:
            return None
        return obj_list

    def retrieve_all_obj_metadata(self):
        """
        """
        metadata = {}
        paginator = self.s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=self.bucket)
        for page in page_iterator:
            for obj in page.get('Contents'):
                try:
                    metadata[obj.get('Key')] = self.s3_client.head_object(
                        Bucket=self.bucket,
                        Key=obj.get('Key')
                    )
                except botocore.exceptions.ClientError as err:
                    logging.error(err)
        return metadata

    def retrieve_object_body(self, key):
        """
        """
        try:
            res = self.s3_client.get_object(
                Bucket=self.bucket, Key=key)
            content = res.get('Body').read().decode('utf-8')
        except botocore.exceptions.ClientError as err:
            logging.error(err)
        except TypeError:
            return None
        return content

    def retrieve_object_metadata(self, key):
        """
        """
        try:
            metadata = self.s3_client.head_object(
                Bucket=self.bucket,
                Key=key
            )
        except botocore.exceptions.ClientError as err:
            logging.error(err)
        except TypeError:
            return None
        return metadata

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
        self.output_tokens=output_obj.get("generatedTokenCount")

    def get_output(self):
        """
        """
        return self.test_output

    def get_output_tokens(self):
        """
        """
        return self.output_tokens

    def set_input(self, prompt, context):
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
        #TODO check rcode, output, error
        rcode, output, error = super()._run_command(command, verbose=False)
        end_time = datetime.datetime.now().isoformat()

        self.test_output = super()._json_load("./temp.json")
        self.test_output["start_time"] = start_time
        self.test_output["end_time"] = end_time
    
        result = super()._json_load("./temp.json")
        self.test_metadata["date"] = result.get("date")
        self.test_metadata["start_time"] = start_time
        self.test_metadata["end_time"] = end_time
        self.test_metadata["throughput"] = str(self.test_output.get("rps"))
        self.test_metadata["min_latency"] =  str(float(self.test_output.get("fastest"))/(10**9))
        self.test_metadata["prompt"] = self.query
        self.test_metadata["ghz_concurrency"] = str(self.ghz_concurrency)
        self.test_metadata["ghz_max_requests"] = str(self.total_requests)


    def get_command(self):
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

            #TODO Should NOT be hardcoded
            test_metadata["modelmesh_pods_per_node"] = "4"
            test_metadata["nodes"] = "1"
            output_obj["modelmesh_pods_per_node"] = "4"
            output_obj["nodes"] = "1"

            #TODO delete this local copy
            super()._json_dump(output_obj, f"ghz-test-{start_time}-.json")

            path = self.s3_result_path()
            s3_json_obj =  "{}-ghz-results.json".format(str(uuid.uuid4()))
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


class DatasetDemo():
    """
    Demo for the dataset generator
    """

    def __init__(self):
        print("#################")
        test_query_generator = AnsibleWisdomQueryGenerator(
            "sorted_dataset.json", max_size=4)
        print("Dataset version: {}".format(
            test_query_generator.dataset_version))
        token_sizes = [x["op_token_count"]
                       for x in test_query_generator.dataset]
        print("Token sizes of all entries in the dataset:  {}".format(token_sizes))
        print("#################")
        print("Here are the next 5 queries to be used (round robin):")
        for i in range(5):
            next_query = test_query_generator.get_next_query()
            print({"prompt": next_query["prompt"],
                  "context": next_query["context"]})


class S3Demo():
    """
    Demo for the S3 storage backend.
    """

    def __init__(self):
        """
        """
        print("#################")
        print("Connecting to S3...")
        self.storage = S3Storage(
            region='us-east-1',
            #access_key="myuser",
            #secret_key="25980928",
            #s3_endpoint="http://localhost:9000",
            bucket="wisdom-perf-data-test"
        )
        print("Listing buckets...")
        buckets = self.storage.list_buckets()
        print("Uploading a test file")
        self.storage.upload_file_with_metadata(
            filename="data.txt",
            object_name="test/data.txt",
            metadata={'my_personal_key': 'my_personal_value'}
        )
        print("All done! Will display the results in 5 seconds")
        print("#################")
        time.sleep(5)
        obj_list_p = self.storage.list_objects_paginated("test/", "/")
        metadata = self.storage.retrieve_all_obj_metadata()
        obj_content = self.storage.retrieve_object_body("test/data.txt")
        obj_metadata = self.storage.retrieve_object_metadata("test/data.txt")
        print("#################")
        print(f"Bucket list: {buckets}")
        print("#################")
        print(f'List of objects (paginated): {obj_list_p}')
        print("#################")
        print(f'List of all objects\' metadata: {metadata}')
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
