# Copyright (C) 2024 Jan Philipp Berg <git.7ksst@aleeas.com>
#
# This file is part of recipe2txt.
#
# recipe2txt is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.
#
# recipe2txt is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# recipe2txt. If not, see <https://www.gnu.org/licenses/>.
"""
Entry point of the program.
"""
import logging
import os
import sys
from logging import DEBUG

from recipe2txt.fetcher import Cache
from recipe2txt.html2recipe import update_counts
from recipe2txt.parsing_error import write_errors
from recipe2txt.recipes2out import RecipeWriter
from recipe2txt.user_interface import (
    get_parser,
    init_database,
    init_logging,
    mutex_args,
    sancheck_args,
    strings2urls,
)
from recipe2txt.utils.ContextLogger import get_logger
from recipe2txt.utils.misc import Counts, dict2str, ensure_accessible_file_critical

try:
    from recipe2txt.fetcher_async import AsyncFetcher as Fetcher
except ImportError:
    from recipe2txt.fetcher import (  # type: ignore[assignment] # isort: skip
        Fetcher as Fetcher,
    )


logger = get_logger(__name__)


def main() -> None:
    """
    Orchestrates a full run of the program
    """
    # ----------
    a = get_parser().parse_args()
    mutex_args(a)
    init_logging(a.debug, a.verbosity)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "CLI-ARGS: %s\t%s", os.linesep, dict2str(vars(a), os.linesep + "\t")
        )

    logger.info("--- Processing arguments ---")
    sancheck_args(a)

    out = ensure_accessible_file_critical(a.output)
    database = init_database(a.debug, out)
    writer = RecipeWriter(out, a.output_format)
    counts = Counts()
    urls = strings2urls(a.url, a.file, counts)
    fetcher = Fetcher(
        database=database,
        counts=counts,
        timeout=a.timeout,
        connections=a.connections,
        caching_strategy=Cache(a.cache),
    )
    # ----------
    fetcher.fetch(urls)
    # ----------
    logger.info("--- Writing recipes ---")
    recipes = database.get_recipes()
    update_counts(counts, recipes)
    writer.write(recipes)
    # ----------
    logger.info("--- Summary ---")
    if logger.isEnabledFor(DEBUG):
        logger.info(fetcher.get_counts())
    write_errors(a.debug)
    sys.exit(os.EX_OK)


if __name__ == "__main__":
    main()
