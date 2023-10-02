# pylint: disable=too-few-public-methods,empty-docstring,too-many-arguments

"""
"""

import logging

import boto3
import botocore.exceptions


class S3Storage():
    """
    """

    def __init__(self, region, bucket, access_key=None, secret_key=None, s3_endpoint=None):
        """
        """
        try:
            session = boto3.Session(profile_name='default')
            self.region = region
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

