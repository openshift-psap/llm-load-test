# pylint: disable=too-few-public-methods,empty-docstring,too-many-arguments

"""
"""

import time

from input_generator import InputGenerator
from s3storage import S3Storage


class DatasetDemo():
    """
    Demo for the dataset generator
    """

    def __init__(self):
        print("#################")
        test_query_generator = InputGenerator(
            "sorted_dataset.json", max_size=4)
        print("Dataset version: {}".format(
            test_query_generator.dataset_version))
        token_sizes = [x["op_token_count"]
                       for x in test_query_generator.dataset]
        print("Token sizes of all entries in the dataset:  {}".format(token_sizes))
        print("#################")
        print("Here are the next 5 queries to be used (round robin):")
        for _ in range(5):
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
            # access_key="myuser",
            # secret_key="25980928",
            # s3_endpoint="http://localhost:9000",
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
