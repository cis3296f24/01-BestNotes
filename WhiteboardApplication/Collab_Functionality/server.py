#Creates the server that will serve as the base to communicate between different users

import socket
import threading

class Server:
    def __init__(self, host='127.0.0.1', port=5555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen(5)
        print(f"Server started on {host}:{port}")
        self.clients = []

    def broadcast(self, data, client_socket):
        """Send data to all connected clients except the sender."""
        for client in self.clients:
            if client != client_socket:
                try:
                    client.sendall(data)
                except:
                    self.clients.remove(client)

    def handle_client(self, client_socket):
        """Receive data from a client and broadcast it."""
        while True:
            try:
                data = client_socket.recv(1024)
                if not data:
                    break
                print("Broadcasting data")
                self.broadcast(data, client_socket)
            except:
                break
        client_socket.close()
        self.clients.remove(client_socket)
        print("Client disconnected")

    def run(self):
        while True:
            client_socket, addr = self.server.accept()
            print(f"Client connected: {addr}")
            self.clients.append(client_socket)
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()

if __name__ == "__main__":
    server = Server()
    server.run()