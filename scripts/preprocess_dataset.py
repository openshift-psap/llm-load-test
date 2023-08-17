# pylint: disable=too-few-public-methods,empty-docstring,too-many-arguments

"""
The gold dataset is structured as a text file where each line is a JSON object.
This file preprocess that file, turning it into a real JSON file which is
structured as follows:

{
  "metadata": { "version": "gold-dataset-version", ...}
  "dataset":
    [
      {
         "prompt": "- name: install nginx on RHEL",
         "context": "<context>",
         "input_token": 123,
         "output_tokens": 321,
         ...
      },
      ...
    ]
}

As we start using other datasets, we can create/expand a similarly structured
file. This keeps highly specific code for parsing the original text file out
of the load generator.
"""

import json


def lines_of_json_to_list_of_dicts(input_file):
    """
    """
    json_lines = []
    with open(input_file, encoding="utf-8") as ds_file:
        for line in ds_file:
            entry = json.loads(line)
            # rename input_script to context
            entry["context"] = entry.pop("input_script")
            json_lines.append(entry)
    return json_lines


def sort_list_of_dicts_by_key(dict_list, key):
    """
    """
    return sorted(dict_list, key=lambda d: d[key])


def list_of_dicts_to_json(dict_list, output_file, version):
    """
    """
    output_object = {"metadata": {"version": version}, "dataset": dict_list}
    with open(output_file, "w", encoding="utf-8") as outfile:
        # Preserve order from dict_list
        outfile.write(json.dumps(output_object, indent=2))


GOLD_DATASET_FILENAME = "awgold_v2.4.2_tasks-202300113-185050.json"
OUTPUT_FILENAME = "sorted_dataset.json"

unsorted_queries = lines_of_json_to_list_of_dicts(GOLD_DATASET_FILENAME)
sorted_queries = sort_list_of_dicts_by_key(unsorted_queries, 'op_token_count')
list_of_dicts_to_json(sorted_queries, OUTPUT_FILENAME, version=GOLD_DATASET_FILENAME)
