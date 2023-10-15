# Copyright (C) 2023 Jan Philipp Berg <git.7ksst@aleeas.com>
#
# This file is part of recipe2txt.
#
# recipe2txt is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# recipe2txt is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with recipe2txt.
# If not, see <https://www.gnu.org/licenses/>.
"""
Entry point of the program.
"""
import os
import sys
from logging import DEBUG

from recipe2txt.argparse import mutex_args, process_params, get_parser
from recipe2txt.file_setup import write_errors
from recipe2txt.utils.ContextLogger import get_logger

logger = get_logger(__name__)

def main() -> None:
    a = get_parser().parse_args()
    mutex_args(a)
    urls, fetcher = process_params(a)
    fetcher.fetch(urls)
    logger.info("--- Summary ---")
    if logger.isEnabledFor(DEBUG):
        logger.info(fetcher.get_counts())
    write_errors(a.debug)
    sys.exit(os.EX_OK)

if __name__ == '__main__':
    main()

