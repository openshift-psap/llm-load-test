"""User definition."""

import logging
import queue
import time


class User:
    """Define a user."""

    def __init__(
        self,
        user_id,
        dataset_q,
        stop_q,
        results_pipe,
        plugin,
        logger_q,
        log_level,
        run_duration,
    ):
        """Initialize object."""
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
        self.run_duration = run_duration

    def make_request(self, test_end_time=0):
        """Make a request."""
        try:
            query = self.dataset_q.get(timeout=2)
        except queue.Empty:
            # if timeout passes, queue.Empty will be thrown
            # User should continue to poll for inputs
            return None
        except ValueError:
            self.logger.warn("dataset q does not exist!")
            return None

        self.logger.info("User %s making request", self.user_id)
        result = self.plugin.request_func(query, self.user_id, test_end_time)
        return result

    def _init_user_process_logging(self):
        """Init logging."""
        qh = logging.handlers.QueueHandler(self.logger_q)
        root = logging.getLogger()
        root.setLevel(self.log_level)
        root.handlers.clear()
        root.addHandler(qh)

        self.logger = logging.getLogger("user")
        return logging.getLogger("user")

    def run_user_process(self):
        """Run a process."""
        self._init_user_process_logging()

        test_end_time = time.time() + self.run_duration
        while self.stop_q.empty():
            result = self.make_request(test_end_time)
            # make_request will return None after 2 seconds if dataset_q is empty
            # to ensure that users don't get stuck waiting for requests indefinitely
            if result is not None:
                self.results_list.append(result)

        self.results_pipe.send(self.results_list)

        time.sleep(4)
        self.logger.info("User %s done", self.user_id)
