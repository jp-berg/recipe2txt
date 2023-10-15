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

import unittest
from math import trunc
from time import sleep

from recipe2txt.utils.timer import Timer


class Test(unittest.TestCase):

    def test_multi_timer(self):
        t = Timer()
        id1 = t.start_multi()
        sleep(0.1)
        id2 = t.start_multi()
        sleep(0.1)
        elapsed1 = t.end_multi(id1)
        t.start()
        sleep(0.1)
        elapsed0 = t.end()
        sleep(0.2)
        elapsed2 = t.end_multi(id2)

        self.assertEqual(trunc(elapsed0 * 1000), 100)
        self.assertEqual(trunc(elapsed1 * 1000), 200)
        self.assertEqual(trunc(elapsed2 * 1000), 400)
        self.assertEqual(trunc(t.total() * 100),  70)
        with self.assertRaises(RuntimeError):
            t.end_multi(-1)
