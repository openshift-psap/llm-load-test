import logging
import logging.handlers
import multiprocessing as mp
import sys
import time
import utils

from dataset import Dataset
from user import User
import logging_utils

def run_main_process(procs, concurrency, duration, dataset, dataset_q, stop_q):
    logging.info("Test from main process")

    # Initialize the dataset_queue with 4*concurrency requests
    for query in dataset.get_next_n_queries(4*concurrency):
        dataset_q.put(query)

    # Start processes
    for proc in procs:
        logging.info("Starting %s", proc)
        proc.start()

    start_time = time.time()
    current_time = start_time
    while (current_time - start_time) < duration:
        # Keep the dataset queue full for duration
        if dataset_q.qsize() < (2*concurrency):
            logging.debug("Adding %d entries to dataset queue", 2*concurrency)
            for query in dataset.get_next_n_queries(2*concurrency):
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
    dataset_q.close()

    return

def gather_results(results_pipes):
    # Receive all results from each processes results_pipe
    logging.debug("Receiving results from user processes")
    results_list = []
    for results_pipe in results_pipes:
        user_results = results_pipe.recv()
        results_list.extend(user_results)
    return results_list

def exit_gracefully(procs, logger_q, log_reader_thread, code):
    logging.debug("Calling join() on all user processes")
    for proc in procs:
        proc.join()
    logging.info("User processes terminated succesfully")

    # Shutdown logger thread
    logger_q.put(None)
    log_reader_thread.join()

    exit(code)

    
def main(args):
    args = utils.parse_args(args)

    mp_ctx = mp.get_context('spawn')
    logger_q = mp_ctx.Queue()
    log_reader_thread = logging_utils.init_logging(args.log_level, logger_q)

    ## Create processes and their Users
    stop_q = mp_ctx.Queue(1)
    dataset_q = mp_ctx.Queue()
    procs = []
    results_pipes = []

    #### Parse config
    logging.debug("Parsing YAML config file %s", args.config)
    concurrency, duration, plugin = 0, 0, None
    config = utils.yaml_load(args.config)
    try:
        concurrency, duration, plugin = utils.parse_config(config)
    except ValueError:
        logging.error("Exiting due to invalid input")
        exit_gracefully(procs, logger_q, log_reader_thread, 1)

    logging.debug("Creating dataset with configuration %s", config['dataset'])
    dataset = Dataset(**config['dataset'])


    logging.debug("Creating %s Users and corresponding processes", concurrency)
    for idx in range(concurrency):
        send_results, recv_results = mp_ctx.Pipe()
        user = User(idx,
                    dataset_q=dataset_q,
                    stop_q=stop_q,
                    results_pipe=send_results,
                    plugin=plugin,
                    logger_q=logger_q,
                    log_level=args.log_level)
        procs.append(mp_ctx.Process(target=user.run_user_process))
        results_pipes.append(recv_results)

    logging.debug("Running main process")
    run_main_process(procs, concurrency, duration, dataset, dataset_q, stop_q)

    results_list = gather_results(results_pipes)

    utils.write_output(config, results_list)

    exit_gracefully(procs, logger_q, log_reader_thread, 0)



if __name__ == "__main__":
    main(sys.argv[1:])
    