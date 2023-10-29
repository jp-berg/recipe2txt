# Copyright (C) 2023 Jan Philipp Berg <git.7ksst@aleeas.com>
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

import logging
import traceback
from math import sqrt
from pathlib import Path

from recipe2txt.utils.misc import ensure_accessible_file
from recipe2txt.utils.traceback_utils import format_stacks, get_shared_frames

logger = logging.getLogger(__name__)


def fun0_1(x: float | int) -> float:
    return sqrt(x)


def fun0_2(x: float | int) -> float:
    return 13 / x


def fun1_2(x: float | int) -> float:
    return fun0_2(x) * 10


def fun1_1(x: float | int) -> float:
    return fun0_1(x) * 3


def fun2(x: float | int) -> float:
    if x > 12:
        logger.debug(
            "Calling fun1_2"
        )  # Check logging indentation from different function
        return fun1_2(x * 0)
    else:
        logger.debug("Calling fun1_1")
        return fun1_1(x) - 12


def fun3(x: float | int) -> float:
    return fun2(x) * 4.56


def fun4(x: float | int) -> float:
    return fun3(x) + 0.1


def fun5(x: float | int) -> float:
    return fun4(x) + 4321


class GenTraces:
    def __init__(self, *values: int) -> None:
        self.tb_ex_list: list[traceback.TracebackException] = []
        self.error_vals: list[int] = []
        self.res = [self._provoke_exception(value) for value in values]
        self.values = values

    def _provoke_exception(self, x: int) -> float | None:
        try:
            y = fun5(x)
        except Exception as e:
            self.tb_ex_list.append(traceback.TracebackException.from_exception(e))
            self.error_vals.append(x)
            return None
        return y

    def get_formatted(self) -> list[str]:
        name = "_".join([str(val) for val in self.error_vals]) + ".txt"
        if not (file := ensure_accessible_file(Path(__file__).parent, "traces", name)):
            raise OSError(f"File could not be created: {name}")

        if not file.stat().st_size > 0:
            shared_frames = get_shared_frames(self.tb_ex_list)
            lines_list = format_stacks(self.tb_ex_list, shared_frames, "test")
            lines = [line for sublist in lines_list for line in sublist]
            with open(file, "w") as f:
                f.writelines(lines)
        else:
            with open(file, "r") as f:
                lines = f.readlines()

        return lines
