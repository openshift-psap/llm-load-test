
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


REPORTING ISSUES

- Please use GitHub issues
- Please include as much information as possible for us to
  understand and if at all possible reproduce the issue.


CONTRIBUTING

- Open an issue before opening a PR and reference the issue in
  your PR
- Make sure your contribution passes the linter
- Add comments / documentation
- Include tests in your contribution

