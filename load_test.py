"""Main llm-load-test CLI entrypoint."""

import logging
import logging.handlers
import multiprocessing as mp
import sys
import time
from user import User

from dataset import Dataset

import logging_utils

import utils


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


def run_warmup(
    dataset,
    dataset_q,
    results_pipes,
    warmup_q,
    warmup_reqs=10,
    warmup_timeout=60,
):
    """Run the warmup tasks."""
    # Put requests in warmup queue
    for query in dataset.get_next_n_queries(warmup_reqs):
        dataset_q.put(query)

    warmup_results = 0
    warmup_results_list = []
    start_time = time.time()
    current_time = start_time
    while warmup_results < warmup_reqs:
        for results_pipe in results_pipes:
            if results_pipe.poll():
                user_results = results_pipe.recv()
                warmup_results = warmup_results + len(user_results)
                warmup_results_list.extend(user_results)
        logging.info(
            "Warming up, %s results received out of %s expected",
            warmup_results,
            warmup_reqs,
        )
        current_time = time.time()
        if (current_time - start_time) > warmup_timeout:
            logging.error("Warmup timed out (%s seconds) before receiving all responses", warmup_timeout)
            return False
        time.sleep(2)

    # Signal end of warmup
    warmup_q.put(None)

    err_count = 0
    for result in warmup_results_list:
        if result.error_text is not None:
            err_count = err_count + 1

    if err_count > 0:
        logging.error(
            "Warmup failed: %s out of %s requests returned errors",
            err_count,
            warmup_reqs,
        )
        return False
    return True


def gather_results(results_pipes):
    """Get the results."""
    # Receive all results from each processes results_pipe
    logging.debug("Receiving results from user processes")
    results_list = []
    for results_pipe in results_pipes:
        user_results = results_pipe.recv()
        results_list.extend(user_results)
    return results_list


def exit_gracefully(procs, warmup_q, dataset_q, stop_q, logger_q, log_reader_thread, code):
    """Exit gracefully."""
    # Signal users to stop sending requests
    if warmup_q is not None and warmup_q.empty():
        warmup_q.put(None)

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

    # Shutdown logger thread
    logger_q.put(None)
    log_reader_thread.join()

    sys.exit(code)


def main(args):
    """Load test CLI entrypoint."""
    args = utils.parse_args(args)

    mp_ctx = mp.get_context("spawn")
    logger_q = mp_ctx.Queue()
    log_reader_thread = logging_utils.init_logging(args.log_level, logger_q)

    # Create processes and their Users
    stop_q = mp_ctx.Queue(1)
    dataset_q = mp_ctx.Queue()
    warmup_q = mp_ctx.Queue(1)
    procs = []
    results_pipes = []

    # Parse config
    logging.debug("Parsing YAML config file %s", args.config)
    concurrency, duration, plugin = 0, 0, None
    try:
        config = utils.yaml_load(args.config)
        concurrency, duration, plugin = utils.parse_config(config)
    except Exception as e:
        logging.error("Exiting due to invalid input: %s", e)
        exit_gracefully(procs, warmup_q, dataset_q, stop_q, logger_q, log_reader_thread, 1)

    try:
        logging.debug("Creating dataset with configuration %s", config["dataset"])
        # Get model_name if set for prompt formatting
        model_name = config.get("plugin_options", {}).get("model_name", "")
        dataset = Dataset(model_name=model_name, **config["dataset"])

        warmup = config.get("warmup")
        if not warmup:
            warmup_q = None
        logging.debug("Creating %s Users and corresponding processes", concurrency)
        for idx in range(concurrency):
            send_results, recv_results = mp_ctx.Pipe()
            user = User(
                idx,
                dataset_q=dataset_q,
                warmup_q=warmup_q,
                stop_q=stop_q,
                results_pipe=send_results,
                plugin=plugin,
                logger_q=logger_q,
                log_level=args.log_level,
                run_duration=duration,
            )
            proc = mp_ctx.Process(target=user.run_user_process)
            procs.append(proc)
            logging.info("Starting %s", proc)
            proc.start()
            results_pipes.append(recv_results)

        if config.get("warmup"):
            logging.info("Running warmup")
            warmup_options = config.get("warmup_options", {})
            warmup_reqs = warmup_options.get("requests", 10)
            warmup_timeout = warmup_options.get("timeout_sec", 120)
            warmup_passed = run_warmup(
                dataset,
                dataset_q,
                results_pipes,
                warmup_q,
                warmup_reqs=warmup_reqs,
                warmup_timeout=warmup_timeout,
            )
            if not warmup_passed:
                exit_gracefully(procs, warmup_q, dataset_q, stop_q, logger_q, log_reader_thread, 1)
            else:
                time.sleep(2)

        logging.debug("Running main process")
        run_main_process(concurrency, duration, dataset, dataset_q, stop_q)

        # Result_list has all the agregated results
        results_list = gather_results(results_pipes)
        # Now we include the results from the metadata inclusions as part of the results
        
        utils.write_output(config, results_list)

    except Exception:
        logging.exception("Unexpected exception in main process")
        exit_gracefully(procs, warmup_q, dataset_q, stop_q, logger_q, log_reader_thread, 1)

    exit_gracefully(procs, warmup_q, dataset_q, stop_q, logger_q, log_reader_thread, 0)


if __name__ == "__main__":
    main(sys.argv[1:])
