import ssl
import socket
import threading
import json
import os
import time
import select
from PySide6.QtCore import QObject, Signal
from WhiteboardApplication.Collab_Functionality.utils import logger

class CollabServer(QObject):
    clientConnected = Signal(object)  # Signal emitted when a client connects
    clientDisconnected = Signal(object)  # Signal emitted when a client disconnects

    def __init__(self, discovery_host="localhost", discovery_port=9000, server_port=5050, parent=None):
        super().__init__(parent)  # Pass parent to QObject constructor
        self.discovery_host = discovery_host
        self.discovery_port = discovery_port
        self.port = server_port
        self.server_socket = None
        self.clients = []
        self.ssl_key_path = None
        self.ssl_cert_path = None
        self.ssl_context = None
        self.running = False
        self.server_thread = None
        self.server_socket_lock = threading.Lock()
        print(f"Initialized CollabServer with discovery_host: {self.discovery_host}")

    def load_config(self):
        """Load configuration from a JSON file based on the project directory."""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = current_dir
            while not os.path.exists(os.path.join(project_root, 'config.json')):
                project_root = os.path.dirname(project_root)
                if project_root == os.path.dirname(project_root):
                    raise FileNotFoundError("config.json not found in the project directory.")

            config_path = os.path.join(project_root, 'config.json')
            with open(config_path, 'r') as config_file:
                config = json.load(config_file)

            ssl_key_path = os.path.join(project_root, config.get('ssl_key_path', 'ssl/server.key'))
            ssl_cert_path = os.path.join(project_root, config.get('ssl_cert_path', 'ssl/server.crt'))

            if not os.path.exists(ssl_key_path):
                raise FileNotFoundError(f"SSL key file not found: {ssl_key_path}")
            if not os.path.exists(ssl_cert_path):
                raise FileNotFoundError(f"SSL certificate file not found: {ssl_cert_path}")

            return ssl_key_path, ssl_cert_path
        except Exception as e:
            print(f"Error loading configuration: {e}")
            return None, None

    def register_with_discovery(self, username):
        """Register with the discovery server."""
        try:
            with socket.create_connection((self.discovery_host, self.discovery_port)) as s:
                lookup_message = f"LOOKUP {username}\n"
                s.sendall(lookup_message.encode())
                response = s.recv(1024).decode().strip()
                if response != "NOT_FOUND":
                    print(f"User {username} is already registered at {response}.")
                    return True

                register_message = f"REGISTER {username} {self.port}\n"
                s.sendall(register_message.encode())
                response = s.recv(1024).decode().strip()
                print(f"Discovery server response: {response}")
                return response == "OK"
        except Exception as e:
            print(f"Error registering with discovery server: {e}")
            return False

    def check_port_in_use(self, port):
        """Check if a port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(('0.0.0.0', port))
                return False
            except socket.error:
                return True

    def start(self, username):
        """Start the CollabServer."""
        self.ssl_key_path, self.ssl_cert_path = self.load_config()
        if not self.ssl_key_path or not self.ssl_cert_path:
            print("SSL configuration is missing. Server cannot start.")
            return

        if not self.register_with_discovery(username):
            print("Failed to register with discovery server.")
            return

        self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.ssl_context.load_cert_chain(certfile=self.ssl_cert_path, keyfile=self.ssl_key_path)

        while self.check_port_in_use(self.port):
            print(f"Port {self.port} is in use. Trying a different port.")
            self.port += 1

        print("Registered successfully.")
        self.server_thread = threading.Thread(target=self.start_server, daemon=True)
        self.server_thread.start()

    def start_server(self):
        """Start the server socket and accept clients."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('0.0.0.0', self.port))
                sock.listen(5)
                self.server_socket = self.ssl_context.wrap_socket(sock, server_side=True)
                self.running = True
                print(f"Server started on port {self.port} with SSL.")

                while self.running:
                    client_socket, _ = self.server_socket.accept()
                    self.clients.append(client_socket)
                    self.clientConnected.emit(client_socket)
                    threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()
        except Exception as e:
            print(f"Error starting server: {e}")
            self.running = False

    def handle_client(self, client_socket):
        """Handle communication with a client."""
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                print(f"Received: {data.decode()}")
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client_socket.close()
            self.clients.remove(client_socket)
            self.clientDisconnected.emit(client_socket)

    def stop_server(self):
        """Stop the server and clean up resources."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        for client in self.clients:
            client.close()
        self.clients.clear()
        print("Server stopped.")

class CollabClient:
    def __init__(self, discovery_host="localhost", discovery_port=9000):
        self.discovery_host = discovery_host if isinstance(discovery_host, str) else "localhost"
        self.discovery_port = discovery_port
        self.socket = None
        self.client_socket = None
        self.ssl_context = None
        self.running = False

    def connect_to_host(self, host_address, port, username):
        """Connect to the host and send initial authentication details."""
        print(f"(Collab_client) Received host_address={host_address}, port={port}")
        try:
            # Create a socket
            self.client_socket = socket.create_connection((host_address, port), timeout=10)

            # If an SSL context is set, wrap the socket
            if self.ssl_context:
                self.client_socket = self.ssl_context.wrap_socket(
                    self.client_socket,
                    server_hostname=host_address)

            # Send the username to authenticate with the server
            auth_message = f"AUTH {username}\n"
            print(f"Attempting to connect to {host_address}:{port}")
            self.client_socket.sendall(auth_message.encode())

            # Wait for the server's response
            response = self.client_socket.recv(1024).decode().strip()
            if response == "OK":
                print(f"(Collab_client) Successfully connected to {host_address}:{port} as {username}")
                self.running = True

                # Start a thread to listen for incoming data
                threading.Thread(target=self._listen_to_server, daemon=True).start()
                return True
            else:
                print(f"Connection failed (Collab_client): {response}")
                self.client_socket.close()
                return False

        except socket.timeout:
            print(f" (Collab_client) Connection to host {host_address}:{port} timed out.")
            return False
        except Exception as e:
            print(f"(Collab_client) Error connecting to host {host_address}:{port} - {e}")
            if self.client_socket:
                self.client_socket.close()
            return False

    def _listen_to_server(self):
        """Listen for incoming messages from the server."""
        try:
            while self.running:
                data = self.client_socket.recv(1024)
                if not data:
                    print("Disconnected from server. (Collab_client)")
                    self.running = False
                    break

                # Emit a signal with the received data
                self.drawingReceived.emit(data)
        except Exception as e:
            print(f"Error listening to server (Collab_client): {e}")
        finally:
            self.client_socket.close()

    def disconnect(self):
        """Disconnect from the host."""
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception as e:
                print(f"Error closing socket (Collab_client): {e}")

    def connect_with_retry(self, username, max_attempts=3):
        for attempt in range(max_attempts):
            if self.connect(username):
                return True
            logger.warning(f"Connection attempt {attempt + 1} failed, retrying (collab_client)...")
            time.sleep(1)
        return False

    def lookup_host(self, username):
        discovery_server_ip = self.discovery_host if isinstance(self.discovery_host, str) else 'localhost'
        discovery_server_port = self.discovery_port if isinstance(self.discovery_port, int) else 9000
        #print(f"(Collab_client) Connecting to discovery server at {discovery_server_ip}:{discovery_server_port}")
        #print(f"(Collab_client) Discovery server at {self.discovery_host}:{self.discovery_port}")

        if not username:
            print("Error (collab_client): Username must be provided for lookup.")
            return None, None
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                print(f"(Collab_client) Connecting to discovery server at {discovery_server_ip}:{discovery_server_port}")
                print(f"(Collab_client) Discovery server at {self.discovery_host}:{self.discovery_port}")
                sock.connect((discovery_server_ip, discovery_server_port))

                lookup_command = f"LOOKUP {username}\n"
                sock.sendall(lookup_command.encode())
                print(f"Sent LOOKUP command for username (Collab_client): {username}")

                response = sock.recv(1024).decode().strip()
                print(f"Received response from discovery server (Collab_client): {response}")

                if response == "NOT_FOUND":
                    print(f"User '{username}' not found on the discovery server. (Collab_client)")
                    return None, None

                # Ensure the response is valid before attempting to unpack
                if ":" in response:
                    ip, port = response.split(":")
                    print(f"(Collab_client)Lookup result for {username}: {ip}:{port}")
                    return ip.strip(), int(port.strip())
                else:
                    print(f"Error (collab_client): Invalid response format: {response}")
                    return None, None

        except (ValueError, OSError) as e:
            print(f"Error in lookup_host (Collab_client): {e}")
        except socket.timeout:
            print(f"Error (Collab_client): Connection to discovery server at {discovery_server_ip}:{discovery_server_port} timed out.")
        except ConnectionRefusedError:
            print(f"Error (Collab_client): Connection refused by discovery server at {discovery_server_ip}:{discovery_server_port}.")
        except Exception as e:
            print(f"Unexpected error in lookup_host (Collab_client): {e}")

        return None, None

    def connect(self, username):
        try:
            host_info = self.lookup_host(username)
            if not host_info or not all(host_info):
                print(f"(Collab_client) User {username} not found or lookup failed. ")
                return False  # Explicitly indicate failure

            ip, port = host_info
            print(f"(Collab_client) Attempting to connect to {username}'s server at {ip}:{port}.")

            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            self.socket = context.wrap_socket(
                socket.socket(socket.AF_INET, socket.SOCK_STREAM),
                server_hostname=ip)

            self.socket.connect((ip, port))
            print(f" (Collab_client) Connected to {username}'s server at {ip}:{port}.")
            return True

        except Exception as e:
            print(f"Connection error (Collab_client): {e}")
            return False

    def get_host_ip(self):
        try:
            # Use `socket.gethostname()` to resolve the host address
            host_info = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
            for entry in host_info:
                ip = entry[4][0]
                if not ip.startswith("127."):  # Ignore localhost addresses
                    return ip
            print("No external IP found. Defaulting to localhost. (Collab_client)")
            return "127.0.0.1"  # Fallback to localhost

        except Exception as e:
            print(f"Error retrieving host IP (Collab_client): {e}")
            return "127.0.0.1"

    def connect_to_discovery_server(self):
        host = self.discovery_host if isinstance(self.discovery_host, str) else self.get_host_ip()
        port = 9000

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.setblocking(False)  # Set to non-blocking
        try:
            client_socket.connect_ex((host, port))  # Non-blocking connect

            # Use select to wait until the socket is ready for writing (i.e., connected)
            ready_to_read, ready_to_write, in_error = select.select([], [client_socket], [], 5)
            if ready_to_write:
                print(f"(Collab_client) Connected to discovery server at {host}:{port}")
                response = client_socket.recv(1024).decode()
                print(f"Server response (Collab_client): {response}")
            else:
                print("Connection attempt timed out. (Collab_client)")

        except Exception as e:
            print(f"An unexpected error occurred (Collab_client): {e}")
        finally:
            client_socket.close()

    def send_drawing(self, data):
        try:
            if self.socket:
                self.socket.sendall(json.dumps(data).encode())
            else:
                print("Not connected to the server. (Collab_client)")
        except Exception as e:
            print(f"Error sending drawing data (Collab_client): {e}")