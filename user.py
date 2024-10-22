"""User definition."""

import logging
import queue
import time


class User:
    """Define a user."""

    def __init__(
        self,
        user_id,
        request_q,
        stop_q,
        results_pipe,
        plugin,
        logger_q,
        log_level,
        run_duration,
        rate_limited,
    ):
        """Initialize object."""
        self.user_id = user_id
        self.plugin = plugin
        self.request_q = request_q
        self.stop_q = stop_q
        self.results_list = []
        self.results_pipe = results_pipe
        self.logger_q = logger_q
        self.log_level = log_level
        # Must get reset in user process to use the logger created in _init_user_process_logging
        self.logger = logging.getLogger("user")
        self.run_duration = run_duration
        self.rate_limited = rate_limited

    def make_request(self, query, test_end_time=0, req_schedule_time=None):
        """Make a request."""

        self.logger.info("User %s making request", self.user_id)
        result = self.plugin.request_func(query, self.user_id, test_end_time)

        if req_schedule_time:
            result.scheduled_start_time = req_schedule_time

        result.calculate_results()

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

    def _user_loop(self, test_end_time):
        while self.stop_q.empty():
            result = self.make_request(test_end_time)
            if result is not None:
                self.results_list.append(result)

    def _rate_limited_user_loop(self, test_end_time):
        while self.stop_q.empty():
            try:
                req_schedule_time, query = self.request_q.get(timeout=5)
                if not self.stop_q.empty():
                    break
            except queue.Empty:
                # if timeout passes, queue.Empty will be thrown
                # User should check if stop_q has been set, else poll again
                # self.debug.info("User waiting for a request to be scheduled")
                continue

            result = self.make_request(query, test_end_time, req_schedule_time=req_schedule_time)

            if result is not None:
                self.results_list.append(result)
            else:
                self.logger.info("Unexpected None result from User.make_request()")


    def run_user_process(self):
        """Run a process."""
        self._init_user_process_logging()

        # Waits for all processes to actually be started
        while not self.rate_limited and self.request_q.empty():
            time.sleep(0.1)

        test_end_time = time.time() + self.run_duration
        self.logger.info("User %s starting request loop", self.user_id)

        if self.rate_limited:
            self._rate_limited_user_loop(test_end_time)
        else:
            self._user_loop(test_end_time)

        self.results_pipe.send(self.results_list)

        time.sleep(4)
        self.logger.info("User %s done", self.user_id)
