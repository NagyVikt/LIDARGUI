# utils/logging_config.py

import logging

def configure_logging(log_file='led_control.log'):
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
