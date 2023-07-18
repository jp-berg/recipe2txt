import os
import unittest

import recipe2txt.utils


class TracebackTests(unittest.TestCase):

    def setUp(self) -> None:
        self.gen_tbs = GenTraces(-7, -29, 23, 37)

    def test_anonymize_paths(self):

        path_start = os.path.join("...", "test")
        for val, trace in zip(self.gen_tbs.error_vals, self.gen_tbs.tb_ex_list):
            anon_stack = recipe2txt.utils.traceback_utils.shorten_paths(trace.stack, "test")
            for frame in anon_stack:
                with self.subTest(i=f"partial anonymization | Number = {val} | Frame = {frame}"):
                    self.assertTrue(frame.filename.startswith(path_start))
            anon_stack = recipe2txt.utils.traceback_utils.shorten_paths(trace.stack, "tests")
            for frame in anon_stack:
                with self.subTest(i=f"full anonymization | Number = {val} | Frame = {frame}"):
                    self.assertEqual(frame.filename, ".../gen_stack.py")

    def test_get_shared_frames(self):
        shared = recipe2txt.utils.traceback_utils.get_shared_frames(self.gen_tbs.tb_ex_list)

        i = 0
        for shared_frame in shared:
            for tb in self.gen_tbs.tb_ex_list:
                with self.subTest(i=f"{shared_frame=} | {tb.stack[i]=} | Frame-Number {i}"):
                    self.assertEqual(tb.stack[i], shared_frame)
            i += 1

        remaining = [tb_ex.stack[i:] for tb_ex in self.gen_tbs.tb_ex_list if len(tb_ex.stack) > i]

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
            self.fail(f"get_shared_frames()-cutoff to early: all stacks still have a common frame (Failed for frames {equal_frames})")

    def test_format_stacks(self):

        validation = "".join(self.gen_tbs.get_formatted())

        shared_frames = recipe2txt.utils.traceback_utils.get_shared_frames(self.gen_tbs.tb_ex_list)
        lines_list = recipe2txt.utils.traceback_utils.format_stacks(self.gen_tbs.tb_ex_list, shared_frames, "test")
        test = "".join([line for lines in lines_list for line in lines])
        self.assertEqual(validation, test)
