# pylint: disable=too-few-public-methods,empty-docstring,too-many-arguments,too-many-instance-attributes
"""
"""

import argparse
import datetime
import json
import os
import time
import subprocess
import sys
import uuid
import random

from concurrent.futures import ThreadPoolExecutor

from input_generator import InputGenerator
from base import Base
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

    def __init__(self, config_file="config.yaml"):
        """
        """
        self.storage_config = {}
        self.load_gen_config = {}
        self.input_dataset = {}
        self.metadata = {}
        base_path = os.getenv("CONFIG_PATH")
        config_file_env = os.getenv("CONFIG_FILENAME")
        if base_path is None:
            base_path = os.path.dirname(os.path.realpath(__file__))
        if config_file_env is not None:
            config_file = config_file_env
        try:
            print(f"Base path: {base_path}")
            config_full_path = os.path.join(base_path, config_file)
            print(f"Using config file from: {config_full_path}")
            self.config = super()._yaml_load(config_full_path)
        except (FileNotFoundError, RuntimeError) as msg:
            super()._exit_failure("Could not open/parse " + str(msg))
        self.__parse_storage_config()
        self.__parse_load_gen_config()
        self.__parse_metadata()
        self.warmup = self.config.get("warmup") # TODO remove warmup option, it is unused in lightspeed cpt
        self.output_dir = self.config.get("output_dir")
        print(f"Config: self.warmup: {self.warmup} self.output_dir: {self.output_dir}")

    def get_output_dir(self):
        return self.output_dir
    
    def get_threads(self):
        return self.threads

    def get_complete_config(self):
        """
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
        Only supports S3 and local.
        """
        if self.config.get("storage").get("type") == "s3":
            self.storage_config = self.config.get("storage").get("s3_params").copy()
            self.storage_config["type"] = "s3"
        elif self.config.get("storage").get("type") == "local":
            self.storage_config["type"] = "local"


    def __parse_load_gen_config(self):
        """
        Meant to be called at config load time e.g. constructor
        Only supports ghz atm.
        """

        load_gen_config = self.config.get("load_generator")
        if load_gen_config.get("type") == "ghz":
            self.load_gen_config = self.config.get("load_generator").get("ghz_params").copy()
            self.load_gen_config["type"] = "ghz"
        
        self.threads = load_gen_config.get("threads", 8)

        self.input_dataset = load_gen_config.get("input_dataset").copy()

        self.multiplexed = load_gen_config.get("multiplexed")

    def __parse_metadata(self):
        """
        Meant to be called at config load time e.g. constructor
        Used for any extra metadata which will be attached to results,
        that is not already apart of the ghz / storage config.
        """
        metadata = self.config.get("metadata")

        # S3 metadata needs to be strings
        for keys in metadata:
            metadata[keys] = str(metadata[keys])
        self.metadata = metadata

    def get_load_gen_config(self):
        """
        Returns a dictionary of the command configuration.
        Currently only GHZ commands are supported (type: ghz)
        """
        return self.load_gen_config
    
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

    def get_metadata(self):
        """
        Returns a dictionary of the test condition metadata
        """
        return self.metadata


class GhzRunner(CommandRunner, Base):
    """
    """

    def __init__(self, params, output_dir):
        """
        """
        self.test_output = None
        self.test_metadata = {}
        self.output_dir=output_dir
        self.ghz_params=params

        self.uuid = uuid.uuid4()

        # Some tests (e.g. ansible lightspeed) need input data in different formats.
        # The expectation is that this will get overwritten before used,
        # and that the format of this string will match the required format for the
        # model under test.
        self.input = {"text": "Temporary ghz input prompt in json format"}

    def run(self):
        """
        """

        self.ghz_params["data"] = self.input
        self.ghz_params["format"] = "json"
        self.ghz_params["output"] = f"{self.output_dir}/{self.uuid}.json"

        config_file_name=f"{self.output_dir}/ghz-config-{self.uuid}.json"
        self._json_dump(self.ghz_params, config_file_name, overwrite=True)
        print(f"Running ghz with the follow config json in file {config_file_name}")
        print(self.ghz_params)

        start_time = datetime.datetime.now().isoformat()

        command = ["ghz", f"--config={config_file_name}"]
        rcode, _, _ = super()._run_command(command, verbose=False)
        if rcode != 0:
            raise RuntimeError
        end_time = datetime.datetime.now().isoformat()

        self.test_output = super()._json_load(self.ghz_params["output"])
        self.test_output["start_time"] = start_time
        self.test_output["end_time"] = end_time
        self.test_output["input"] = self.input
        # TODO cleanup this metadata
        # - Flatten all test configs into a string:string dict {x.y.z: foo}
        # - Add only extra required metadata like start/end times
        self.test_metadata["date"] = self.test_output.get("date")
        self.test_metadata["start_time"] = start_time
        self.test_metadata["end_time"] = end_time
        self.test_metadata["throughput"] = str(self.test_output.get("rps"))
        self.test_metadata["min_latency"] = str(float(self.test_output.get("fastest"))/(10**9))
        #self.test_metadata["input"] = json.dumps(self.input)
        self.test_metadata["concurrency"] = str(self.ghz_params.get('concurrency'))
        self.test_metadata["ghz_max_requests"] = str(self.ghz_params.get('total'))
        self.test_metadata["ghz_max_duration"] = str(self.ghz_params.get('duration'))

    def get_output(self):
        """
        """
        return self.test_output

    def get_metadata(self):
        """
        """
        return self.test_metadata

    def set_input(self, input):
        """
        """
        self.input=input

class ParallelExperimentRunner(Base):
    """
    """

    def __init__(
        self,
        storage_config,
        load_gen_config,
        input_dataset,
        metadata,
        output_dir,
        nb_threads=4
    ):
        """
        """
        self.storage_config = storage_config
        self.load_gen_config = load_gen_config
        self.output_dir = output_dir
        self.metadata = metadata
        self.nb_threads = nb_threads

        self.ghz_instances = tuple(
                GhzRunner(params=load_gen_config.copy(), output_dir=self.output_dir) for i in range(0, nb_threads)
        )

        self.dataset_gen = InputGenerator(
            input_dataset.get("filename"),
            input_dataset.get("max_size")
        )

        if self.storage_config.get("type") == "s3":
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
        ""
        ""

        print(f"Attempting to upload object with metadata: {metadata}")
        path = self.s3_result_path()
        s3_json_obj_name = "{}-multiplexed-ghz-results.json".format(str(uuid.uuid4()))
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

    def run_tests(self, save_output=True):
        ""
        ""
        print(f"Running multiplexed test with save_output: {save_output}")

        # queue of instances to actually run.
        for ghz_instance in self.ghz_instances:
            scrambled = self.dataset_gen.get_input_array().copy()
            random.shuffle(scrambled)
            ghz_instance.set_input(scrambled)
            print(f"Prepared ghz instance UUID {ghz_instance.uuid} with input \n {ghz_instance.input}")

        with ThreadPoolExecutor(max_workers=self.nb_threads) as executor:
            for instance in self.ghz_instances:
                executor.submit(instance.run)

        self.output_obj = []
        for ghz_instance in self.ghz_instances:
            test_metadata = instance.get_metadata()
            output_obj = instance.get_output()

            # Insert metadata into test_metadata and output_obj
            test_metadata.update(self.metadata)
            output_obj.update(self.metadata)

            start_time = test_metadata.get("start_time")
            self.output_obj.append(output_obj)

        test_metadata["threads"] = str(self.nb_threads)

        if save_output:
            self.upload_to_s3(self.output_obj, test_metadata)
        else:
            super()._json_dump(output_obj, f"{self.output_dir}/ghz-test-{start_time}.json")

    def run(self):
        """Used to be more than this with warmup.
        """
        save_to_s3 = (self.storage_config.get("type") == "s3")
        self.run_tests(save_output=save_to_s3)


class ExperimentRunner(Base):
    """
    """

    def __init__(
        self,
        storage_config,
        load_gen_config,
        input_dataset,
        metadata,
        output_dir,
        warmup
    ):
        """
        """
        self.storage_config = storage_config
        self.load_gen_config = load_gen_config
        self.metadata = metadata
        self.output_dir = output_dir
        self.warmup = warmup

        self.ghz_instance = GhzRunner(
            params=self.load_gen_config.copy(),
            output_dir = self.output_dir
        )

        self.dataset_gen = InputGenerator(
            input_dataset.get("filename"),
            input_dataset.get("max_size")
        )
        if self.storage_config.get("type") == "s3":
            self.storage = S3Storage(
                region=self.storage_config.get("s3_region"),
                bucket=self.storage_config.get("s3_bucket")
            )

    def s3_result_path(self):
        """
        Temporary hack for our planned file structure in S3.
        This path should probably depend on the config / param input to the experiment.
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
            #time.sleep(15) # Sleep to show a break in CPU/GPU utilization metrics between runs

            self.ghz_instance.set_input(query.get("input"))
            self.ghz_instance.run()

            test_metadata = self.ghz_instance.get_metadata()
            output_obj = self.ghz_instance.get_output()

            # Insert metadata metadata into test_metadata and output_obj
            test_metadata.update(self.metadata)
            output_obj.update(self.metadata)
            
            start_time = test_metadata.get("start_time")
            super()._json_dump(output_obj, f"{self.output_dir}/ghz-test-{start_time}.json")
           
            if save_output:
                self.upload_to_s3(output_obj, test_metadata)

    def run(self):
        """
        """
        dataset = self.dataset_gen.get_dataset()
        if self.warmup:
            save_concurrency = self.ghz_instance.concurrency
            save_requests = self.ghz_instance.requests
            # fill the queues but avoid overload errors 
            self.ghz_instance.concurrency = 4*self.ghz_instance.concurrency
            self.ghz_instance.requests = 200*save_concurrency

            print("############ DOING WARMUP RUNS ##############")
            # Warmup with only first entry in dataset 
            self.run_tests(dataset[1:2], save_output=False)
            self.ghz_instance.concurrency = save_concurrency
            self.ghz_instance.requests = save_requests
        
        print("############ WARMUP PHASE COMPLETE ##############")
        print("############  RUNNING LOAD TESTS   ##############")
        save_to_s3 = (self.storage_config.get("type") == "s3")
        self.run_tests(dataset, save_output=save_to_s3)
        

def run_multiplexed(config):
    threads = config.get_threads()
    load_gen_config = config.get_load_gen_config()
    concurrency_per_thread = load_gen_config.get("concurrency")
    total_conc = threads * concurrency_per_thread
    print(f"Parallel experiment with {threads} threads and  {concurrency_per_thread} concurrency, for a total concurrency of {total_conc}")
    test = ParallelExperimentRunner(
        storage_config=config.get_storage_config(),
        load_gen_config=load_gen_config,
        input_dataset=config.get_input_dataset(),
        output_dir = config.get_output_dir(),
        metadata=config.get_metadata(),
        nb_threads=threads
    )
    test.run()

def run_one_input_at_a_time(config):
    test = ExperimentRunner(
        storage_config=config.get_storage_config(),
        load_gen_config=config.get_load_gen_config(),
        input_dataset=config.get_input_dataset(),
        output_dir = config.get_output_dir(),
        warmup=config.get_warmup(),
        metadata=config.get_metadata(),
    )
    test.run()


def main(args):
    """
    CLI.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="increase output verbosity")
    parser.add_argument("-c", "--config", action="store", default="config.yaml",
                        help="config YAML file name")
    parser.add_argument("--ghz", action="store_true",
                        help="use ghz")
    parser.add_argument("--experiment", action="store_true", default=True,
                        help="Run load test experiment based on config file in ./config.yaml or $CONFIG_PATH/$CONFIG_FILENAME")
    parser.add_argument("--parallel_experiment", action="store_true",
                        help="Deprecated. Set load_generator.multiplexed to True in the config file.")
    args = parser.parse_args(args)
    config = Config(args.config)
    if args.verbose:
        print(config.get_complete_config())
    if args.experiment:
        if config.multiplexed:
            run_multiplexed(config)
        else:
            run_one_input_at_a_time(config)

    if args.parallel_experiment:
        print("warning: deprecated. The parallel experiment option is deprecated and will be removed. Set load_generator.multiplexed to True in the config file.")
        run_multiplexed(config)


if __name__ == "__main__":
    main(sys.argv[1:])

