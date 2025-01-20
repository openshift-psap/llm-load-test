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
pip install -r requirements.txt
python synthetic_datagen.py --model facebook/opt-125m --dataset_name sample --num_samples 100 --distribution {normal, uniform, equal} <DISTRIBUTION SPECIFIC PARAMETERS> 

```

### Normal Distribution
```
--input_mean 1000 --input_sd 30 --output_mean 1000 --output_sd 30
```
- A standard deviation(sd) value of at least 30 recommended to avoid request synchronization

### Uniform Distribution
```
--input_min 1000 --input_max 1200 --output_min 200 --output_max 320
```

### Equal Length Sequences
```
--input_len 1000 --input_max 1200 --output_min 200 --output_max 320
```

The script can also be pointed to local models following a huggingface model structure. 