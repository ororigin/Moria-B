# api_server.py
from flask import Flask, request, jsonify
from bot_manager import BotManager
import threading
import time

app = Flask(__name__)
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
    return jsonify({'bots': manager.get_bot_list()})

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
    """获取假人聊天日志的最后100行"""
    lines = request.args.get('lines', default=100, type=int)
    return jsonify({'messages': manager.get_logs(name, 'chat', lines)})

@app.route('/bot/<name>/log', methods=['GET'])
def get_log(name):
    """获取假人系统日志的最后100行"""
    lines = request.args.get('lines', default=100, type=int)
    return jsonify({'messages': manager.get_logs(name, 'log', lines)})

@app.route('/system/usage', methods=['GET'])
def get_system_usage():
    """获取系统整体资源使用情况"""
    return jsonify(manager.get_system_usage())

@app.route('/bot/<name>/resources', methods=['GET'])
def get_bot_resources(name):
    """获取指定假人的资源使用情况"""
    resources = manager.get_bot_resources(name)
    if resources:
        return jsonify(resources)
    return jsonify({'error': '假人不存在或未运行'}), 404

@app.route('/bot/resources', methods=['GET'])
def get_all_resources():
    """获取所有假人的资源使用情况"""
    return jsonify(manager.get_all_resources())

def run_manager():
    manager.start()

if __name__ == '__main__':
    # 在单独线程中启动管理器
    manager_thread = threading.Thread(target=run_manager, daemon=True)
    manager_thread.start()
    
    # 启动Flask应用
    app.run(port=manager.config.get('web_port', 5000), use_reloader=False)