import pickle
import socket
import threading

HOST = "127.0.0.1"
PORT = 10000


class GameClient:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.isConnected = False

    def run(self):
        self.sock.connect((HOST, PORT))
        self.isConnected = True
        receiver = threading.Thread(target=self.receive_messages, args=())
        receiver.start()

    def receive_messages(self):
        try:
            msg = pickle.loads(self.sock.recv(1024))
            print(msg)
            threading.Thread(target=self.send_messages, args=()).start()
        except:
            print("bye ah.mo")
            self.sock.close()
            self.isConnected = False
        while self.isConnected:
            try:
                msg = pickle.loads(self.sock.recv(1024))
                print(msg)
            except:
                print("bye ah.mo")
                self.sock.close()
                self.isConnected = False

    def send_messages(self):
        while self.isConnected:
            msg = input()
            self.sock.send(pickle.dumps(msg))
            if msg.lower() == "4":
                self.sock.close()
                self.isConnected = False


client = GameClient()
client.run()
