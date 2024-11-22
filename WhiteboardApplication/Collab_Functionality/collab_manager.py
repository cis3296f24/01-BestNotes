import ssl
import socket
import threading
import json
import os
from utils import logger
import time
import select
from PySide6.QtCore import QObject, Signal

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
        print(f"Initialized CollabServer with discovery_host: {self.discovery_host}")

        self.discovery_port = discovery_port
        self.port = server_port
        self.username = None
        self.server_socket_lock = threading.Lock()

    def load_config(self):
        """Load configuration from a JSON file based on the project directory"""
        try:
            # Get the absolute path to this file's directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = current_dir
            while not os.path.exists(os.path.join(project_root, 'config.json')):
                project_root = os.path.dirname(project_root)  # Move up one directory
                if project_root == os.path.dirname(project_root):
                    raise FileNotFoundError("config.json not found in the project directory.")

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
            print(f"Error: Failed to decode JSON from the config file.")
            return None, None

    def register_with_discovery(self, username):
        """Register with the discovery server."""
        with socket.create_connection((self.discovery_host, self.discovery_port)) as s:
            # Send a LOOKUP command to check if the user is already registered
            lookup_message = f"LOOKUP {username}\n"
            s.sendall(lookup_message.encode())
            response = s.recv(1024).decode().strip()
            if response != "NOT_FOUND":
                print(f"User {username} is already registered at {response}.")
                return True  # User is already registered, skip re-registration

            # Proceed with registration if the user is not already registered
            register_message = f"REGISTER {username} {self.port}\n"
            s.sendall(register_message.encode())
            response = s.recv(1024).decode().strip()
            print(f"Discovery server response: {response}")
            return response == "OK"

    '''
    def register_with_discovery(self, username):
        print(f"Discovery host before validation: {self.discovery_host}")

        if not self.discovery_host:
            self.discovery_host = "localhost"  # Fallback to default

        self.username = username
        try:
            # Ensure discovery_host is a valid string
            if not isinstance(self.discovery_host, str) or not self.discovery_host:
                raise ValueError("Invalid discovery host value. Must be a non-empty string.")

            print(f"Discovery host is {self.discovery_host} and port is {self.discovery_port}")

            with socket.create_connection((self.discovery_host, self.discovery_port)) as s:
                print(f"Connecting to discovery server at {self.discovery_host}:{self.discovery_port}")

                # Send a REGISTER command with username and port
                register_message = f"REGISTER {username} {self.port}\n"
                print(f"Sending register message: {register_message}")
                s.sendall(register_message.encode())

                # Receive response from the discovery server
                response = s.recv(1024).decode().strip()
                print(f"Discovery server response: {response}")

                if response != "OK":
                    print(f"Unexpected response from discovery server: {response}")
                    return False
                return True

        except Exception as e:
            print(f"Discovery server registration error (collab_server): {e}")
            return False
    '''
    '''
    def start_server(self):
        """Start the server, binding it to a specific port."""
        while True:
            try:
                # Attempt to create and bind the socket
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.bind(('0.0.0.0', self.port))
                self.server_socket.listen(5)
                print(f"Server started on port {self.port}")
                break  # Successfully started the server, exit the loop
            except OSError as e:
                if e.errno == 98:  # Port is already in use (Linux/Mac)
                    print(f"Error: Port {self.port} is already in use, trying a different port.")
                    self.port += 1  # Increment the port and try again
                else:
                    print(f"Error starting server: {e}")
                    raise  # Re-raise the exception if it's not related to the port

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

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket = self.ssl_context.wrap_socket(self.server_socket, server_side=True)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)

            print(f"Server started on port {self.port} with SSL. (collab_server)")
            while True:
                client_socket, addr = self.server_socket.accept()
                print(f"New connection from {addr} (collab_server)")
                threading.Thread(target=self.handle_client, args=(client_socket,)).start()
        except Exception as e:
            print(f"Server error (collab_server): {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
    '''
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
            print(f"Port {self.port} is already in use, trying a different port.")
            self.port += 1  # Increment the port number

        # Start the server with SSL wrapping and binding
        self.start_server()
    '''
    def start_server(self):
        """Start the server, binding it to a specific port."""
        try:
            # Create the server socket and wrap it with SSL
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket = self.ssl_context.wrap_socket(self.server_socket, server_side=True)

            # Bind the server to the port
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)

            print(f"Server started on port {self.port} with SSL. (collab_server)")

            # Accept client connections and spawn a new thread for each client
            while True:
                client_socket, addr = self.server_socket.accept()
                print(f"New connection from {addr} (collab_server)")
                threading.Thread(target=self.handle_client, args=(client_socket,)).start()

        except Exception as e:
            print(f"Server error (collab_server): {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
    '''
    '''
    def start_server(self):
        """Start the server and handle graceful shutdown."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            print(f"Server started on port {self.port}")

            self.running = True

            def server_thread():
                while self.running:
                    try:
                        client_socket, addr = self.server_socket.accept()
                        print(f"New connection from {addr}")
                        threading.Thread(target=self.handle_client, args=(client_socket,)).start()
                    except Exception as e:
                        if not self.running:
                            break
                        print(f"Server error (collab_server): {e}")

            # Start the server in a separate thread
            threading.Thread(target=server_thread, daemon=True).start()

        except Exception as e:
            print(f"Server startup error: {e}")
        finally:
            self.cleanup()
    '''

    ''''
    def start_server(self):
        """Start the server and handle graceful shutdown."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Enable port reuse
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            print(f"Server started on port {self.port}")

            self.running = True

            def server_thread():
                while self.running:
                    try:
                        if self.server_socket.fileno() == -1:  # Check if the socket is closed
                            print("Server socket is closed, exiting thread.")
                            break
                        client_socket, addr = self.server_socket.accept()
                        print(f"New connection from {addr}")
                        threading.Thread(target=self.handle_client, args=(client_socket,)).start()
                    except Exception as e:
                        if not self.running:
                            break
                        print(f"Server error (collab_server): {e}")
                    except socket.error as se:
                        print(f"Socket error occurred: {se}")

            # Start the server in a separate thread
            threading.Thread(target=server_thread, daemon=True).start()

        except Exception as e:
            print(f"Server startup error: {e}")
        finally:
            self.cleanup()
    '''

    def start_server(self):
        """Start the server and handle graceful shutdown."""
        retry_count = 5
        for _ in range(retry_count):
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Enable port reuse
                self.server_socket.bind(('0.0.0.0', self.port))
                self.server_socket.listen(5)
                print(f"Server started on port {self.port}")
                break  # If successful, break the retry loop
            except OSError as e:
                print(f"Port {self.port} is already in use. Retrying...")
                self.port += 1  # Try the next port number
                if self.port > 65535:
                    print("No available ports left to bind.")
                    return
            except Exception as e:
                print(f"Server startup error: {e}")
                return

        self.running = True
        threading.Thread(target=self.server_thread, daemon=True).start()

    def stop_server(self):
        """Stop the server and cleanup resources."""
        print("Stopping server...")
        self.running = False
        if self.server_socket:
            try:
                print("Closing server socket...")
                self.server_socket.close()  # Close the server socket
                print("Server socket closed.")
            except Exception as e:
                print(f"Error closing server socket: {e}")
        for client in self.clients:
            try:
                print(f"Closing client socket: {client}")
                client.close()  # Close client sockets
            except Exception as e:
                print(f"Error closing client socket: {e}")
        self.clients.clear()
        print("Server stopped.")

    def cleanup(self):
        """Cleanup any resources or threads before exit."""
        if self.server_socket:
            self.server_socket.close()
        for client in self.clients:
            client.close()

        self.clients.clear()
        print("Cleanup completed.")

    def handle_client(self, client_socket):
        """Handle client communication."""
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    print("Client disconnected.")
                    break  # Exit the loop if client disconnects
                print(f"Received data: {data}")
                # Handle the data here
        except Exception as e:
            print(f"Error handling client: {e}")
        finally:
            client_socket.close()
            print("Client socket closed.")
        '''
        """Handle communication with a single client."""
        print(f"Client connected (collab_server): {client_socket.getpeername()}")
        self.clientConnected.emit(client_socket)

        self.clients.append(client_socket)
        try:
            while True:
                if client_socket.fileno() == -1:  # Check if the socket is closed
                    break
                data = client_socket.recv(1024).decode()
                if data.startswith("LOGIN"):
                    username = data.split(" ")[1]
                    print(f"User {username} logged in. (collab_server)")
                    client_socket.sendall("LOGIN_SUCCESS".encode())
                elif data:
                    print(f"Received (collab_server): {data}")
                    self.broadcast(data, client_socket)
                else:
                    break
        except Exception as e:
            print(f"Client error (collab_server): {e}")
        finally:
            self.clients.remove(client_socket)
            if client_socket.fileno() != -1:  # Ensure it's still open
                client_socket.close()
            print(f"Client disconnected (collab_server): {client_socket.getpeername()}")
            self.clientDisconnected.emit(client_socket)
            '''


    '''
    def handle_client(self, client_socket):
        """Handle communication with a single client."""
        # Log the new client connection
        print(f"Client connected (collab_server): {client_socket.getpeername()}")

        # Optional: Trigger the on_client_connected event if defined
        if hasattr(self, 'on_client_connected'):
            try:
                self.on_client_connected(client_socket)
            except Exception as e:
                print(f"Error in on_client_connected handler (collab_server): {e}")

        # Add the client socket to the list of active clients
        self.clients.append(client_socket)
        try:
            while True:
                data = client_socket.recv(1024).decode()
                if data.startswith("LOGIN"):
                    username = data.split(" ")[1]
                    print(f"User {username} logged in. (collab_server)")
                    client_socket.sendall("LOGIN_SUCCESS".encode())
                elif data:
                    print(f"Received (collab_server): {data}")
                    self.broadcast(data, client_socket)
                else:
                    break
        except Exception as e:
            print(f"Client error (collab_server): {e}")
        finally:
            # Remove the client socket from the list and close the connection
            self.clients.remove(client_socket)
            client_socket.close()
            print(f"Client disconnected (collab_server): {client_socket.getpeername()}")
    '''
    def broadcast(self, message, sender_socket):
        """Broadcast a message to all clients except the sender."""
        for client in self.clients:
            if client != sender_socket:
                try:
                    client.sendall(message.encode())
                except Exception as e:
                    print(f"Broadcast error (collab_server): {e}")

    def set_on_client_connected(self, callback):
        self.on_client_connected = callback

class CollabClient:
    def __init__(self, discovery_host="localhost", discovery_port=9000):
        self.discovery_host = discovery_host if isinstance(discovery_host, str) else "localhost"
        self.discovery_port = discovery_port
        self.socket = None

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
                print(f"Connected to discovery server at {host}:{port}")
                response = client_socket.recv(1024).decode()
                print(f"Server response (Collab_client): {response}")
            else:
                print("Connection attempt timed out.")

        except Exception as e:
            print(f"An unexpected error occurred (Collab_client): {e}")
        finally:
            client_socket.close()

    '''
    def connect_to_discovery_server(self):
        host = self.discovery_host if isinstance(self.discovery_host, str) else self.get_host_ip()  # Dynamically resolve the host IP
        port = 9000

        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((host, port))
            print(f"(Collab_client) Connected to discovery server at {host}:{port}")
            response = client_socket.recv(1024).decode()
            print(f"Server response (Collab_client): {response}")
            client_socket.close()
        except ConnectionRefusedError:
            print("Error (Collab_client) : Connection refused. Ensure the discovery server is running.")
        except Exception as e:
            print(f"An unexpected error occurred (Collab_client): {e}")
    '''
    def send_drawing(self, data):
        try:
            if self.socket:
                self.socket.sendall(json.dumps(data).encode())
            else:
                print("Not connected to the server. (Collab_client)")
        except Exception as e:
            print(f"Error sending drawing data (Collab_client): {e}")