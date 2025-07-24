# flask_server_wrapper.py
from werkzeug.serving import make_server
import threading

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