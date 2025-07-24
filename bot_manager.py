# bot_manager.py
import multiprocessing
import json
import time
import signal
import os
import logging
from datetime import datetime
from bot import Bot
from system_monitor import SystemMonitor
import psutil

class BotManager:
    def __init__(self, config_path="config.json"):
        self.bots = {}
        self.config = self.load_config(config_path)
        self.output_queue = multiprocessing.Queue()
        
        # 创建日志目录
        self.logs_dir = "logs"
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # 日志收集器进程
        self.log_collector = multiprocessing.Process(target=self.collect_logs)
        self.log_collector.daemon = True
        
        # 系统监控
        self.system_monitor = SystemMonitor()
        self.resource_queue = multiprocessing.Queue()
        # 资源收集器进程
        self.resource_collector = multiprocessing.Process(target=self.collect_resources)
        self.resource_collector.daemon = True
        # 使用 Manager 创建共享字典
        manager = multiprocessing.Manager()
        self.bot_resources = manager.dict()

    def load_config(self, path):
        with open(path, 'r') as f:
            return json.load(f)

    def collect_logs(self):
        """日志收集器进程，将日志写入文件"""
        while True:
            if not self.output_queue.empty():
                log = self.output_queue.get()
                if log == "SHUTDOWN":
                    break
                
                bot_name = log['bot_name']
                log_type = log['type']
                message = log['message']
                
                # 创建假人日志目录
                bot_log_dir = os.path.join(self.logs_dir, bot_name)
                os.makedirs(bot_log_dir, exist_ok=True)
                
                # 写入日志文件
                log_file = os.path.join(bot_log_dir, f"{log_type}.log")
                with open(log_file, 'a', encoding='utf-8') as f:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"[{timestamp}] {message}\n")
            time.sleep(0.1)

    def start_bot(self, name, server, port, password):
        if name in self.bots:
            return False

        command_queue = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=self.run_bot,
            args=(name, server, port, password, command_queue, self.output_queue)
        )
        process.daemon = True
        process.start()
        
        self.bots[name] = {
            'process': process,
            'command_queue': command_queue,
            'server': server,
            'port': port
        }
        return True

def run_bot(self, name, server, port, password, command_queue, output_queue):
    bot = Bot(name, server, port, password, command_queue, output_queue)
    bot.create_bot()
    
    # 获取当前进程ID
    pid = os.getpid()
    
    while bot.is_running:
        try:
            # 获取进程资源使用情况
            process = psutil.Process(pid)
            cpu_percent = process.cpu_percent(interval=0.0)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)  # 转换为MB
            
            # 发送资源数据到队列
            self.resource_queue.put({
                'bot_name': name,
                'pid': pid,
                'cpu': cpu_percent,
                'memory': round(memory_mb, 1),
                'last_update': time.time()
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        time.sleep(1)
        
        # 移除资源记录
        if name in self.bot_resources:
            del self.bot_resources[name]

    def _update_bot_resources(self, name, pid):
        try:
            # 获取进程资源使用情况
            process = psutil.Process(pid)
            cpu_percent = process.cpu_percent(interval=0.0)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)  # 转换为MB
            
            # 更新资源记录
            self.bot_resources[name] = {
                'pid': pid,
                'cpu': cpu_percent,
                'memory': round(memory_mb, 1),
                'last_update': time.time()
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # 进程已结束或无权限访问
            pass

    def stop_bot(self, name):
        if name in self.bots:
            self.bots[name]['command_queue'].put("!STOP!")
            self.bots[name]['process'].join(timeout=5.0)
            
            if self.bots[name]['process'].is_alive():
                self.bots[name]['process'].terminate()  
            del self.bots[name]
            return True
        return False

    def get_bot_list(self):
        return list(self.bots.keys())

    def send_command(self, name, command):
        if name in self.bots:
            self.bots[name]['command_queue'].put(command)
            return True
        return False

    def get_logs(self, name, log_type, lines=100):
        """读取指定日志文件的最后N行"""
        log_file = os.path.join(self.logs_dir, name, f"{log_type}.log")
        if not os.path.exists(log_file):
            return []
        
        try:
            # 读取文件最后N行
            with open(log_file, 'r', encoding='utf-8') as f:
                return f.readlines()[-lines:]
        except Exception as e:
            logging.error(f"读取日志文件失败: {str(e)}")
            return []

    def get_system_usage(self):
        return self.system_monitor.get_usage()
    
    def get_bot_resources(self, name):
        """获取指定假人的资源使用情况"""
        if name in self.bot_resources:
            return self.bot_resources[name].copy()
        return None
    
    def get_all_resources(self):
        """获取所有假人的资源使用情况"""
        return {name: data.copy() for name, data in self.bot_resources.items()}

    def collect_resources(self):
        """资源收集器进程，更新资源使用情况"""
        while True:
            if not self.resource_queue.empty():
                resource_data = self.resource_queue.get()
                if resource_data == "SHUTDOWN":
                    break
                    
                bot_name = resource_data['bot_name']
                self.bot_resources[bot_name] = resource_data
    
    def start(self):
        self.resource_collector.start()
        # 启动系统监控
        self.system_monitor.start()
        
        # 启动日志收集器
        self.log_collector.start()
        
        # 从配置启动初始机器人
        for bot_config in self.config.get('bots', []):
            self.start_bot(
                bot_config['name'],
                bot_config['server'],
                bot_config['port'],
                bot_config.get('password', '')
            )
        
        # 注册退出处理
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        
        # 保持主进程运行
        while True:
            time.sleep(1)

    def shutdown(self, signum, frame):
        # 停止系统监控
        self.system_monitor.stop()
        
        # 停止所有机器人
        for name in list(self.bots.keys()):
            self.stop_bot(name)
        
        # 停止日志收集器
        self.output_queue.put("SHUTDOWN")
        self.log_collector.join()
        
        # 停止资源收集器
        self.resource_queue.put("SHUTDOWN")
        self.resource_collector.join()
            
        exit(0)

if __name__ == "__main__":
    manager = BotManager()
    manager.start()