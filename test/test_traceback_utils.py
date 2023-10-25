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

import os
import unittest
from test.testfiles.permanent.gen_stack import GenTraces

import recipe2txt.utils.traceback_utils as tb_u


class TracebackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gen_tbs = GenTraces(-7, -29, 23, 37)

    def test_shorten_paths(self):
        path_start = os.path.join("...", "test")
        for val, trace in zip(self.gen_tbs.error_vals, self.gen_tbs.tb_ex_list):
            anon_stack = tb_u.shorten_paths(trace.stack, "test")
            for frame in anon_stack:
                with self.subTest(
                    msg=f"partial anonymization | Number = {val} | Frame = {frame}"
                ):
                    self.assertTrue(frame.filename.startswith(path_start))
            anon_stack = tb_u.shorten_paths(trace.stack, "tests")
            for frame in anon_stack:
                with self.subTest(
                    msg=f"full anonymization | Number = {val} | Frame = {frame}"
                ):
                    self.assertEqual(frame.filename, ".../gen_stack.py")

    def test_get_shared_frames(self):
        shared = tb_u.get_shared_frames(self.gen_tbs.tb_ex_list)

        i = 0
        for shared_frame in shared:
            for tb in self.gen_tbs.tb_ex_list:
                with self.subTest(
                    shared_frame=shared_frame, frame=tb.stack[i], frame_number=i
                ):
                    self.assertEqual(tb.stack[i], shared_frame)
            i += 1

        remaining = [
            tb_ex.stack[i:] for tb_ex in self.gen_tbs.tb_ex_list if len(tb_ex.stack) > i
        ]

        if not remaining:
            return

        min_len = len(min(remaining, key=len))
        to_compare = remaining[0]
        equal_frames = []
        for i in range(1, min_len):
            all_frames_equal = True
            for stack in remaining[1:]:
                if to_compare[i] != stack[i]:
                    all_frames_equal = False
                    break
            if all_frames_equal:
                equal_frames.append(i)
            else:
                break

        if equal_frames:
            self.fail(
                "get_shared_frames()-cutoff to early: all stacks still have a common"
                f" frame (Failed for frames {equal_frames})"
            )

    def test_format_stacks(self):
        validation = "".join(self.gen_tbs.get_formatted())

        shared_frames = tb_u.get_shared_frames(self.gen_tbs.tb_ex_list)
        lines_list = tb_u.format_stacks(self.gen_tbs.tb_ex_list, shared_frames, "test")
        test = "".join([line for lines in lines_list for line in lines])
        self.assertEqual(validation, test)
