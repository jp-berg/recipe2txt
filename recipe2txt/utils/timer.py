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

import time


class Timer:
    def __init__(self) -> None:
        self.times: list[float] = []
        self.total_cache_stale: bool = True
        self.total_cache: float = 0.0

        self.next_id = 1
        self.multi_start_times: dict[int, float] = {}

    def start(self) -> float:
        if 0 in self.multi_start_times:
            raise RuntimeError("Timer already started")
        self.multi_start_times[0] = time.perf_counter()
        return self.multi_start_times[0]

    def end(self) -> float:
        return self.end_multi(0)

    def _get_next_id(self) -> int:
        next_id = self.next_id
        self.next_id += 1
        return next_id

    def start_multi(self) -> int:
        timer_id = self._get_next_id()
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
        self.next_id = 1
        self.multi_start_times.clear()
