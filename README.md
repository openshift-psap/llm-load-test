# llm-load-test

This tool is designed to load test large language models running in different runtimes / behind different APIs.

## Requirements

- Python 3.10 or newer

## Usage

**Installation**:

```
python3 -m venv venv
source venv/bin/activate
pip install .
```

**Running the Tool**:

- Change/Update the configuration file `config.yaml` as needed for your test. Look at the appropriate plugin for the configuration options.
- Run the tool with the following command: `python load_test.py -c config.yaml`

**Command Line Options**:

```
usage: load-test [-h] [-c CONFIG] [-log {warn,warning,info,debug}]

options:
  -h, --help            show this help message and exit
  -c, --config CONFIG   config YAML file name
  -log, --log_level {warn,warning,info,debug}
                        Provide logging level. Example --log_level debug, default=warning
```

## Configuration Options

The tool's behavior can be customized using a YAML configuration file. Take a look at `config.yaml` for an example. More documentation on this should be added in the future.

**Results**:
The tool will produce a results summary logged to stdout, and detailed test results along with its summary in json format in `outpu/output.json`.
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
    "tpot": {
      "min": 27.586110933559148,
      "max": 40.88755629279397,
      "median": 38.5650954713167,
      "mean": 36.610498448261545,
      "percentile_80": 39.64898690651721,
      "percentile_90": 40.02262306964303,
      "percentile_95": 40.630858620320716,
      "percentile_99": 40.88648535348555
    },
    "ttft": {
      "min": 203.82094383239746,
      "max": 1181.5788745880127,
      "median": 431.65814876556396,
      "mean": 473.4579073755365,
      "percentile_80": 683.5222721099855,
      "percentile_90": 764.7189617156984,
      "percentile_95": 832.2112917900082,
      "percentile_99": 1133.0137634277346
    },
    "tt_ack": {
      "min": 153.1047821044922,
      "max": 526.094913482666,
      "median": 162.1863842010498,
      "mean": 185.01624935551695,
      "percentile_80": 205.64818382263184,
      "percentile_90": 209.48517322540283,
      "percentile_95": 265.4685258865356,
      "percentile_99": 439.9926090240484
    },
    "response_time": {
      "min": 980.7870388031006,
      "max": 6064.596891403198,
      "median": 5120.97430229187,
      "mean": 4604.336657022175,
      "percentile_80": 5499.248218536377,
      "percentile_90": 5687.238049507141,
      "percentile_95": 5813.571393489838,
      "percentile_99": 5972.328190803529
    },
    "output_tokens": {
      "min": 21,
      "max": 128,
      "median": 128.0,
      "mean": 114.0,
      "percentile_80": 128.0,
      "percentile_90": 128.0,
      "percentile_95": 128.0,
      "percentile_99": 128.0
    },
    "input_tokens": {
      "min": 59,
      "max": 990,
      "median": 401.0,
      "mean": 434.5,
      "percentile_80": 734.8000000000001,
      "percentile_90": 843.4000000000005,
      "percentile_95": 955.4,
      "percentile_99": 982.23
    },
    "throughput": 185.12628986046127,
    "total_requests": 38,
    "total_failures": 0,
    "failure_rate": 0.0
  }
}
```

## Contributing

Contributions to this tool are welcome!
