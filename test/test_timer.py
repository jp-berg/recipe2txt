import unittest
from time import sleep
from math import trunc

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
