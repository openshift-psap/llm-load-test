#import logging

class User:
    def __init__(self, user_id, dataset_q, results_pipe, plugin):
        self.user_id = user_id
        self.plugin = plugin
        self.dataset_q = dataset_q
        self.results_list = []
        self.results_pipe = results_pipe

    def make_request(self):
        query = self.dataset_q.get()
        #logging.info(f"User {self.user_id} making request idx {idx}: {query}")
        print(f"User {self.user_id} making request {query}")
        result = self.plugin.request_func(query, self.user_id)
        return result


