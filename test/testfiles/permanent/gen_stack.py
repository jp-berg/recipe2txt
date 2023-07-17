from math import sqrt
from pathlib import Path
import traceback
import os

from recipe2txt.utils.misc import get_shared_frames, format_stacks, ensure_accessible_file


def fun0_1(x):
    return sqrt(x)


def fun0_2(x):
    return 13 / x


def fun1_2(x):
    return fun0_2(x) * 10


def fun1_1(x):
    return fun0_1(x) * 3


def fun2(x):
    if x > 12:
        return fun1_2(x * 0)
    else:
        return fun1_1(x) - 12


def fun3(x):
    return fun2(x) * 4.56


def fun4(x):
    return fun3(x) + 0.1


def fun5(x):
    return fun4(x) + 4321


class GenTraces:
    def __init__(self, *values):
        self.tb_ex_list = []
        self.error_vals = []
        self.res = [self._provoke_exception(value) for value in values]
        self.values = values

    def _provoke_exception(self, x):
        try:
            y = fun5(x)
        except Exception as e:
            self.tb_ex_list.append(traceback.TracebackException.from_exception(e))
            self.error_vals.append(x)
            return None
        return y

    def get_formatted(self):
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
