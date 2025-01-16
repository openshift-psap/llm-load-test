"""Dataset class."""
import json
import logging
import random

dataset_seed = 1337


class Dataset:
    """Dataset class."""

    def __init__(self,
                 file,
                 max_queries=3000,
                 min_input_tokens=0,
                 max_input_tokens=16000,
                 min_output_tokens=0,
                 max_output_tokens=4096,
                 max_sequence_tokens=32000,
                 custom_prompt_format=None
                 ):
        """Init method."""
        logging.info("Initializing dataset with %s", locals())
        self.dataset_list = [input for input in
                             initialize_dataset(file,
                                                max_queries=max_queries,
                                                min_input_tokens=min_input_tokens,
                                                max_input_tokens=max_input_tokens,
                                                min_output_tokens=min_output_tokens,
                                                max_output_tokens=max_output_tokens,
                                                max_sequence_tokens=max_sequence_tokens,
                                                custom_prompt_format=custom_prompt_format
                                                )
                             ]
        if len(self.dataset_list) < 4:
            logging.warning("Total dataset is %s elements, check filters!", len(self.dataset_list))
        self.index = 0

    def get_next_n_queries(self, n):
        """Get the N next queries."""
        max_index = len(self.dataset_list)
        next_n_indices = [i % max_index for i in range(self.index, self.index + n)]
        self.index = (self.index + n) % max_index
        return [self.dataset_list[i] for i in next_n_indices]


def initialize_dataset(
    filename,
    max_queries=3000,
    min_input_tokens=0,
    max_input_tokens=16000,
    min_output_tokens=0,
    max_output_tokens=4096,
    max_sequence_tokens=32000,
    custom_prompt_format=None
):
    """Initialize the dataset."""
    prompt_format = "{prompt}" if not custom_prompt_format else custom_prompt_format
    if '{system_prompt}' not in prompt_format and '{prompt}' not in prompt_format:
        logging.warning("Prompt template does not contain any of ['{system_prompt}', '{prompt}']")

    with open(filename, "r", encoding="utf-8") as file:
        total_queries = 0

        # [1:] to skip the first line, it contains metadata
        lines = file.readlines()[1:]
        random.Random(dataset_seed).shuffle(lines)

        for line in lines:
            # Load each line as a JSON object
            try:
                json_object = json.loads(line.strip())
            except json.JSONDecodeError as e:
                logging.error("Error decoding JSON in file %s %s", filename, e)
                continue
            try:
                input_tokens = int(json_object["tok_input_length"])
                output_tokens = int(json_object["tok_output_length"])
                prompt = json_object["question"]
                system_prompt = json_object["system_prompt"]
                input_id = json_object["index"]
            except KeyError as e:
                logging.error(
                    "Unexpected format in dataset file %s, KeyError: %s, \n %s", filename, e, json_object
                )
                continue
                # TODO exit or just skip here?
            token_lengths_ok = filter_token_lengths(input_tokens,
                                                    output_tokens,
                                                    min_input_tokens,
                                                    max_input_tokens,
                                                    min_output_tokens,
                                                    max_output_tokens,
                                                    max_sequence_tokens)
            if (token_lengths_ok):
                input_data = {
                    "text": prompt_format.format(prompt=prompt,
                                                 system_prompt=system_prompt),
                    "input_id": input_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                }
                total_queries = total_queries + 1
                yield input_data
                if total_queries >= max_queries:
                    break


def filter_token_lengths(input_tokens,
                         output_tokens,
                         min_input_tokens,
                         max_input_tokens,
                         min_output_tokens,
                         max_output_tokens,
                         max_sequence_tokens):
    """Filter the tokens by length."""
    sequence_tokens = input_tokens + output_tokens
    return (output_tokens > min_output_tokens
            and output_tokens < max_output_tokens
            and input_tokens < max_input_tokens
            and input_tokens > min_input_tokens
            and sequence_tokens < max_sequence_tokens)
