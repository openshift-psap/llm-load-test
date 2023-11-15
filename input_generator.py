# pylint: disable=too-few-public-methods,empty-docstring,too-many-arguments

"""
"""

import numpy as np
import random
import logging

from base import Base


class InputGenerator(Base):
    """
    Parses a json input file

    If max_size is defined, dataset will be a subset of max_size which are
    equally spaced from the full sorted dataset.
    """

    def __init__(self, file, max_size):
        """
        """
        logging.info(f"Loading dataset file {file}")
        input_json = self._json_load(file)

        input_dataset = input_json["dataset"]

        if max_size is not None:
            self.dataset = self._get_even_subset(input_dataset, max_size)
        else:
            self.dataset = input_dataset

        self.dataset_version = input_json["metadata"]["version"]
        self.next_query = 0

    def get_next_query(self):
        """
        Get the next query. Iterates through the dataset in a round-robin.
        """
        ret_idx = self.next_query
        self.next_query = (self.next_query+1) % len(self.dataset)
        return self.dataset[ret_idx]

    def get_dataset(self):
        """
        Access current dataset
        """
        return self.dataset
    
    def get_input_array(self):
        ret = []
        for data_object in self.dataset:
            ret.append(data_object.get("input"))
        
        return [data_object.get("input") for data_object in self.dataset]
            

    def _get_even_subset(self, input_dataset, max_size):
        """
        Returns a subset of n queries, equally spaced from input_dataset

        This is useful if the dataset is sorted in some way and you want an even distribution.
        For example, if it is sorted by input length and you want to test different input sizes.
        """
        dataset_len= len(input_dataset)
        indices = np.round(np.linspace(0, dataset_len - 1, max_size)).astype(int)
        logging.info(f"Using subset of dataset file with indices: {indices}")
        return ([input_dataset[i] for i in indices])

    def _get_random_subset(self, max_size):
        """
        Returns a random subset of n queries of this input generators dataset
        """
        ret = self.dataset.copy()
        random.shuffle(ret)
        return (ret[0:max_size])

