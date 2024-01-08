import json
import random

dataset_seed = 1337
class Dataset:
    def __init__(self, file, max_queries, max_input_tokens, max_output_tokens):
        self.dataset_list = [query for query in read_jsonlines(file, max_queries=max_queries, max_input_tokens=max_input_tokens, max_output_tokens=max_output_tokens)]
        random.Random(dataset_seed).shuffle(self.dataset_list)
        self.index = 0

    def get_next_n_queries(self, n):
        max_index=len(self.dataset_list)
        next_n_indices = [i % max_index for i in range(self.index, self.index+n)] 
        self.index = (self.index + n) % max_index
        return [self.dataset_list[i] for i in next_n_indices]


def read_jsonlines(filename, max_queries=1000, max_input_tokens=1024, max_output_tokens=1024):
    with open(filename, 'r', encoding='utf-8') as file:
        next(file) #First line for metadata
        lines = 0
        for line in file:
            # Load each line as a JSON object
            try:
                json_object = json.loads(line.strip())
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                continue
            try:
                input_tokens = json_object.get('tok_input_length')
                input_data = json_object.get('input')
                output_tokens = input_data.get('min_new_tokens')
            except KeyError as e:
                print(f"Unexpected format in input dataset, KeyError: {e}")
            if output_tokens < max_output_tokens and input_tokens < max_input_tokens:
                lines = lines + 1
                input_data["input_tokens"] = input_tokens
                yield input_data
                if lines >= max_queries:
                    break

