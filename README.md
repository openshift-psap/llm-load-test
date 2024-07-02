# llm-load-test

This tool is designed to load test large language models running in different runtimes / behind different APIs. 

## Requirements

- Python 3.9 or newer

## Usage


**Generate Dataset**:

```sh  
python generate_random_text_dataset.py --tok_input_length 10 --tok_output_length 50 --N 100 --output_file random_text_dataset.jsonl  
```  
  
- `--tok_input_length`: The length of the input.  
- `--tok_output_length`: The length of the output.  
- `--N`: The number of samples to generate.  
- `--output_file`: The name of the output file (default is `random_text_dataset.jsonl`).  
   

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
The tool will produce a results summary logged to stdout, and detailed test results along with its summary in json format.
The json output will have following:
1. Array of results with one element per request sent during the test. 
2. Detailed summary report of the run.
3. All the config metadata related to run 

For example:

```
"results": [
...
    {
      "user_id": 7,
      "input_text": "...",
      "input_tokens": 940,
      "output_text": "...",
      "output_tokens": 128,
      "start_time": 1708535304.5261629,
      "ack_time": 1708535304.691414,
      "first_token_time": 1708535304.95455,
      "end_time": 1708535309.094971,
      "response_time": 4568.808078765869,
      "tt_ack": 165.2512550354004,
      "ttft": 428.3871650695801,
      "tpot": 32.60173947792354,
      "error_code": null,
      "error_text": null
    }
  ],
  "config": {
...
    "load_options": {
      "type": "constant",
      "concurrency": 8,
      "duration": 20
...
  },
  "summary": {
    "tpot": { #time per ouput_token
      "min": 0.010512285232543946,
      "max": 0.018693844079971312,
      "median": 0.01216195583343506,
      "mean": 0.012808671338217597,
      "percentile_80": 0.012455177783966065,
      "percentile_90": 0.01592913103103638,
      "percentile_95": 0.017840550780296324,
      "percentile_99": 0.018523185420036312
    },
    "ttft": { #time to first token
      "min": 0.4043765068054199,
      "max": 0.5446293354034424,
      "median": 0.46433258056640625,
      "mean": 0.4660029411315918,
      "percentile_80": 0.51033935546875,
      "percentile_90": 0.5210948467254639,
      "percentile_95": 0.5295632600784301,
      "percentile_99": 0.54161612033844
    },
    "itl": { #input token latency
      "min": 0.008117493672586566,
      "max": 0.01664590356337964,
      "median": 0.009861880810416522,
      "mean": 0.010531313198552402,
      "percentile_80": 0.010261738599844314,
      "percentile_90": 0.013813444118403915,
      "percentile_95": 0.015781731761280615,
      "percentile_99": 0.016473069202959836
    },
    "tt_ack": { #time to ack
      "min": 0.404374361038208,
      "max": 0.544623851776123,
      "median": 0.464330792427063,
      "mean": 0.46600091457366943,
      "percentile_80": 0.5103373527526855,
      "percentile_90": 0.5210925340652466,
      "percentile_95": 0.5295597910881042,
      "percentile_99": 0.5416110396385193
    },
    "response_time": {
      "min": 2.102457046508789,
      "max": 3.7387688159942627,
      "median": 2.3843793869018555,
      "mean": 2.5091602653265,
      "percentile_80": 2.4795608520507812,
      "percentile_90": 2.992232322692871,
      "percentile_95": 3.541854977607727,
      "percentile_99": 3.6993860483169554
    },
    "output_tokens": {
      "min": 200,
      "max": 200,
      "median": 200.0,
      "mean": 200.0,
      "percentile_80": 200.0,
      "percentile_90": 200.0,
      "percentile_95": 200.0,
      "percentile_99": 200.0
    },
    "input_tokens": {
      "min": 2000,
      "max": 2000,
      "median": 2000.0,
      "mean": 2000.0,
      "percentile_80": 2000.0,
      "percentile_90": 2000.0,
      "percentile_95": 2000.0,
      "percentile_99": 2000.0
    },
    "output_tokens_throughput": 159.25729928295627,
    "input_tokens_throughput": 1592.5729928295625,
    "full_duration": 20.093270540237427,
    "total_requests": 16,
    "complete_request_per_sec": 0.7962864964147813,
    "total_failures": 0,
    "failure_rate": 0.0
  }
}
```


## Contributing

Contributions to this tool are welcome! 
