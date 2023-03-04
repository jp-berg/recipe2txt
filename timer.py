import time
import random
from sys import maxsize

def _get_next_id():
    return random.randint(1, maxsize) # 0 reserved

class Timer:
    def __init__(self):
        self.times = []
        self.total_cache_stale = True
        self.total_cache = 0.0
        
        self.multi_start_times = {}
    
    def start(self):
        if 0 in self.multi_start_times:
            raise RuntimeError("Timer already started")
        self.multi_start_times[0] = time.perf_counter()
        return self.multi_start_times[0]
        
    def end(self):
        return self.end_multi(0)
                              
    def start_multi(self):
        timer_id = _get_next_id()
        self.multi_start_times[timer_id] = time.perf_counter()
        return timer_id
        
    def end_multi(self, timer_id):
        end_time = time.perf_counter()
        if timer_id not in self.multi_start_times:
            raise RuntimeError("Timer {} not started".format(timer_id))
        amount = end_time - self.multi_start_times.pop(timer_id)
        self.times.append(amount)
        self.total_cache_stale = True
        return amount
    
    def get_running(self):
        return list(self.multi_start_times.keys())
        
    def total(self):
        if self.total_cache_stale:
            self.total_cache = sum(self.times)
            self.total_cache_stale = False
        return self.total_cache
    
    def reset(self):
        self.times.clear()
        self.invocations = 0
        self.total_cache_stale = True
        
        self.multi_start_times.clear()
        
    
            
