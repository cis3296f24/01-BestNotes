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

    def __init__(self, discovery_host="localhost", discovery_port=9000, server_port=5050):
        super().__init__()
        self.port = server_port
        self.server_socket = None
        self.clients = []
        self.ssl_key_path = None
        self.ssl_cert_path = None
        self.ssl_context = None
        self.discovery_host = discovery_host
        print(f"Initialized CollabServer with discovery_host (Collab_server): {self.discovery_host}")

        self.discovery_port = discovery_port
        self.port = server_port
        self.username = None
        self.server_socket_lock = threading.Lock()
        self.server_thread = None #Thread to support running server

    def load_config(self):
        """Load configuration from a JSON file based on the project directory"""
        try:
            # Get the absolute path to this file's directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = current_dir
            while not os.path.exists(os.path.join(project_root, 'config.json')):
                project_root = os.path.dirname(project_root)  # Move up one directory
                if project_root == os.path.dirname(project_root):
                    raise FileNotFoundError("config.json not found in the project directory. (Collab_server)")

            config_path = os.path.join(project_root, 'config.json')
            with open(config_path, 'r') as config_file:
                config = json.load(config_file)

            # Ensure the SSL paths are relative to the project root
            ssl_key_path = config.get('ssl_key_path', 'ssl/server.key')
            ssl_cert_path = config.get('ssl_cert_path', 'ssl/server.crt')

            ssl_key_path = os.path.join(project_root, ssl_key_path)
            ssl_cert_path = os.path.join(project_root, ssl_cert_path)

            # Validate that the files exist
            if not os.path.exists(ssl_key_path):
                raise FileNotFoundError(f"SSL key file not found (collab_server): {ssl_key_path}")
            if not os.path.exists(ssl_cert_path):
                raise FileNotFoundError(f"SSL certificate file not found (collab_server): {ssl_cert_path}")

            return ssl_key_path, ssl_cert_path
        except FileNotFoundError as e:
            print(f"Error (collab_server): {str(e)}")
            return None, None
        except json.JSONDecodeError:
            print(f"Error (Collab_server): Failed to decode JSON from the config file.")
            return None, None

    def register_with_discovery(self, username):
        """Register with the discovery server."""
        with socket.create_connection((self.discovery_host, self.discovery_port)) as s:
            # Send a LOOKUP command to check if the user is already registered
            lookup_message = f"LOOKUP {username}\n"
            s.sendall(lookup_message.encode())
            response = s.recv(1024).decode().strip()
            if response != "NOT_FOUND":
                print(f"(Collab_server) User {username} is already registered at {response}.")
                return True  # User is already registered, skip re-registration

            # Proceed with registration if the user is not already registered
            register_message = f"REGISTER {username} {self.port}\n"
            s.sendall(register_message.encode())
            response = s.recv(1024).decode().strip()
            print(f"Discovery server response (Collab_server) : {response}")
            return response == "OK"

    def check_port_in_use(self, port):
        """Check if a port is in use."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('0.0.0.0', port))
            return False  # Port is available
        except socket.error:
            return True  # Port is already in use
        finally:
            sock.close()

    def start(self, username):
        # Load SSL configuration before starting the server
        self.ssl_key_path, self.ssl_cert_path = self.load_config()
        if not self.ssl_key_path or not self.ssl_cert_path:
            print("SSL configuration is missing. Server cannot start. (collab_server)")
            return

        # Register with the discovery server before starting the socket
        if not self.register_with_discovery(username):
            print("Failed to register with discovery server. (collab_server)")
            return

        # Set up SSL context for the server
        self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ssl_context.load_cert_chain(certfile=self.ssl_cert_path, keyfile=self.ssl_key_path)

        # Check if the port is in use and increment if necessary
        while self.check_port_in_use(self.port):
            print(f"Port {self.port} is already in use, trying a different port. (Collab_server)")
            self.port += 1  # Increment the port number

        # Start the server with SSL wrapping and binding
        self.start_server()

    def start_server(self):
        """Start the server and handle graceful shutdown."""
        retry_count = 5
        for _ in range(retry_count):
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Enable port reuse
                self.server_socket.bind(('0.0.0.0', self.port))
                self.server_socket.listen(5)
                print(f"(Collab_server) Server started on port {self.port}")
                break  # If successful, break the retry loop
            except OSError as e:
                print(f"(Collab_server) Port {self.port} is already in use. Retrying...")
                self.port += 1  # Try the next port number
                if self.port > 65535:
                    print("No available ports left to bind. (Collab_server)")
                    return
            except Exception as e:
                print(f"Server startup error (Collab_server): {e}")
                return

        self.running = True
        threading.Thread(target=self.server_thread, daemon=True).start()

    def stop_server(self):
        """Stop the server and cleanup resources."""
        print("(Collab_server) Stopping server...")
        self.running = False
        if self.server_socket:
            try:
                print("(Collab_server) Closing server socket...")
                self.server_socket.close()  # Close the server socket
                print("Server socket closed. (Collab_server)")
            except Exception as e:
                print(f"Error closing server socket (Collab_server): {e}")
        for client in self.clients:
            try:
                print(f"Closing client socket (Collab_server): {client}")
                client.close()  # Close client sockets
            except Exception as e:
                print(f"Error closing client socket (Collab_server): {e}")
        self.clients.clear()
        print("Server stopped.(Collab_server)")

    def cleanup(self):
        """Cleanup any resources or threads before exit."""
        if self.server_socket:
            self.server_socket.close()
        for client in self.clients:
            client.close()

        self.clients.clear()
        print("Cleanup completed.(Collab_server)")

    def handle_client(self, client_socket):
        """Handle client communication."""
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    print("Client disconnected. (Collab_server)")
                    break  # Exit the loop if client disconnects
                print(f"Received data (Collab_server): {data}")
                # Handle the data here
        except Exception as e:
            print(f"Error handling client (Collab_server): {e}")
        finally:
            client_socket.close()
            print("Client socket closed. (Collab_server)")

    def broadcast(self, message, sender_socket):
        """Broadcast a message to all clients except the sender."""
        for client in self.clients:
            if client != sender_socket:
                try:
                    # Send data in smaller chunks if necessary
                    client.sendall(message.encode())
                except Exception as e:
                    print(f"Broadcast error (collab_server): {e}")
                    self.clients.remove(client)

    def set_on_client_connected(self, callback):
        self.on_client_connected = callback

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
        try:
            # Create a socket
            self.client_socket = socket.create_connection((host_address, port), timeout=10)

            # If an SSL context is set, wrap the socket
            if self.ssl_context:
                self.client_socket = self.ssl_context.wrap_socket(
                    self.client_socket,
                    server_hostname=host_address
                )

            # Send the username to authenticate with the server
            auth_message = f"AUTH {username}\n"
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

        if not username:
            print("Error (collab_client): Username must be provided for lookup.")
            return None, None

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                print(f"(Collab_client) Connecting to discovery server at {discovery_server_ip}:{discovery_server_port}")
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
                print(f"(Collab_client)Connected to discovery server at {host}:{port}")
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