
DESCRIPTION

llm-load-test is a frontend/wrapper for the [ghz](https://github.com/bojand/ghz)
[gRPC](https://grpc.io/) benchmarking and load testing tool.


PURPOSE

Currently, the only supported gRPC endpoint and inference model
are [Model Mesh](https://github.com/opendatahub-io/modelmesh) as provided by
[Open Data Hub](https://opendatahub.io/) and the
[Ansible Wisdom](https://www.redhat.com/en/engage/project-wisdom)
model. 


PREREQUISITES

- a supported gRPC endpoint
- ghz in the path
- proto files
- an S3 bucket.


HOWTO

- create a Python venv and install all the requirements
- fill config.json with appropriate values
- see your S3 bucket afterwards.


BACKLOG / Wishlist

- The ability to run different queries at the same time
- Capture the model's output and output token length 
- CI
- the various demoes probably don't work anymore
