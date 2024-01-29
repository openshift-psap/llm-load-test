import logging
import time

class User:
    def __init__(self, user_id, dataset_q, stop_q, results_pipe, plugin, logger_q, log_level):
        self.user_id = user_id
        self.plugin = plugin
        self.dataset_q = dataset_q
        self.stop_q = stop_q
        self.results_list = []
        self.results_pipe = results_pipe
        self.logger_q = logger_q
        self.log_level = log_level
        # Must get reset in user process to use the logger created in _init_user_process_logging 
        self.logger = logging.getLogger("user")

    def make_request(self):
        query = self.dataset_q.get()
        self.logger.info("User %s making request", self.user_id)
        result = self.plugin.request_func(query, self.user_id)
        return result

    def _init_user_process_logging(self):
        qh = logging.handlers.QueueHandler(self.logger_q)
        root = logging.getLogger()
        root.setLevel(self.log_level)
        root.handlers.clear()
        root.addHandler(qh)

        self.logger  = logging.getLogger("user")
        return logging.getLogger("user")

    def run_user_process(self):
        self._init_user_process_logging()

        while self.stop_q.empty():
            result = self.make_request()
            self.results_list.append(result)

        self.results_pipe.send(self.results_list)

        time.sleep(4)
        self.logger.info("User %s done", self.user_id)
