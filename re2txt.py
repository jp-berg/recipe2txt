import sys
import os
from logging import DEBUG
from recipe2txt.argparse import parser, mutex_args, process_params
from recipe2txt.file_setup import write_errors
from recipe2txt.utils.ContextLogger import get_logger

logger = get_logger(__name__)

if __name__ == '__main__':
    a = parser.parse_args()
    mutex_args(a)
    urls, fetcher = process_params(a)
    fetcher.fetch(urls)
    logger.info("--- Summary ---")
    if logger.isEnabledFor(DEBUG):
        logger.info(fetcher.get_counts())
    write_errors(a.debug)
    sys.exit(os.EX_OK)
