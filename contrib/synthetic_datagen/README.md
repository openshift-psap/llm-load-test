# Synthetic Data Generation for llm-load-test

This utility generates synthetic datasets compatible with [llm-load-test](https://github.com/openshift-psap/llm-load-test) - The standard llm serving performance testing tool for PSAP team @ Redhat.

This is required in certain synthetic scenarios where the input/output lengths are artificially constrained to a specified length and distribution.

## Setup

```
pip install -r contrib/synthetic_datagen/requirements.txt
```

## Usage

**Note:** There is a known request synchronization issue that can cause sub-optimal performance when using a dataset with no sequence to sequence variation in input/output lengths.

```
usage: synthetic_datagen.py [-h] -m MODEL -o FILE [-i FILE [FILE ...]] -c COUNT (--input-equal LEN |
                            --input-normal MEAN SD | --input-uniform MIN MAX) (--output-equal LEN |
                            --output-normal MEAN SD | --output-uniform MIN MAX)

Create Synthetic Datasets for use with llm-load-test

options:
  -h, --help            show this help message and exit
  -m, --model MODEL     HuggingFace model name or path to model
  -o, --dataset FILE    path to output file
  -i, --corpus FILE [FILE ...]
                        path to corpus file(s)
  -c, --samples COUNT   number of samples to generate
  --input-equal LEN
  --input-normal MEAN SD
  --input-uniform MIN MAX
  --output-equal LEN
  --output-normal MEAN SD
  --output-uniform MIN MAX
```

### Normal Distribution

```
--input-normal 1000 30 --output-normal 1000 30
```

- A standard deviation(sd) value of at least 30 recommended to avoid request synchronization

### Uniform Distribution

```
--input-uniform 1000 1200 --output-uniform 200 320
```

### Equal Length Sequences

```
--input-equal 1000 --output-equal 1200
```

The script can also be pointed to local models following a HuggingFace model structure. 
