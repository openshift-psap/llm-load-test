#!/bin/bash

# FIXMEs
# * extract ROOTUSER and ROOTPASSWORD
# * extract myuser/25980928

ROOTUSER="ROOTUSER"
ROOTPASSWORD="ROOTPASSWORD"

BUCKET_NAME="mybucket"
REGION="myregion"

# consoleAdmin rights are needed to create buckets
KEY_ID=$ROOTUSER
SECRET_ACCESS_KEY=$ROOTPASSWORD

# Create the MinIO datadir
mkdir -p ~/minio/data

# Start the MinIO server
# 9000 => S3 port
# 9090 => admin (web) port
podman run \
   -d \
   -p 9000:9000 \
   -p 9090:9090 \
   -v ~/minio/data:/data:z \
   -e "MINIO_ROOT_USER=$ROOTUSER" \
   -e "MINIO_ROOT_PASSWORD=$ROOTPASSWORD" \
   quay.io/minio/minio server /data --console-address ":9090"

# Download the MC CLI. Required to create users. 
wget -nc https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc

# wait until minio is ready
sleep 5

# setup the MC CLI
./mc alias set myminio http://localhost:9000 $ROOTUSER $ROOTPASSWORD

# Create a user for later use
./mc admin user add myminio myuser 25980928
./mc admin policy set myminio readwrite user=myuser

# Create a bucket
export BUCKET_NAME="mybucket"
export REGION="myregion"
export KEY_ID="ROOTUSER"
export SECRET_ACCESS_KEY="ROOTPASSWORD"

python - << EOF

import boto3
import logging
import os

from botocore.exceptions import ClientError

def create_bucket(bucket_name=os.getenv("BUCKET_NAME"), region=os.getenv("REGION")):
    """
    :param bucket_name: Bucket to create
    :param region: String region to create bucket in, e.g., 'us-west-2'
    :return: True if bucket created, else False
    """

    try:
        s3_client = boto3.client(
           service_name = 's3',
           region_name = region,
	   aws_access_key_id=os.getenv("KEY_ID"),
	   aws_secret_access_key=os.getenv("SECRET_ACCESS_KEY"),
           endpoint_url='http://localhost:9000'
        )
        location = {'LocationConstraint': region}
        s3_client.create_bucket(Bucket=bucket_name,
                                CreateBucketConfiguration=location)
    except ClientError as e:
        logging.error(e)
        return False
    return True

if __name__ == "__main__":
    create_bucket()

EOF

