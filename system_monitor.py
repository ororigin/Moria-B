# system_monitor.py
import psutil
import time
import multiprocessing

class SystemMonitor:
    def __init__(self, update_interval=2):
        self.update_interval = update_interval
        self.cpu_usage = multiprocessing.Value('d', 0.0)
        self.memory_usage = multiprocessing.Value('d', 0.0)
        self.process = multiprocessing.Process(target=self._monitor)
        self.process.daemon = True
        
    def start(self):
        self.process.start()
        
    def stop(self):
        if self.process.is_alive():
            self.process.terminate()
            
    def _monitor(self):
        while True:
            # 获取CPU占用率（百分比）
            self.cpu_usage.value = psutil.cpu_percent(interval=None)
            
            # 获取内存占用率（百分比）
            memory = psutil.virtual_memory()
            self.memory_usage.value = memory.percent
            
            time.sleep(self.update_interval)
            
    def get_usage(self):
        return {
            'cpu': round(self.cpu_usage.value, 1),
            'memory': round(self.memory_usage.value, 1)
        }