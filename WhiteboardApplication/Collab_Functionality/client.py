import socket
import threading

class Client:
    def __init__(self, host='127.0.0.1', port=5555):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect((host, port))

    def send(self, data):
        self.client.sendall(data)

    def receive(self, on_data_received):
        while True:
            try:
                data = self.client.recv(1024)
                if not data:
                    break
                on_data_received(data)
            except:
                break
        self.client.close()

    def start_receiving(self, on_data_received):
        threading.Thread(target=self.receive, args=(on_data_received,)).start()