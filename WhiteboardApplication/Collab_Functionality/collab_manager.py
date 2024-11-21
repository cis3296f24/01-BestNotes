import ssl
import socket
import threading
import json
import os

class CollabServer:
    def __init__(self, port=5050):
        self.port = port
        self.server_socket = None
        self.clients = []  # List of connected clients
        self.ssl_key_path, self.ssl_cert_path = self.load_config()
        self.ssl_context = None

    def load_config(self):
        """Load SSL configuration from the project directory."""
        # Find the absolute path to the directory containing collab_manager.py
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Adjust to the parent directory where config.json resides
        base_dir = os.path.abspath(os.path.join(current_dir, "../../"))
        config_file = os.path.join(base_dir, 'config.json')

        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Configuration file not found at: {config_file}")

        with open(config_file, 'r') as f:
            config = json.load(f)

        ssl_key_path = os.path.join(base_dir, config.get('ssl_key_path', 'ssl/server.key'))
        ssl_cert_path = os.path.join(base_dir, config.get('ssl_cert_path', 'ssl/server.crt'))

        if not os.path.exists(ssl_key_path) or not os.path.exists(ssl_cert_path):
            raise FileNotFoundError(f"SSL files not found. Key: {ssl_key_path}, Cert: {ssl_cert_path}")

        return ssl_key_path, ssl_cert_path

    def start(self):
        """Start the SSL-secured server."""
        # Use pre-configured SSL context if provided
        context = self.ssl_context if self.ssl_context else ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=self.ssl_cert_path, keyfile=self.ssl_key_path)

        try:
            # Create and wrap the server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket = context.wrap_socket(self.server_socket, server_side=True)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)

            print(f"Server started on port {self.port} with SSL.")
            while True:
                client_socket, addr = self.server_socket.accept()
                print(f"New connection from {addr}")
                threading.Thread(target=self.handle_client, args=(client_socket,)).start()
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()

    '''
    def handle_client(self, client_socket):
        """Handle communication with a single client."""
        self.clients.append(client_socket)
        try:
            while True:
                data = client_socket.recv(1024).decode()
                if data:
                    print(f"Received: {data}")
                    self.broadcast(data, client_socket)
                else:
                    break
        except Exception as e:
            print(f"Client error: {e}")
        finally:
            self.clients.remove(client_socket)
            client_socket.close()
    '''
    def handle_client(self, client_socket):
        self.clients.append(client_socket)
        try:
            while True:
                data = client_socket.recv(1024).decode()
                if data.startswith("LOGIN"):
                    username = data.split(" ")[1]
                    print(f"User {username} logged in.")
                    client_socket.sendall("LOGIN_SUCCESS".encode())
                elif data:
                    print(f"Received: {data}")
                    self.broadcast(data, client_socket)
                else:
                    break
        except Exception as e:
            print(f"Client error: {e}")
        finally:
            self.clients.remove(client_socket)
            client_socket.close()

    def broadcast(self, message, sender_socket):
        """Broadcast a message to all clients except the sender."""
        for client in self.clients:
            if client != sender_socket:
                try:
                    client.sendall(message.encode())
                except Exception as e:
                    print(f"Broadcast error: {e}")


class CollabClient:
    def __init__(self, server_host="localhost", server_port=5050):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = None

    def connect(self):
        """Establish a connection to the server with SSL."""
        try:
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            self.socket = context.wrap_socket(
                socket.socket(socket.AF_INET, socket.SOCK_STREAM),
                server_hostname=self.server_host
            )
            self.socket.connect((self.server_host, self.server_port))
            print("Connected to server.")
        except Exception as e:
            print(f"Connection error: {e}")

    def send(self, message):
        if not self.socket:
            print("No active connection to the server.")
            return
        try:
            self.socket.sendall(message.encode())
            response = self.socket.recv(1024).decode()
            print(f"Server response: {response}")
        except Exception as e:
            print(f"Send error: {e}")
    '''    
    def send(self, message):
        """Send a message to the server."""
        if not self.socket:
            print("No active connection to the server.")
            return
        try:
            self.socket.sendall(message.encode())
            response = self.socket.recv(1024).decode()
            print(f"Server response: {response}")
        except Exception as e:
            print(f"Send error: {e}")
        finally:
            self.socket.close()
            self.socket = None
    '''

    def send_drawing(self, drawing_data):
        """Send drawing data to the server."""
        if not self.socket:
            print("No active connection to send drawing.")
            return
        try:
            self.socket.sendall(json.dumps(drawing_data).encode())
        except Exception as e:
            print(f"Error sending drawing data: {e}")
