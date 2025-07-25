# bot.py
import time
import threading
from javascript import require, On

class Bot:
    def __init__(self, bot_name: str, server_address: str, port: int, password="ufdbfcir", 
                 command_queue=None, output_queue=None):
        self.mineflayer = require("mineflayer")
        self.is_running = True
        self.bot = None
        self.bot_name = bot_name
        self.server_address = server_address
        self.port = port
        self.password = password
        self.command_queue = command_queue
        self.output_queue = output_queue
        self.command_thread = threading.Thread(target=self._handle_commands)
        if password=="":
            self.password="ufdbfcir"
        
    def create_bot(self):
        try:
            self.bot = self.mineflayer.createBot({
                'host': self.server_address,
                'port': self.port,
                'username': self.bot_name
            })
            self._create_bot_events()
            self.command_thread.start()
            self.print_log(f"假人 {self.bot_name} 已创建")
            return True
        except Exception as e:
            self.print_log(f"创建假人失败: {str(e)}")
            return False

    def _create_bot_events(self):
        bot = self.bot
        ingame_help_content = ['#tpme:传送到你身边 #say [内容]:在聊天栏输出内容 #usecommand [指令(不包含/)]:执行指令 #help [页数]：获得帮助','#minecart:乘坐最近的矿车 #dismount:离开乘骑的实体']

        @On(bot, "messagestr")
        def message_get_handle(this, message, *args):
            self.print_chat(f"[{time.strftime('%m-%d %H:%M:%S', time.localtime())}] {message}")
            if "/reg" in message:
                bot.chat("/reg ufdbfcir ufdbfcir@outlook.com")
                self.print_log(f"假人 {self.bot_name} 已注册")
            if "/l" in message:
                bot.chat(f"/l {self.password}")
                self.print_log(f"假人 {self.bot_name} 已登录")

        @On(bot, "whisper")
        def ingame_command_handle(this, username, message, *args):
            if message[0] == "#":
                command = message[1:].split(' ', 1)
                keyword = command[0]
                content = command[1] if len(command) == 2 else None
                
                if keyword == "usecommand" and content:
                    bot.chat(f"/{content}")
                elif keyword == "tpme":
                    bot.chat(f"/tpa {username}")
                elif keyword == "say" and content:
                    bot.chat(content)
                elif keyword == "help":
                    if not content:
                        bot.chat(f"/w {username} #tpme:传送到你身边 #say [内容]:在聊天栏输出内容 #usecommand [指令(不包含/)]:执行指令 #help [页数]：获得帮助")
                    else:
                        try:
                            page = int(content)
                            if page <= len(ingame_help_content):
                                bot.chat(f"/w {username} {ingame_help_content[page-1]}")
                            else:
                                bot.chat(f"/w {username} 已到尾页")
                        except:
                            bot.chat(f"/w {username} 格式错误")
                elif keyword=="minecart":
                    minecart=bot.nearest_entity(lambda entity: entity.name.lower() == 'minecart')
                    bot.mount(minecart)
                elif keyword=="dismount":
                    bot.dismount()
                else:
                    bot.chat(f"/w {username} 未知指令，输入#help获得指令列表")

        @On(bot, "end")
        def end_bot_handle(this, reason):
            self.print_log(f"假人 {self.bot_name} 关闭: {reason}")
            self.is_running = False

        @On(bot, "death")
        def death_handle(this):
            self.print_log(f"假人 {self.bot_name} 死亡")
            bot.respawn()
            bot.chat("/dback")

        @On(bot, "kicked")
        def kick_handle(this, reason, *args):
            self.print_log(f"假人 {self.bot_name} 被踢出: {reason}")
            self.is_running = False

    def _handle_commands(self):
        while self.is_running:
            if self.command_queue and not self.command_queue.empty():
                command = self.command_queue.get()
                if command == "!STOP!":
                    self.stop()
                else:
                    self.bot.chat(command)
            time.sleep(0.1)

    def use_command(self, command):
        if self.bot:
            self.bot.chat(command)

    def stop(self):
        if self.bot:
            self.bot.quit()
        self.is_running = False

    def print_chat(self, message: str):
        if self.output_queue:
            self.output_queue.put({
                'bot_name': self.bot_name,
                'type': 'chat',
                'message': message
            })

    def print_log(self, message: str):
        if self.output_queue:
            self.output_queue.put({
                'bot_name': self.bot_name,
                'type': 'log',
                'message': message
            })