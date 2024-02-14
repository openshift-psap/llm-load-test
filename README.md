# llm-load-test

This tool is designed to load test large language models running in different runtimes / behind different APIs. 

## Requirements

- Python 3.9 or newer

## Usage

**Running the Tool**:
```
usage: load_test.py [-h] [-c CONFIG] [-log {warn,warning,info,debug}]

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        config YAML file name
  -log {warn,warning,info,debug}, --log_level {warn,warning,info,debug}
                        Provide logging level. Example --log_level debug, default=warning
```

## Configuration Options

The tool's behavior can be customized using a YAML configuration file. Take a look at `config.yaml` for an example. More documentation on this should be added in the future.


**Results**:
The tool will produce a results summary logged to stdout, and detailed test results in json format.
The json output will have an array of results with one element per request sent during the test. For example, here is the detailed information for one request in the array:

```
{
    "start": 1705614329.536056, 
    "end": 1705614332.6319733, 
    "tt_ack": 77.5759220123291, 
    "ttft": 113.14225196838379, 
    "tpot": 13.47473795924868, 
    "response_time": 3.095917224884033, 
    "output_tokens": 225, 
    "worker_id": 0, 
    "input_tokens": 129, 
    "response_string": "...", 
    "input_string": "..."}
```


## Contributing

Contributions to this tool are welcome! 

