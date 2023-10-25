# Copyright (C) 2023 Jan Philipp Berg <git.7ksst@aleeas.com>
#
# This file is part of recipe2txt.
#
# recipe2txt is free software: you can redistribute it and/or modify it under the
# terms of
# the GNU General Public License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# recipe2txt is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# recipe2txt.
# If not, see <https://www.gnu.org/licenses/>.

import os
import traceback
from copy import deepcopy
from os import linesep


def shorten_paths(
        stack: traceback.StackSummary,
        first_visible_dir: str | None = None,
        skip_first: bool = False,
) -> traceback.StackSummary:
    if first_visible_dir is None:
        paths = [frame.filename for frame in stack]
        shared = os.path.commonpath(paths)
        first_visible_dir = os.path.basename(shared)

    start = 1 if skip_first else 0
    for frame in stack[start:]:
        tmp = frame.filename.split(first_visible_dir, 1)
        if len(tmp) == 1:
            remaining_path = os.path.split(tmp[0])[1]  # Just the filename
            frame.filename = os.path.join("...", remaining_path)
        else:
            remaining_path = tmp[1]
            if remaining_path.startswith(os.sep):
                remaining_path = remaining_path[1:]
            frame.filename = os.path.join("...", first_visible_dir, remaining_path)
    return stack


def get_shared_frames(
        tb_exes: list[traceback.TracebackException],
) -> traceback.StackSummary:
    stacks = [tb_ex.stack for tb_ex in tb_exes]
    shortest = deepcopy(min(stacks, key=len))
    equal = True
    shared_list = []
    for i in range(len(shortest)):
        comp = stacks[0][i]
        for stack in stacks[1:]:
            if stack[i] != comp:
                equal = False
                break
        if not equal:
            i = i - 1 if i > 0 else i
            shared_list = shortest[:i]
            break
    if equal:
        shared_list = shortest[:-1]
    shared = traceback.StackSummary.from_list(shared_list)
    return shared


def format_stacks(
        tb_exes: list[traceback.TracebackException],
        shared_stack: traceback.StackSummary,
        first_visible_dir: str | None = None,
) -> list[list[str]]:
    shared_stack_len = len(shared_stack)
    tb_exes_copy = deepcopy(tb_exes)
    for tb_ex in tb_exes_copy:
        tb_ex.stack = traceback.StackSummary.from_list(tb_ex.stack[shared_stack_len:])
        if first_visible_dir:
            tb_ex.stack = shorten_paths(tb_ex.stack, first_visible_dir)
    if first_visible_dir:
        shared_stack = shorten_paths(shared_stack, first_visible_dir)
    first_stack = shared_stack.format() + list(tb_exes_copy[0].format())[1:]

    sep = ["\t..." + linesep] if shared_stack else []
    stacks = [sep + list(tb_ex.format())[1:] for tb_ex in tb_exes_copy[1:]]

    return [first_stack] + stacks
