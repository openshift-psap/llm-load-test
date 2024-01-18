from dataset import Dataset
import logging
import logging.handlers
import threading

import multiprocessing as mp
import pandas as pd
from plugins import caikit_client_plugin, text_generation_webui_plugin
import sys
import time
from user import User
import utils

def logger_thread(q):
    while True:
        record = q.get()
        if record is None:
            break
        logger = logging.getLogger(record.name)
        logger.handle(record)

def init_user_process_logging(q, log_level):
    qh = logging.handlers.QueueHandler(q)
    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()
    root.addHandler(qh)

def run_user_process(user, stop_q, logger_q, log_level):
    init_user_process_logging(logger_q, log_level)

    logger = logging.getLogger("user")
    logger.info(f"INFO TEST User {user.user_id} running process")
    logger.debug(f"DEBUG TEST User {user.user_id} running process")

    while stop_q.empty():
        result = user.make_request()
        user.results_list.append(result)

    user.results_pipe.send(user.results_list)
    
    time.sleep(4)
    logger.info(f"User {user.user_id} done")


def run_main_process(mp_ctx, logger_q, log_level, duration, concurrency, plugin, dataset):
    logging.info("Test from main process")

    #ctx = mp.get_context('spawn')
    stop_q = mp_ctx.Queue(1)
    dataset_q = mp_ctx.Queue()

    procs = []
    results_pipes = []

    # Create all simulated user processes
    for idx in range(concurrency):
        send_results, recv_results = mp_ctx.Pipe()
        user = User(idx, dataset_q=dataset_q, results_pipe=send_results, plugin=plugin)
        procs.append(mp_ctx.Process(target=run_user_process, args=(user,  stop_q, logger_q, log_level)))
        results_pipes.append(recv_results)

    # Initialize the dataset_queue with 4*concurrency requests
    for query in dataset.get_next_n_queries(4*concurrency):
        dataset_q.put(query)

    # Start processes
    for proc in procs:
        logging.info(f"Starting {proc}")
        proc.start()

    start_time = time.time()
    current_time = start_time
    while ((current_time - start_time) < duration):
        # Keep the dataset queue full for duration
        if dataset_q.qsize() < (2*concurrency):
            logging.debug(f"Adding {2*concurrency} entries to dataset queue")
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

    # Receive all results from each processes results_pipe
    results_list = []
    for results_pipe in results_pipes:
        user_results = results_pipe.recv()
        results_list.extend(user_results)

    for proc in procs:
        proc.join()
    logging.info("User processes terminated")

    return results_list

def run_test(mp_ctx, logger_q, log_level, config):
    load_options = config.get("load_options")
    concurrency = load_options.get("concurrency")
    duration = load_options.get("duration")

    plugin_type = config.get("plugin")
    if plugin_type == "text_generation_webui_plugin":
        plugin = text_generation_webui_plugin.TextGenerationWebUIPlugin(config.get("plugin_options"))
    elif plugin_type == "caikit_client_plugin":
        plugin = caikit_client_plugin.CaikitClientPlugin(config.get("plugin_options"))
    else:
        logging.warn(f"Unknown plugin type {plugin_type}")
        return

    dataset = Dataset(**config['dataset'])

    results_list = run_main_process(mp_ctx, logger_q, log_level, duration, concurrency, plugin, dataset)

    utils.write_output(config, results_list)

if __name__ == "__main__":
    mp_ctx = mp.get_context('spawn')

    args = utils.parse_args(sys.argv[1:])

    log_level = logging.INFO
    if args.verbose:
        log_level = logging.DEBUG

    logger_q = mp_ctx.Queue()

    logging_format = '%(asctime)s %(levelname)-8s %(name)s %(processName)-10s %(message)s'
    logging.basicConfig(format=logging_format, level=log_level)

    log_reader_thread = threading.Thread(target=logger_thread, args=(logger_q,))
    log_reader_thread.start()

    config = utils.yaml_load(args.config)
    
    logger = logging.getLogger()

    logger.info(f"dataset config: {config['dataset']}")
    logger.info(f"load_options config: {config['load_options']}")

    run_test(mp_ctx, logger_q, log_level, config)

    logger_q.put(None)
    log_reader_thread.join()
