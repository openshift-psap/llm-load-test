import json
import logging
import random

dataset_seed = 1337


class Dataset:
    def __init__(self,
                 file,
                 model_name="",
                 max_queries=3000,
                 min_input_tokens=0,
                 max_input_tokens=16000,
                 max_output_tokens=4096,
                 max_sequence_tokens=32000
                 ):
        logging.info("Initializing dataset with %s", locals())
        self.dataset_list = [input for input in
            initialize_dataset(
                file,
                model_name=model_name,
                max_queries=max_queries,
                min_input_tokens=min_input_tokens,
                max_input_tokens=max_input_tokens,
                max_output_tokens=max_output_tokens,
                max_sequence_tokens=max_sequence_tokens,
            )
        ]
        self.index = 0

    def get_next_n_queries(self, n):
        max_index = len(self.dataset_list)
        next_n_indices = [i % max_index for i in range(self.index, self.index + n)]
        self.index = (self.index + n) % max_index
        return [self.dataset_list[i] for i in next_n_indices]


def initialize_dataset(
    filename,
    model_name="",
    max_queries=3000,
    min_input_tokens=0,
    max_input_tokens=16000,
    max_output_tokens=4096,
    max_sequence_tokens=32000
):
    
    prompt_format = get_format_string(model_name)
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
                sequence_tokens = input_tokens + output_tokens
            except KeyError as e:
                logging.error(
                    "Unexpected format in dataset file %s, KeyError: %s, \n %s", filename, e, json_object
                )
                continue
                # TODO exit or just skip here?
            if (output_tokens < max_output_tokens
                and input_tokens < max_input_tokens
                and input_tokens > min_input_tokens
                and sequence_tokens < max_sequence_tokens):
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

def get_format_string(model_name):
    known_system_prompts = {
        "llama": "<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n{prompt} [/INST]",
        "flan": "Question: {prompt}\n\nAnswer:",
        "gpt-neox": "{system_prompt}\n\n{prompt}",
        "starcoder": "input: \n\n{prompt} \n\noutput:",
    }

    for name, fmt_str in known_system_prompts.items():
        if name in model_name:
            logging.info("Using %s prompt format, model_name: %s", name, model_name)
            return fmt_str

    logging.info("Using default prompt format model_name: %s", model_name)
    return "{system_prompt}\n\n{prompt}"