"""Main logging class."""

import logging
import threading


def logger_thread(q):
    """Get the logger thread."""
    while True:
        record = q.get()
        if record is None:
            break
        logger = logging.getLogger(record.name)
        logger.handle(record)


def init_logging(log_level, logger_q):
    """Initialize the logger."""
    logging_format = (
        "%(asctime)s %(levelname)-8s %(name)s %(processName)-10s %(message)s"
    )
    logging.basicConfig(format=logging_format, level=log_level)

    log_reader_thread = threading.Thread(target=logger_thread, args=(logger_q,))
    log_reader_thread.start()

    return log_reader_thread
