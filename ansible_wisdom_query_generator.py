# pylint: disable=too-few-public-methods,empty-docstring,too-many-arguments

"""
"""

import numpy as np

from base import Base


class AnsibleWisdomQueryGenerator(Base):
    """
    Parses an input file containing one json object per line (Gold Dataset)
    and chooses a subset of input prompts / contexts
    to be used as input to the load generator querying the model.

    If max_size is defined, dataset will be a subset of max_size which are
    equally spaced from the full sorted dataset.
    """

    def __init__(self, file, max_size):
        """
        """
        input_json = self._json_load(file)
        self.dataset = input_json["dataset"]
        if max_size is not None:
            self.dataset = self._get_subset(max_size)

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

    def _get_subset(self, max_size):
        """
        Returns a subset of n queries, equally spaced from current self.queries
        """
        query_list_length = len(self.dataset)
        indices = np.round(np.linspace(
            0, query_list_length - 1, max_size)).astype(int)
        return ([self.dataset[i] for i in indices])
