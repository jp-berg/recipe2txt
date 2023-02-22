import time

class Timer:
    def __init__(self):
        self.start_time = 0.0
        self.times = []
        self.total_cache_stale = True
        self.total_cache = 0.0
        
    def start(self):
        if self.start_time != 0.0:
            raise RuntimeError("Timer not finished")
        self.start_time = time.perf_counter()
        return self.start_time
        
    def end(self):
        end_time = time.perf_counter()
        if self.start_time == 0.0:
            raise RuntimeError("Timer not started")
        amount = end_time-self.start_time
        self.start_time = 0.0
        self.times.append(amount)
        self.total_cache_stale = True
        return amount
        
    def total(self):
        if self.total_cache_stale:
            self.total_cache = sum(self.times)
            self.total_cache_stale = False
        return self.total_cache
    
    def reset(self):
        self.start_time = 0.0
        self.times.clear()
        self.invocations = 0
        self.total_cache_stale = True
    
    
            
