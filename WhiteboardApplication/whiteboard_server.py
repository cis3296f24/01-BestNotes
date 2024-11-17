import socket
import threading

class WhiteboardServer:
    def __init__(self, host='0.0.0.0', port=12345):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))  # Bind to the specified host and port
        self.server_socket.listen(5)  # Listen for up to 5 client connections
        print(f"Server listening on {host}:{port}")

        self.clients = []  # List to store connected clients

        # Start the accepting connections thread
        self.accept_thread = threading.Thread(target=self.accept_connections)
        self.accept_thread.start()

    def accept_connections(self):
        while True:
            client_socket, client_address = self.server_socket.accept()
            print(f"Connection established with {client_address}")
            self.clients.append(client_socket)
            # Optionally, start a new thread to handle communication with the client
            threading.Thread(target=self.handle_client, args=(client_socket,)).start()

    def handle_client(self, client_socket):
        while True:
            try:
                message = client_socket.recv(1024)
                if not message:
                    break
                # Handle incoming message
                print(f"Received message: {message.decode()}")
            except ConnectionResetError:
                break
        client_socket.close()

# Start the server
if __name__ == "__main__":
    server = WhiteboardServer(host='0.0.0.0', port=12345)  # This starts the server immediately.0.0.0', port=12345)