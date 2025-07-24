# bot_manager.py
import multiprocessing
import json
import time
import signal
import os
import logging
from datetime import datetime
from system_monitor import SystemMonitor
import psutil

class BotManager:
    def __init__(self, config_path="config.json"):
        self.bots = {}
        self.config = self.load_config(config_path)
        
        # 创建日志目录
        self.logs_dir = "logs"
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # 系统监控
        self.system_monitor = SystemMonitor()
        
        # 延迟初始化多进程对象
        self.output_queue = None
        self.resource_queue = None
        self.log_collector = None
        self.resource_collector = None
        self.bot_resources = None

    def load_config(self, path):
        with open(path, 'r') as f:
            return json.load(f)

    @staticmethod
    def collect_logs(logs_dir, output_queue):
        """日志收集器进程，将日志写入文件"""
        while True:
            if not output_queue.empty():
                log = output_queue.get()
                if log == "SHUTDOWN":
                    break
                
                bot_name = log['bot_name']
                log_type = log['type']
                message = log['message']
                
                # 创建假人日志目录
                bot_log_dir = os.path.join(logs_dir, bot_name)
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
            args=(name, server, port, password, command_queue, self.output_queue, self.resource_queue)
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
        if self.bot_resources and name in self.bot_resources:
            return self.bot_resources[name].copy()
        return None
    
    def get_all_resources(self):
        """获取所有假人的资源使用情况"""
        if self.bot_resources:
            return {name: data.copy() for name, data in self.bot_resources.items()}
        return {}

    @staticmethod
    def collect_resources(bot_resources, resource_queue):
        """资源收集器进程，更新资源使用情况"""
        while True:
            if not resource_queue.empty():
                resource_data = resource_queue.get()
                if resource_data == "SHUTDOWN":
                    break
                    
                bot_name = resource_data['bot_name']
                bot_resources[bot_name] = resource_data
    
    def start(self):
        # 初始化多进程对象
        self.output_queue = multiprocessing.Queue()
        self.resource_queue = multiprocessing.Queue()
        
        # 使用 Manager 创建共享字典
        manager = multiprocessing.Manager()
        self.bot_resources = manager.dict()
        
        # 创建收集器进程
        self.log_collector = multiprocessing.Process(
            target=self.collect_logs, 
            args=(self.logs_dir, self.output_queue),
            daemon=True
        )
        self.resource_collector = multiprocessing.Process(
            target=self.collect_resources, 
            args=(self.bot_resources, self.resource_queue),
            daemon=True
        )
        
        # 启动收集器
        self.log_collector.start()
        self.resource_collector.start()
        
        # 启动系统监控
        self.system_monitor.start()
        
        # 从配置启动初始机器人
        for bot_config in self.config.get('bots', []):
            self.start_bot(
                bot_config['name'],
                bot_config['server'],
                bot_config['port'],
                bot_config.get('password', '')
            )
        

        
        # 保持主进程运行
        while True:
            time.sleep(1)

    def shutdown(self, signum, frame):
        """外部调用的关闭方法"""
        # 原有shutdown方法的内容
        self.system_monitor.stop()
        for name in list(self.bots.keys()):
            self.stop_bot(name)
        if self.output_queue:
            self.output_queue.put("SHUTDOWN")
            self.log_collector.join(timeout=2.0)
        if self.resource_queue:
            self.resource_queue.put("SHUTDOWN")
            self.resource_collector.join(timeout=2.0)
            
        exit(0)
        
    def start_bot(self, name, server, port, password):
        if name in self.bots:
            return False

        command_queue = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=BotManager.run_bot,  # 改为调用静态方法
            args=(name, server, port, password, command_queue, self.output_queue, self.resource_queue)
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

    @staticmethod
    def run_bot(name, server, port, password, command_queue, output_queue, resource_queue):
        # 延迟导入避免父进程问题
        from bot import Bot
        
        bot = Bot(name, server, port, password, command_queue, output_queue)
        bot.create_bot()
        
        pid = os.getpid()
        while bot.is_running:
            try:
                process = psutil.Process(pid)
                cpu_percent = process.cpu_percent(interval=0.0)
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / (1024 * 1024)
                
                resource_queue.put({
                    'bot_name': name,
                    'pid': pid,
                    'cpu': cpu_percent,
                    'memory': round(memory_mb, 1),
                    'last_update': time.time()
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            time.sleep(1)

if __name__ == "__main__":
    manager = BotManager()
    manager.start()