from dataset import Dataset
import logging
import multiprocessing as mp
import pandas as pd
from plugins import caikit_client_plugin, text_generation_webui_plugin
import sys
import time
from user import User
import utils

def run_user_process(user, stop_q):
    print(f"User {user.user_id} running process")

    while stop_q.empty():
        result = user.make_request()
        user.results_list.append(result)

    user.results_pipe.send(user.results_list)
    
    time.sleep(4)
    print(f"User {user.user_id} done")


def run_main_process(duration, concurrency, plugin, dataset):
    ctx = mp.get_context('spawn')
    stop_q = ctx.Queue(1)
    dataset_q = ctx.Queue()

    procs = []
    results_pipes = []

    # Create all simulated user processes
    for idx in range(concurrency):
        send_results, recv_results = ctx.Pipe()
        user=User(idx, dataset_q=dataset_q, results_pipe=send_results, plugin=plugin)
        procs.append(ctx.Process(target=run_user_process, args=(user,  stop_q)))
        results_pipes.append(recv_results)

    # Initialize the dataset_queue with 4*concurrency requests
    for query in dataset.get_next_n_queries(4*concurrency):
        dataset_q.put(query)

    # Start processes
    for proc in procs:
        print(f"Starting {proc}")
        proc.start()

    start_time = time.time()
    current_time = start_time
    while ((current_time - start_time) < duration):
        # Keep the dataset queue full for duration
        if dataset_q.qsize() < (2*concurrency):
            print(f"Adding {4*concurrency} entries to dataset queue")
            for query in dataset.get_next_n_queries(2*concurrency):
                dataset_q.put(query)
        time.sleep(0.1)
        current_time = time.time()

    print("Timer ended, stopping processes")

    # Signal users to stop sending requests
    stop_q.put(None)

    # Empty the dataset queue
    while not dataset_q.empty():
        print("Removing element from dataset_q")
        dataset_q.get()

    # Receive all results from each processes results_pipe
    results_list = []
    for results_pipe in results_pipes:
        user_results = results_pipe.recv()
        results_list.extend(user_results)

    for proc in procs:
        proc.join()
    print("procs joined")
    
    return results_list


def run_test(config):
    load_options = config.get("load_options")
    concurrency = load_options.get("concurrency")
    duration = load_options.get("duration")

    plugin_type = config.get("plugin")
    if plugin_type == "text_generation_webui_plugin":
        plugin = text_generation_webui_plugin.TextGenerationWebUIPlugin(config.get("plugin_options"))
    elif plugin_type == "caikit_client_plugin":
        plugin = caikit_client_plugin.CaikitClientPlugin(config.get("plugin_options"))
    else:
        print(f"Unknown plugin type {plugin_type}")
        return

    dataset = Dataset(**config['dataset'])

    results_list = run_main_process(duration, concurrency, plugin, dataset)

    utils.write_output(config, results_list)


def main(args):
    args = utils.parse_args(args)

    if args.verbose:
        logger = mp.log_to_stderr()
        logger.setLevel(logging.INFO)

    config = utils.yaml_load(args.config)
    print(f"dataset config: {config['dataset']}")
    print(f"load_options config: {config['load_options']}")

    run_test(config)


if __name__ == "__main__":
    main(sys.argv[1:])
