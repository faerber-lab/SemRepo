import logging
import os

def get_logger(path, filename):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    new_filename = filename + "_new.log"

    file_handler = logging.FileHandler(os.path.join(path, new_filename))
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger