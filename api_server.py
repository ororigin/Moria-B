# api_server.py
import multiprocessing
from flask import Flask, request, jsonify
import threading
import time
import signal
from werkzeug.serving import make_server
from flask_cors import CORS

# 设置多进程启动方法（仅当尚未设置时）
try:
    multiprocessing.set_start_method('spawn')
except RuntimeError:
    # 如果已经设置过启动方法，则忽略
    pass

class FlaskServerWrapper:
    def __init__(self, app, port):
        self.app = app
        self.port = port
        self.server = make_server('0.0.0.0', port, app)
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        print(f"Flask服务器已在端口 {self.port} 启动")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.thread.join()
            print("Flask服务器已停止")

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# 现在导入 BotManager
from bot_manager import BotManager
manager = BotManager()

@app.route('/bot', methods=['POST'])
def create_bot():
    data = request.json
    name = data.get('name')
    server = data.get('server')
    port = data.get('port')
    password = data.get('password', '')
    
    if not all([name, server, port]):
        return jsonify({'success': False, 'error': '缺少必要参数'}), 400
    
    if manager.start_bot(name, server, port, password):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': '假人已存在'}), 400

@app.route('/bot', methods=['GET'])
def list_bots():
    # 获取在线假人
    online_bots = manager.get_bot_list()
    
    # 获取配置中所有假人（包括离线的）
    all_bots = [bot['name'] for bot in manager.config.get('bots', [])]
    
    # 确保所有假人都在列表中
    bots = list(set(online_bots + all_bots))
    
    return jsonify({'bots': bots})

@app.route('/bot/<name>', methods=['DELETE'])
def delete_bot(name):
    if manager.stop_bot(name):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': '假人不存在'}), 404

@app.route('/bot/<name>/command', methods=['POST'])
def send_command(name):
    data = request.json
    command = data.get('command')
    if not command:
        return jsonify({'success': False, 'error': '缺少命令'}), 400
    
    if manager.send_command(name, command):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': '假人不存在'}), 404

@app.route('/bot/<name>/chat', methods=['GET'])
def get_chat(name):
    lines = request.args.get('lines', default=100, type=int)
    return jsonify({'messages': manager.get_logs(name, 'chat', lines)})

@app.route('/bot/<name>/log', methods=['GET'])
def get_log(name):
    lines = request.args.get('lines', default=100, type=int)
    return jsonify({'messages': manager.get_logs(name, 'log', lines)})

@app.route('/system/usage', methods=['GET'])
def get_system_usage():
    return jsonify(manager.get_system_usage())

@app.route('/bot/<name>/resources', methods=['GET'])
def get_bot_resources(name):
    resources = manager.get_bot_resources(name)
    if resources:
        return jsonify(resources)
    return jsonify({'error': '假人不存在或未运行'}), 404

@app.route('/bot/resources', methods=['GET'])
def get_all_resources():
    return jsonify(manager.get_all_resources())

@app.route('/bot/status', methods=['GET'])
def get_all_bots_status():
    bots = manager.get_bot_list()
    statuses = []
    
    for bot_name in bots:
        if bot_name in manager.bots:
            process = manager.bots[bot_name]['process']
            status = 'online' if process.is_alive() else 'offline'
        else:
            status = 'offline'
        
        statuses.append({
            'name': bot_name,
            'status': status
        })
    
    return jsonify({'bots': statuses})

def run_manager():
    manager.start()

if __name__ == '__main__':
    # 在单独线程中启动管理器
    manager_thread = threading.Thread(target=run_manager, daemon=True)
    manager_thread.start()
    
    # 启动Flask应用
    port = manager.config.get('web_port', 5000)
    server = FlaskServerWrapper(app, port)
    server.start()
    
    # 在主线程注册信号处理器
    def shutdown_handler(signum, frame):
        print("收到关闭信号，正在优雅关闭...")
        server.stop()
        manager.shutdown()
        print("关闭完成")
        exit(0)
        
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    # 保持主线程运行
    while True:
        time.sleep(1)