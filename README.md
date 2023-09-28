# llm-load-test

This tool is designed to load test large language models via gRPC. It uses [ghz](https://github.com/bojand/ghz/) under the hood, and supports all ghz options.

## Requirements

- Python 3.x
- `boto3` Python library (for S3 interactions)

## Usage

1. **Running the Tool**:
    ```
    python load_test.py --config <config_file_path>
    ```

    - `-v, --verbose`: Enables verbose (debug-level) logging.
    - `-c, --config`: Specifies the path to the configuration file (default is `config.yaml`).

## Configuration Options

The tool's behavior can be customized using a YAML configuration file. Here's a breakdown of the available sections and their meanings:

- **`output_dir`**: Directory where temporary output files will be saved.
- **`warmup`**: Indicates whether a warmup phase should be executed before the actual load test.
- **`storage`**:
  - `type`: Type of storage (`local` or `s3`).
  - `s3_params`: (If `type` is `s3`) Parameters for S3 storage.
    - `s3_host`: S3 host.
    - `s3_use_https`: Use HTTPS for S3 (true/false).
    - `s3_access_key`: Access key for S3.
    - `s3_secret_key`: Secret key for S3.
    - `s3_bucket`: S3 bucket name.
    - `s3_result_path`: Path in the S3 bucket to store results.
    - `s3_region`: S3 region.
- **`load_generator`**:
  - `type`: Type of load generator (e.g., `ghz`).
  - `ghz_params`: Parameters specific to the `ghz` load generator.
    - `host`: Host address.
    - `skipTLS`: Skip TLS verification (true/false).
    - `proto`: Path to the `.proto` file.
    - `call`: gRPC call.
    - `metadata`: Additional headers attached to the gRPC request.
    - `concurrency`: Concurrency level.
    - `total`: Total number of requests (ignored).
    - `duration`: Duration of the test.
    - `timeout`: Request timeout.
  - `multiplexed`: Indicates if multiplexed testing should be used.
  - `threads`: Number of threads.
  - `input_dataset`: 
    - `filename`: Name of the input dataset file.
    - `max_size`: Maximum size of the dataset to use.
- **`metadata`**: Optional metadata that you want inserted into the output `.json` and/or attached to the S3 objects. For example:
  - `runtime`
  - `model`
  - `gpu_type`
  - `gpu_count`
  - `shards`
  - `model replicas`


3. **Results**:
    The tool will produce test results as output by `ghz`. 

    In the case of multiplexed tests, all concurrent ghz instances output will be concatenated into one json file. Some additional files are added to the output directory for debugging purposes, including the ghz config files and the individual ghz output 

## Contributing

Contributions to this tool are welcome! 

