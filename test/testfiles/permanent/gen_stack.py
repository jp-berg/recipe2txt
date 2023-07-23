import logging
from math import sqrt
from pathlib import Path
import traceback

from recipe2txt.utils.traceback_utils import get_shared_frames, format_stacks
from recipe2txt.utils.misc import ensure_accessible_file

logger = logging.getLogger(__name__)


def fun0_1(x: float | int) -> float:
    return sqrt(x)


def fun0_2(x: float | int) -> float:
    return 13 / x


def fun1_2(x: float | int) -> float:
    return fun0_2(x) * 10


def fun1_1(x: float | int)  -> float:
    return fun0_1(x) * 3


def fun2(x: float | int) -> float:
    if x > 12:
        logger.debug("Calling fun1_2") # Check logging indentation from different function
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
