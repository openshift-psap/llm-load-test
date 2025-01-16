"""Main llm-load-test CLI entrypoint."""

import logging
import logging.handlers
import multiprocessing as mp
import sys
import time

from llm_load_test.user import User
from llm_load_test.dataset import Dataset

from llm_load_test import logging_utils
from llm_load_test import utils


def run_main_process(concurrency, duration, dataset, dataset_q, stop_q):
    """Run the main process."""
    logging.info("Test from main process")

    # Initialize the dataset_queue with 4*concurrency requests
    for query in dataset.get_next_n_queries(2 * concurrency):
        dataset_q.put(query)

    start_time = time.time()
    current_time = start_time
    while (current_time - start_time) < duration:
        # Keep the dataset queue full for duration
        if dataset_q.qsize() < int(0.5*concurrency + 1):
            logging.info("Adding %d entries to dataset queue", concurrency)
            for query in dataset.get_next_n_queries(concurrency):
                dataset_q.put(query)
        time.sleep(0.1)
        current_time = time.time()

    logging.info("Timer ended, stopping processes")

    # Signal users to stop sending requests
    stop_q.put(None)

    # Empty the dataset queue
    while not dataset_q.empty():
        logging.debug("Removing element from dataset_q")
        dataset_q.get()

    return


def gather_results(results_pipes):
    """Get the results."""
    # Receive all results from each processes results_pipe
    logging.debug("Receiving results from user processes")
    results_list = []
    for results_pipe in results_pipes:
        user_results = results_pipe.recv()
        results_list.extend(user_results)
    return results_list


def stop_procs(procs, dataset_q, stop_q):
    """Exit gracefully."""
    # Signal users to stop sending requests
    if stop_q.empty():
        stop_q.put(None)

    if dataset_q is not None and not dataset_q.empty():
        logging.warning("Removing more elements from dataset_q after gathering results!")
        while not dataset_q.empty():
            dataset_q.get()

    logging.debug("Calling join() on all user processes")
    for proc in procs:
        proc.join()
    logging.info("User processes terminated succesfully")

    stop_q.get()


def stop_test(logger_q, log_reader_thread, code):
    """Clean up logger thread and exit the program."""
    # Shutdown logger thread
    logger_q.put(None)
    log_reader_thread.join()

    sys.exit(code)


def create_procs(mp_ctx, dataset_q, stop_q, plugin, logger_q, log_level, duration, concurrency):
    """Create the user process objects."""
    procs = []
    results_pipes = []
    logging.debug("Creating %s Users and corresponding processes", concurrency)
    for idx in range(concurrency):
        send_results, recv_results = mp_ctx.Pipe()
        user = User(
            idx,
            dataset_q=dataset_q,
            stop_q=stop_q,
            results_pipe=send_results,
            plugin=plugin,
            logger_q=logger_q,
            log_level=log_level,
            run_duration=duration,
        )

        proc = mp_ctx.Process(target=user.run_user_process)
        procs.append(proc)
        logging.info("Starting %s", proc)
        proc.start()
        results_pipes.append(recv_results)

    return procs, results_pipes


def main():
    """Load test CLI entrypoint."""
    args = utils.parse_args(sys.argv[1:])

    mp_ctx = mp.get_context("spawn")
    logger_q = mp_ctx.Queue()
    log_reader_thread = logging_utils.init_logging(args.log_level, logger_q)

    # Create processes and their Users
    stop_q = mp_ctx.Queue(1)
    dataset_q = mp_ctx.Queue()
    procs = []
    results_pipes = []

    # Parse config
    logging.debug("Parsing YAML config file %s", args.config)
    concurrency, duration, plugin = 0, 0, None
    try:
        config = utils.yaml_load(args.config)
        concurrency, duration, plugin = utils.parse_config(config)
    except Exception as e:
        logging.error("Exiting due to invalid input: %s", repr(e))

        stop_procs([], dataset_q, stop_q)
        stop_test(logger_q, log_reader_thread, 1)

    try:
        if not isinstance(concurrency, list):
            concurrency = [concurrency]

        for n_users in concurrency:
            config["load_options"]["concurrency"] = n_users
            logging.debug("Creating dataset with configuration %s", config["dataset"])
            dataset = Dataset(**config["dataset"])

            procs, results_pipes = create_procs(mp_ctx, dataset_q, stop_q, plugin, logger_q, args.log_level, duration, n_users)

            logging.debug("Running main process")

            run_main_process(n_users, duration, dataset, dataset_q, stop_q)
            results_list = gather_results(results_pipes)
            utils.write_output(config, results_list, concurrency=n_users, duration=duration)

            stop_procs(procs, dataset_q, stop_q)

    # Terminate queues immediately on ^C
    except KeyboardInterrupt:
        stop_q.cancel_join_thread()
        dataset_q.cancel_join_thread()

        stop_procs(procs, dataset_q, stop_q)
        stop_test(logger_q, log_reader_thread, 1)
    except Exception:
        logging.exception("Unexpected exception in main process")
        stop_procs(procs, dataset_q, stop_q)
        stop_test(logger_q, log_reader_thread, 1)

    stop_test(logger_q, log_reader_thread, 0)


if __name__ == "__main__":
    main()
