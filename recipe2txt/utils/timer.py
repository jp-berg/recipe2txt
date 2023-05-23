import time
import random
from sys import maxsize


def _get_next_id() -> int:
    return random.randint(1, maxsize)  # 0 reserved


class Timer:
    def __init__(self) -> None:
        self.times: list[float] = []
        self.total_cache_stale: bool = True
        self.total_cache: float = 0.0

        self.multi_start_times: dict[int, float] = {}

    def start(self) -> float:
        if 0 in self.multi_start_times:
            raise RuntimeError("Timer already started")
        self.multi_start_times[0] = time.perf_counter()
        return self.multi_start_times[0]

    def end(self) -> float:
        return self.end_multi(0)

    def start_multi(self) -> int:
        timer_id = _get_next_id()
        self.multi_start_times[timer_id] = time.perf_counter()
        return timer_id

    def end_multi(self, timer_id: int) -> float:
        end_time = time.perf_counter()
        if timer_id not in self.multi_start_times:
            raise RuntimeError(f"Timer {timer_id} not started")
        amount = end_time - self.multi_start_times.pop(timer_id)
        self.times.append(amount)
        self.total_cache_stale = True
        return amount

    def get_running(self) -> list[int]:
        return list(self.multi_start_times.keys())

    def total(self) -> float:
        if self.total_cache_stale:
            self.total_cache = sum(self.times)
            self.total_cache_stale = False
        return self.total_cache

    def reset(self) -> None:
        self.times.clear()
        self.total_cache_stale = True

        self.multi_start_times.clear()


if __name__ == '__main__':
    # simple tests
    from math import trunc

    t = Timer()
    id1 = t.start_multi()
    time.sleep(0.1)
    id2 = t.start_multi()
    time.sleep(0.1)
    elapsed1 = t.end_multi(id1)
    t.start()
    time.sleep(0.1)
    elapsed0 = t.end()
    time.sleep(0.2)
    elapsed2 = t.end_multi(id2)

    assert (trunc(elapsed0 * 1000) == 100)
    assert (trunc(elapsed1 * 1000) == 200)
    assert (trunc(elapsed2 * 1000) == 400)
    assert (trunc(t.total() * 100) == 70)

    try:
        t.end_multi(-1)
        assert False
    except RuntimeError:
        pass
