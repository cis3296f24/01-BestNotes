import ssl
import socket
import threading
import json
import os
import time
import websockets
import asyncio
import select
import stun
from PySide6.QtCore import QObject, Signal, QEventLoop, QCoreApplication
from WhiteboardApplication.Collab_Functionality.utils import logger
import stun
from WhiteboardApplication.Collab_Functionality.turn_server import TURN_SERVER, TURN_PASSWORD, TURN_USERNAME
from web_rtc_connection import WebRTCConnection

#install websockets

class CollabServer(QObject):
    clientConnected = Signal(object)  # Signal emitted when a client connects
    clientDisconnected = Signal(object)  # Signal emitted when a client disconnects
    STUN_SERVER = "stun:stun.l.google.com:19302"

    def __init__(self, discovery_host="localhost", discovery_port=9000, server_port=5050, user_ip=None, user_port=None, parent=None):
        super().__init__(parent)
        self.discovery_host = discovery_host
        self.discovery_port = discovery_port
        self.server_port = server_port

        self.user_port =user_port
        self.user_ip = user_ip

        self.server_socket = None
        self.clients = []
        self.ssl_key_path = None
        self.ssl_cert_path = None
        self.ssl_context = None
        self.running = False
        self.server_thread = None
        self.server_socket_lock = threading.Lock()
        self.websocket_clients = {}  # To store websocket connections for each client
        print(f"Initialized CollabServer with discovery_host: {self.discovery_host}")

        # Initialize the WebRTC connection with TURN server details
        self.webrtc_connection = WebRTCConnection(
            ice_servers=[{'urls': TURN_SERVER, 'username': TURN_USERNAME, 'credential': TURN_PASSWORD},
                         {'urls': self.STUN_SERVER}]
        )

    def get_public_ip_and_port(self):
        """Get the public IP and port using a STUN server."""
        try:
            # Use STUN to determine the public IP and port
            nat_type, external_ip, external_port = stun.get_ip_info(stun_host=self.STUN_SERVER)
            print(f"(Collab_server) Public IP: {external_ip}, Public Port: {external_port}")
            return external_ip, external_port
        except Exception as e:
            print(f"(Collab_Server) Error getting public IP and port: {e}")
            return None, None

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
            print(f"Error loading configuration (collab_server): {e}")
            return None, None

    def register_with_discovery(self, username):
        """Register with the discovery server using public IP and port."""
        public_ip = self.user_ip
        public_port = self.user_port
        turn_info = f"{TURN_SERVER} {TURN_USERNAME} {TURN_PASSWORD}"

        if not public_ip or not public_port:
            print("Unable to determine public IP and port. (collab_server)")
            return False

        try:
            with socket.create_connection((self.discovery_host, self.discovery_port)) as s:
                register_message = f"REGISTER {username} {public_ip} {public_port} {turn_info}\n"
                s.sendall(register_message.encode())
                response = s.recv(1024).decode().strip()
                print(f"Discovery server response (collab_server): {response}")

                # Check if the response starts with 'OK'
                if response.startswith("OK"):
                    return True
                else:
                    print(f"Unexpected response from server (collab_server): {response}")
                    return False
        except Exception as e:
            print(f"Error registering with discovery server (collab_server): {e}")
            return False

    def check_port_in_use(self, port):
        """Check if a port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(('0.0.0.0', port))
                return False
            except socket.error:
                return True

    async def handle_signaling(self, websocket, path):
        """Handle WebRTC signaling over WebSocket."""
        print(f"New WebSocket client connected (collab_server_: {path}")
        self.websocket_clients[path] = websocket

        try:
            async for message in websocket:
                print(f"Received signaling message (collab_server): {message}")
                # Handle signaling messages like 'offer', 'answer', 'candidate'
                if message:
                    for client_path, client_ws in self.websocket_clients.items():
                        if client_path != path:
                            await client_ws.send(message)
        except Exception as e:
            print(f"Error in signaling (collab_server_: {e}")
        finally:
            del self.websocket_clients[path]
            print(f"Client disconnected (collab_server): {path}")

    def start(self, username):
        """Start the CollabServer."""
        self.ssl_key_path, self.ssl_cert_path = self.load_config()
        if not self.ssl_key_path or not self.ssl_cert_path:
            print("SSL configuration is missing. Server cannot start. (collab_server)")
            return

        if not self.register_with_discovery(username):
            print("Failed to register with discovery server. (collab_server)")
            return

        self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.ssl_context.load_cert_chain(certfile=self.ssl_cert_path, keyfile=self.ssl_key_path)

        while self.check_port_in_use(self.server_port):
            print(f"Port {self.server_port} is in use. Trying a different port. (collab_server)")
            self.server_port += 1

        print("Registered successfully. (collab_server)")
        self.server_thread = threading.Thread(target=self.run_server)
        self.server_thread.start()

        # Create QApplication instance if it doesn't exist already
        app = QCoreApplication.instance() or QCoreApplication([])

        # Run WebSocket server in asyncio loop without using QEventLoop
        async def start_websocket_server():
            start_server = await websockets.serve(self.handle_signaling, "localhost", 8765)
            print("WebSocket server started for WebRTC signaling. (collab_server)")
            await start_server.wait_closed()  # Keep the server running

        # Create and run asyncio loop in its own thread
        loop = asyncio.new_event_loop()  # Create a new asyncio event loop
        threading.Thread(target=self.run_asyncio_loop, args=(loop, start_websocket_server)).start()

        # Start the Qt application event loop (this doesn't block the asyncio loop)
        app.exec_()

    def run_asyncio_loop(self, loop, start_websocket_server):
        """Run the asyncio event loop in a separate thread."""
        asyncio.set_event_loop(loop)  # Set the event loop in the new thread
        loop.run_until_complete(start_websocket_server())

    def run_server(self):
        """Run the server, handle client connections, and manage socket events."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('0.0.0.0', self.server_port))
        self.server_socket.listen(5)  # Max clients in the listening queue

        print(f"Server listening on port (collab_server) {self.server_port}")

        self.running = True
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                print(f"Client connected (collab_server): {client_address}")
                self.clients.append(client_socket)

                # Handle the new client in a separate thread
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_thread.start()
            except Exception as e:
                print(f"Error while accepting client (collab_server): {e}")
                continue

        self.server_socket.close()

    def handle_client(self, client_socket):
        """Handle communication with a connected client."""
        try:
            while self.running:
                message = client_socket.recv(1024)
                if not message:
                    break
                print(f"Message from client: {message.decode()}")
                # Handle the received message here, like forwarding to other clients
        except Exception as e:
            print(f"Error with client communication: {e}")
        finally:
            client_socket.close()
            print("Client disconnected.")

    def stop(self):
        """Stop the server and close all connections."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print("Server stopped.")

# Example usage:
if __name__ == "__main__":
    server = CollabServer()
    server.start(username="Sample_User")

class CollabClient:
    def __init__(self, discovery_host="localhost", discovery_port=9000, stun_server="stun:stun.l.google.com:19302", turn_server=TURN_SERVER):
        self.discovery_host = discovery_host
        self.discovery_port = discovery_port
        self.stun_server = stun_server
        self.turn_server = turn_server
        self.socket = None
        self.client_socket = None
        self.ssl_context = None
        self.running = False
        self.peer_connection = None
        self.websocket = None

    def get_public_ip(self):
        """Use STUN to get the public IP address."""
        try:
            nat_type, external_ip, external_port = stun.get_ip_info(self.stun_server, 3478)
            if external_ip:
                print(f"Detected public IP (collab_client): {external_ip}")
                return external_ip, external_port
            else:
                print("Unable to detect public IP using STUN. (collab_client)")
                return None, None
        except Exception as e:
            print(f"STUN error (collab_client): {e}")
            return None, None

    def connect_to_turn_server(self):
        """Connect to the TURN server for relay."""
        """Provide TURN server details for ICE configuration."""
        try:
            print(f"Using TURN server {self.turn_server} for relay. (collab_client)")
            return self.turn_server, 3478  # Default TURN server port
        except Exception as e:
            print(f"TURN configuration error (collab_client): {e}")
            return None, None

    async def connect_to_websocket(self, server_url):
        """Connect to WebSocket server for WebRTC signaling."""
        try:
            self.websocket = await websockets.connect(server_url)
            print(f"Connected to WebSocket server at {server_url} (collab_client)")
        except Exception as e:
            print(f"Error connecting to WebSocket server (collab_client): {e}")

    async def send_message(self, message):
        """Send a message over WebSocket."""
        try:
            await self.websocket.send(json.dumps(message))
            print(f"Sent message (collab_client): {message}")
        except Exception as e:
            print(f"Error sending message (collab_client): {e}")

    def create_peer_connection(self):
        """Create WebRTC peer connection with STUN and TURN servers."""
        ice_servers = [
            {'urls': f"stun:{self.stun_server}"},
            {
                'urls': f"turn:{self.turn_server}",
                'username': TURN_USERNAME,
                'credential': TURN_PASSWORD,
            },
        ]
        self.peer_connection = WebRTCConnection(ice_servers)
        print("Created WebRTC PeerConnection. (collab_client)")
        self.peer_connection.onicecandidate = self.on_ice_candidate
        self.peer_connection.ondatachannel = self.on_data_channel

    def on_ice_candidate(self, candidate):
        """Handle new ICE candidates."""
        if candidate:
            message = {'type': 'candidate', 'candidate': candidate}
            print(f"Sending ICE candidate (collab_client): {candidate}")
            threading.Thread(target=asyncio.run, args=(self.send_message(message),)).start()

    def on_data_channel(self, data_channel):
        """Handle incoming data channel."""
        print("Data channel established. (collab_client)")
        data_channel.onmessage = self.on_message_received

    def on_message_received(self, message):
        """Handle incoming messages from data channel."""
        print(f"Received message (collab_client): {message}")
        # Handle collaboration messages here

    def connect(self, username):
        """Connect to the host using WebRTC and TURN."""
        try:
            # Lookup host info
            ip, port = self.lookup_host(username)
            if not ip or not port:
                print(f"User {username} not found. (collab_client)")
                return False

            # Connect to WebSocket signaling server
            signaling_server_url = f"ws://{ip}:{port}/ws"
            asyncio.run(self.connect_to_websocket(signaling_server_url))

            # Create WebRTC connection
            self.create_peer_connection()
            print("WebRTC setup initiated. (collab_client)")
            return True
        except Exception as e:
            print(f"Connection error (collab_client): {e}")
            return False


    def lookup_host(self, username):
        """Query discovery server for host details."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((self.discovery_host, self.discovery_port))
                sock.sendall(f"LOOKUP {username}\n".encode())
                response = sock.recv(1024).decode().strip()
                if response == "NOT_FOUND":
                    return None, None

                ip, port = response.split(":")
                return ip.strip(), int(port.strip())
        except Exception as e:
            print(f"Lookup failed (collab_client): {e}")
            return None, None

    def disconnect(self):
        """Disconnect from WebRTC and WebSocket."""
        self.running = False
        if self.websocket:
            try:
                asyncio.run(self.websocket.close())
                print("Closed WebSocket connection. (collab_client)")
            except Exception as e:
                print(f"Error closing WebSocket (collab_client): {e}")

        if self.peer_connection:
            try:
                self.peer_connection.close()
                print("Closed WebRTC PeerConnection. (collab_client)")
            except Exception as e:
                print(f"Error closing WebRTC connection (collab_client): {e}")