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


def run_main_process(rps, duration, dataset, request_q, stop_q):
    """Run the main process."""
    logging.info("Test from main process")

    start_time = time.time()
    end_time = start_time + duration
    if rps is not None:
        main_loop_rps_mode(dataset, request_q, rps, start_time, end_time)
    else:
        main_loop_concurrency_mode(dataset, request_q, start_time, end_time)

    logging.info("Timer ended, stopping processes")

    # Signal users to stop sending requests
    stop_q.put(None)

    # Empty the dataset queue
    while not request_q.empty():
        logging.debug("Removing element from request_q")
        request_q.get()

    return

def main_loop_concurrency_mode(dataset, request_q, start_time, end_time):
    """Let all users send requests repeatedly until end_time"""
    logging.info("Test from main process")

    # Initialize the request_q with 2*concurrency requests
    for query in dataset.get_next_n_queries(2 * concurrency):
        request_q.put((None, query))

    current_time = start_time
    while current_time < end_time:
        if request_q.qsize() < int(0.5*concurrency + 1):
            logging.info("Adding %d entries to dataset queue", concurrency)
            for query in dataset.get_next_n_queries(concurrency):
                request_q.put((None, query))
        time.sleep(0.1)
        current_time = time.time()

    logging.info("Timer ended, stopping processes")

    # Signal users to stop sending requests
    stop_q.put(None)


def request_schedule_constant_rps(rps, start_time, end_time):
    """Returns a list of timestamps for request schedule with constant RPS"""
    interval = 1 / rps
    next_req_time = start_time
    while next_req_time < end_time:
        yield(next_req_time)
        next_req_time = next_req_time + interval


# This function should support non-constant RPS in the future
def main_loop_rps_mode(dataset, request_q, rps, start_time, end_time):
    """Dispatch requests with constant RPS, via schedule_q"""
    req_times = request_schedule_constant_rps(rps, start_time, end_time)
        
    current_time = time.time()
    query = dataset.get_next_n_queries(1)[0]
    for next_req_time in req_times:
        while next_req_time > current_time:
            # Wait or spin until next req needs to be dispatched
            sleep_time = (next_req_time - current_time) - 0.03 # Sleep until 30ms before next_req_time
            if sleep_time > 0:
                time.sleep(sleep_time)
            # else spin
            current_time = time.time()
        
        logging.info(f"Scheduling request time {next_req_time}")
        request_q.put((next_req_time, query))
        
        query = dataset.get_next_n_queries(1)[0]

        if current_time >= end_time:
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


def exit_gracefully(procs, request_q, stop_q, logger_q, log_reader_thread, code):
    """Exit gracefully."""
    # Signal users to stop sending requests
    if stop_q.empty():
        stop_q.put(None)

    if request_q is not None and not request_q.empty():
        logging.warning("Removing more elements from request_q after gathering results!")
        while not request_q.empty():
            request_q.get()

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
    request_q = mp_ctx.Queue(1)
    request_q.cancel_join_thread()
    stop_q = mp_ctx.Queue(1)

    procs = []
    results_pipes = []

    # Parse config
    logging.debug("Parsing YAML config file %s", args.config)
    rps, concurrency, duration, plugin = None, 0, 0, None
    try:
        config = utils.yaml_load(args.config)
        rps, concurrency, duration, plugin = utils.parse_config(config)
    except Exception as e:
        logging.error("Exiting due to invalid input: %s", repr(e))
        exit_gracefully(procs, request_q, stop_q, logger_q, log_reader_thread, 1)

    try:
        logging.debug("Creating dataset with configuration %s", config["dataset"])
        # Get model_name if set for prompt formatting
        model_name = config.get("plugin_options", {}).get("model_name", "")
        dataset = Dataset(model_name=model_name, **config["dataset"])

        logging.info("Creating %s Users and corresponding processes", concurrency)
        for idx in range(concurrency):
            send_results, recv_results = mp_ctx.Pipe()
            results_pipes.append(recv_results)
            user = User(
                idx,
                request_q=request_q,
                stop_q=stop_q,
                results_pipe=send_results,
                plugin=plugin,
                logger_q=logger_q,
                log_level=args.log_level,
                run_duration=duration,
                rate_limited=(rps is not None)
            )
            proc = mp_ctx.Process(target=user.run_user_process)
            procs.append(proc)
            logging.info("Starting %s", proc)
            proc.start()

        logging.debug("Running main process")
        run_main_process(rps, duration, dataset, request_q, stop_q)

        results_list = gather_results(results_pipes)

        utils.write_output(config, results_list)

    # Terminate queues immediately on ^C
    except KeyboardInterrupt:
        stop_q.cancel_join_thread()
        exit_gracefully(procs, request_q, stop_q, logger_q, log_reader_thread, 130)
    except Exception:
        logging.exception("Unexpected exception in main process")
        exit_gracefully(procs, request_q, stop_q, logger_q, log_reader_thread, 1)

    exit_gracefully(procs, request_q, stop_q, logger_q, log_reader_thread, 0)


if __name__ == "__main__":
    main(sys.argv[1:])
