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

import contextlib
import logging
import shutil
import test.testfiles.permanent.gen_stack as gen_stack
from pathlib import Path
from typing import Final, Generator

import recipe2txt.utils.misc as misc
from recipe2txt.utils.ContextLogger import (_LOG_FORMAT_STREAM,
                                            QueueContextFilter,
                                            QueueContextFormatter)
from recipe2txt.utils.ContextLogger import QueueContextManager as QCM
from recipe2txt.utils.ContextLogger import get_logger, string2level
from recipe2txt.utils.misc import (Directory, File, ensure_accessible_file,
                                   ensure_existence_dir_critical)

logger = get_logger(__name__)
if __name__ == '__main__':
    logger.setLevel(logging.INFO)
else:
    logger.setLevel(logging.CRITICAL)

root: Final = Directory(Path(__file__).parent)
log_files = ensure_existence_dir_critical(root, "logfiles")
write_logger = logging.getLogger("writelogger")
write_logger.propagate = False
write_logger.setLevel(logging.DEBUG)

formatter = QueueContextFormatter(_LOG_FORMAT_STREAM)
log_filter = QueueContextFilter()

write_logger.addFilter(log_filter)

dir_normal = log_files / "gen_log_res"
dir_fail = Path("/root/test")


def queue_processor(nums: list[int], directory_normal: Path, directory_fail: Path) -> int:
    minimum = 1000
    total = 0
    for idx, num in enumerate(nums):
        with QCM(write_logger, write_logger.info, "Processing %s", num):  # Check indentation, string formatting
            try:
                res = int(gen_stack.fun5(num))
            except ZeroDivisionError as e:
                write_logger.error("Value caused ZeroDivisonError: ", exc_info=e)
                res = 101
            except ValueError as e:
                write_logger.error("Value caused error: ", exc_info=e)  # C
                res = 202
            total += res
            write_logger.info("Total is %s", total)  # Check if exceptions and other log messages work together
            if total < minimum:
                write_logger.warning("Needs %s more", minimum - total)
            # Check logging indentation in different module
            if res % 2 == 0:
                file = ensure_accessible_file(directory_normal, str(res))
            else:
                file = ensure_accessible_file(directory_fail, str(res))
            if file:
                file.write_text(str(total))
            else:
                write_logger.warning("Total could not be written!")
            if idx == (len(nums) - 1):
                write_logger.critical("Reached the last element")  # Check highest log level
    if total < minimum:
        write_logger.error("The total (%s) is smaller than %s", total, minimum)  # Check if context is released
    return total


def gen_log() -> None:
    if dir_normal.is_dir():
        shutil.rmtree(dir_normal)
    queue = [-7, 29, 8, 41, 3, 44, -19, 2, 1, 6]
    logging.info("The values used are %s", queue)  # Check 'stringification of logged objects
    res = queue_processor(queue, dir_normal, dir_fail)
    write_logger.info("The result of the calculations: %s", res)
    shutil.rmtree(dir_normal)


@contextlib.contextmanager
def inject_write_logger(logfile: File, level: int) -> Generator[None, None, None]:
    filehandler = logging.FileHandler(logfile)
    filehandler.setFormatter(formatter)
    write_logger.addHandler(filehandler)

    log_filter.set_handler(filehandler)
    log_filter.set_level(level)

    gen_stack_log, gen_stack.logger = gen_stack.logger, write_logger
    misc_log, misc.logger = misc.logger, write_logger
    yield
    gen_stack.logger = gen_stack_log
    misc.logger = misc_log

    write_logger.removeHandler(filehandler)
    filehandler.close()


def gen_logs(folder: Path) -> list[File]:
    write_logger.handlers.clear()
    write_logger.filters.clear()
    paths = []
    for string, num in string2level.items():
        file = misc.ensure_accessible_file_critical(folder, string)
        if file.stat().st_size == 0:
            logger.info("Generating %s", file)
            with inject_write_logger(file, num):
                gen_log()

        paths.append(File(file))
    return paths


log_paths: list[File] = gen_logs(log_files)
