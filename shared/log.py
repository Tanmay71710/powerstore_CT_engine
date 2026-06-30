import logging
from logging.handlers import RotatingFileHandler

def set_logger(log_file):
    
    logger = logging.getLogger('CT_engine')

    # Set up logging
    handler = RotatingFileHandler(log_file, maxBytes=100 * 1024 * 1024, backupCount=1)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return logger

def get_logger(logger_name):

    current_logging = logging.getLogger("CT_engine." + logger_name)
    return current_logging