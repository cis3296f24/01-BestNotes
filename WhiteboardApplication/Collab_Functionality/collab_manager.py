import ssl
import socket
import threading
import json
import os
import uuid
from pyngrok import ngrok

from qasync import QEventLoop,  asyncSlot, QApplication
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import time
import logging
import websockets
import asyncio
from dataclasses import dataclass, asdict
import select
import stun
from PySide6.QtCore import QObject, Signal, QCoreApplication, QTimer
from WhiteboardApplication.Collab_Functionality.utils import logger
import stun
from WhiteboardApplication.Collab_Functionality.turn_server import TURN_SERVER, TURN_PASSWORD, TURN_USERNAME
from web_rtc_connection import WebRTCConnection, RTCSessionDescription, RTCIceCandidate, DataChannel, \
    RTCIceConnectionState, RTCSignalingState

#install websockets
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to capture all logs
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # Logs will be displayed in the console
)

TURN_CONFIG = {
                "urls": TURN_SERVER,
                "username": TURN_USERNAME,
                "credential": TURN_PASSWORD,
                "credentialType": "password"
        }

STUN_CONFIG = {
        "urls": "stun:stun.l.google.com:19302"
        }


class CollabServer(QObject):
    clientConnected = Signal(object)  # Signal emitted when a client connects
    clientDisconnected = Signal(object)  # Signal emitted when a client disconnects
    STUN_SERVER = "stun:stun.l.google.com:19302"

    def __init__(self, discovery_host="localhost", discovery_port=9000, server_port=5050, user_ip=None, user_port=None,
                 parent=None):
        super().__init__(parent)
        self.discovery_host = discovery_host
        self.discovery_port = discovery_port
        self.server_port = server_port

        self.user_port = user_port
        self.user_ip = user_ip

        self.server_socket = None
        self.clients = []
        self.ssl_key_path = None
        self.ssl_cert_path = None
        self.ssl_context = None
        self.running = False
        self.server_thread = None
        self.peer_connections = None
        self.server_socket_lock = threading.Lock()
        self.websocket_clients = {}  # To store websocket connections for each client
        self.ngrok_tunnel = None
        print(f"Initialized CollabServer with discovery_host: {self.discovery_host}")

        # Initialize the WebRTC connection with TURN server details
        self.webrtc_connection = WebRTCConnection([
            TURN_CONFIG,
            STUN_CONFIG
        ])

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
        if not self.ngrok_tunnel:
            print("Ngrok tunnel is not active. Cannot register with discovery server.")
            return False

        """Register with the discovery server using public IP and port."""
        public_ip = self.user_ip
        public_port = self.user_port
        ngrok_url = self.ngrok_tunnel.public_url

        turn_info = f"{TURN_SERVER} {TURN_USERNAME} {TURN_PASSWORD}"

        if not public_ip or not public_port:
            print("Unable to determine public IP and port. (collab_server)")
            return False

        try:
            with socket.create_connection((self.discovery_host, self.discovery_port)) as s:
                register_message = f"REGISTER {username} {public_ip} {public_port} {turn_info} {ngrok_url}\n"
                s.sendall(register_message.encode())
                response = s.recv(1024).decode().strip()
                print(f"Discovery server response (collab_server): {response}")

                # Check if the response starts with 'OK'
                if response.startswith("OK") or response.startswith("ALREADY_REGISTERED"):
                    return True
                else:
                    print(f"Unexpected response from server (collab_server): {response}")
                    return False
        except Exception as e:
            print(f"Error registering with discovery server (collab_server): {e}")
            return False

    def check_port_in_use(self, port):
        print(f"Checking if port {port} is in use...")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(('0.0.0.0', port))
                print(f"Port {port} is not in use.")
                return False
            except socket.error:
                print(f"Port {port} is already in use.")
                return True

    def start_ngrok_tunnel(self, port):
        print("Attempting to start ngrok tunnel...")
        try:
            self.ngrok_tunnel = ngrok.connect(port)
            print(f"Ngrok tunnel successfully started: {self.ngrok_tunnel.public_url}")
        except Exception as e:
            print(f"Failed to start ngrok tunnel: {e}")
            self.ngrok_tunnel = None

    def start(self, username):
        """Start the CollabServer."""
        self.ssl_key_path, self.ssl_cert_path = self.load_config()
        if not self.ssl_key_path or not self.ssl_cert_path:
            print("SSL configuration is missing. Server cannot start.")
            return

        self.start_ngrok_tunnel(self.user_port)

        if not self.ngrok_tunnel:
            print("Ngrok tunnel could not be established. Exiting.")
            return

        if not self.register_with_discovery(username):
            print("Failed to register with discovery server.")
            return

        # Initialize peer connections dict
        self.peer_connections = {}

        # Initialize WebRTC
        self.webrtc_connection = WebRTCConnection([
            TURN_CONFIG,
            STUN_CONFIG
        ])
        print("WebRTC connection initialized")

        #Check TURN configuration
        if not self.webrtc_connection.ice_servers:
            print("TURN server configuration is missing!")
        else:
            print(f"TURN server is configured: {self.webrtc_connection.ice_servers}")

        # Start the server
        loop = asyncio.get_event_loop()
        loop.create_task(self.start_signaling_server())
        print(f"Signaling server starting on {self.user_ip}:{self.user_port}")

    async def run_asyncio_loop(self):
        """Run the asyncio event loop in the Qt event loop."""
        logging.info("Starting asyncio loop for WebSocket server...")
        try:
            async with websockets.serve(self.handle_signaling, self.user_ip, self.user_port):
                logging.info(f"WebSocket server started for WebRTC signaling on {self.user_ip}:{self.user_port}")
                await asyncio.Future()  # Keep the server running
        except Exception as e:
            logging.error(f"Error in WebSocket server: {e}")

    async def handle_signaling(self, websocket, path):
        client_id = str(uuid.uuid4())
        try:
            async for message in websocket:
                data = json.loads(message)

                if data["type"] == "offer":
                    # Create new peer connection for this client
                    print(f"Received offer from client, creating peer connection...\n")
                    peer_conn = WebRTCConnection(data.get("iceServers", self.webrtc_connection.ice_servers))
                    await self._configure_turn(peer_conn, TURN_CONFIG)
                    logging.info("Configured turn server in handle signaling\n")
                    # Set up event handlers
                    peer_conn.onicecandidate = lambda c: self._on_ice_candidate(websocket, c)
                    peer_conn.ondatachannel = lambda c: self._on_data_channel(client_id, c)

                    # Store the connection
                    self.peer_connections[client_id] = {
                        'connection': peer_conn,
                        'websocket': websocket,
                        'channels': {}
                    }

                    # Set remote description (client's offer)
                    await peer_conn.set_remote_description(
                        RTCSessionDescription(type="offer", sdp=data["sdp"]))

                    peer_conn.oniceconnectionstatechange = lambda: self.on_ice_connection_state_change(peer_conn)
                    if peer_conn.signalingState == 'stable':
                        # Create and send answer
                        answer = await peer_conn.create_answer()
                        await peer_conn.set_local_description(answer)
                        await websocket.send(json.dumps({
                            "type": "answer",
                            "sdp": answer.sdp
                        }))
                    else:
                        print(f"Cannot create offer in {peer_conn.signalingState} state.")

                elif data["type"] == "ice-candidate":
                    if client_id in self.peer_connections:
                        await self.peer_connections[client_id]['connection'].add_ice_candidate(
                            RTCIceCandidate(**data["candidate"]))

        except Exception as e:
            logging.error(f"Error in signaling handler: {e}")
        finally:
            if client_id in self.peer_connections:
                self.peer_connections[client_id]['connection'].close()
                del self.peer_connections[client_id]

    def on_ice_connection_state_change(self, peer_conn):
        state = peer_conn.ice_connection_state
        if state == "failed":
            logging.error("ICE connection failed, trying TURN server...")
        else:
            logging.info(f"ICE connection state: {state}")

    def _on_ice_candidate(self, websocket, candidate):
        if candidate:
            logging.info(f"Sending ICE candidate: {candidate}")
            asyncio.create_task(websocket.send(json.dumps({
                "type": "ice-candidate",
                "candidate": asdict(candidate)
            })))

    async def _configure_turn(self, peer_conn, turn_config):
        """Configure TURN server for the peer connection"""
        try:
            logging.info("Starting to configure turn server\n")
            await peer_conn.add_ice_server(turn_config)
            logging.info("TURN server configured successfully\n")
        except Exception as e:
            logging.error(f"Error configuring TURN server: {e}\n")

    def handle_client(self, client_socket):
        """Handles communication with a new client via a socket."""
        client_id = str(uuid.uuid4())
        self.clients.append(client_socket)
        print(f"New client connected: {client_id}")

        try:
            while True:
                data = client_socket.recv(1024)
                if not data:
                    break  # Client disconnected
                message = data.decode("utf-8")
                print(f"Received message from {client_id}: {message}")
                self._process_client_message(client_socket, message, client_id)
        except Exception as e:
            print(f"Error handling client {client_id}: {e}")
        finally:
            client_socket.close()
            self.clients.remove(client_socket)
            print(f"Client {client_id} disconnected")
            self.clientDisconnected.emit(client_socket)

    def _process_client_message(self, client_socket, message, client_id):
        """Process a message received from the client."""
        try:
            message_data = json.loads(message)
            message_type = message_data.get("type")

            if message_type == "offer":
                # Create new WebRTC peer connection for the offer
                peer_conn = WebRTCConnection(self.webrtc_connection.ice_servers)
                self.peer_connections[client_id] = {"connection": peer_conn, "socket": client_socket}
                asyncio.create_task(self._handle_offer(client_socket, message_data, peer_conn))
            elif message_type == "ice-candidate":
                # Handle ICE candidates
                self._handle_ice_candidate(client_socket, message_data, client_id)
            else:
                print(f"Unknown message type: {message_type}")
        except Exception as e:
            print(f"Error processing message from {client_id}: {e}")

    async def _handle_offer(self, client_socket, message_data, peer_conn):
        """Handle the offer from the client and respond with an answer."""
        try:
            # Configure the peer connection with the offer
            await peer_conn.set_remote_description(RTCSessionDescription(type="offer", sdp=message_data["sdp"]))
            if peer_conn.signalingState == "stable":
                answer = await peer_conn.create_answer()
                await peer_conn.set_local_description(answer)

                # Send answer back to client
                response = {
                    "type": "answer",
                    "sdp": answer.sdp
                }
                await client_socket.send(json.dumps(response))
            else:
                print(f"Cannot create answer: {peer_conn.signalingState}")
        except Exception as e:
            print(f"Error handling offer: {e}")

    def _handle_ice_candidate(self, client_socket, message_data, client_id):
        """Handle an ICE candidate message."""
        try:
            if client_id in self.peer_connections:
                candidate = RTCIceCandidate(**message_data["candidate"])
                peer_conn = self.peer_connections[client_id]["connection"]
                asyncio.create_task(peer_conn.add_ice_candidate(candidate))
                print(f"ICE candidate added for client {client_id}")
        except Exception as e:
            print(f"Error handling ICE candidate for {client_id}: {e}")

    def _on_data_channel(self, client_id, channel):
        """Handles the creation of a data channel for a peer."""
        try:
            print(f"Data channel created for client {client_id}")
            # Example: Set up message handler for the data channel
            channel.onmessage = self._on_data_channel_message(client_id, channel)
            self.peer_connections[client_id]["channels"][channel.label] = channel
        except Exception as e:
            print(f"Error handling data channel for {client_id}: {e}")

    def _on_data_channel_message(self, client_id, channel):
        """Handles messages received on a data channel."""
        def on_message(event):
            """Called when a message is received on the data channel."""
            try:
                message = event.data
                print(f"Message from client {client_id} on data channel: {message}")
                # You can forward the message to other clients if needed
                self.broadcast_message({"type": "data-channel-message", "client_id": client_id, "message": message})
            except Exception as e:
                print(f"Error processing message from data channel for {client_id}: {e}")

        return on_message

    async def broadcast_message(self, message, exclude=None):
        """Broadcast message to all peers except the sender"""
        for client_id, websocket in self.peer_connections.items():
            if client_id != exclude:
                try:
                    await websocket.send(json.dumps(message))
                except Exception as e:
                    print(f"Error broadcasting to {client_id}: {e}")

    async def start_signaling_server(self):
        """Start WebSocket signaling server"""
        try:
            self.websocket_server = await websockets.serve(
                self.handle_signaling,
                '0.0.0.0',  # Listen on all interfaces
                self.user_port,
                ping_interval=None  # Disable ping to prevent timeouts
            )
            print(f"Signaling server started on port {self.user_port}")
        except Exception as e:
            print(f"Failed to start signaling server: {e}")
            raise

    def run_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print(f"Binding server to {self.user_ip}:{self.user_port}")
            self.server_socket.bind(('0.0.0.0', self.user_port))
            self.server_socket.listen(5)
            print(f"Server started on {self.user_ip}:{self.user_port}")
            self.running = True
            while self.running:
                client_socket, addr = self.server_socket.accept()
                print(f"New connection from {addr}")
                threading.Thread(target=self.handle_client, args=(client_socket,)).start()
        except Exception as e:
            print(f"Error running the server: {e}")

    def stop_server(self):
        """Stop the server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print("Server stopped")

class CollabClient(QObject):
    # Qt signals for asynchronous events
    connection_established = Signal()
    connection_failed = Signal(str)
    message_received = Signal(dict)

    def __init__(self, discovery_host="localhost", discovery_port=9000):
        super().__init__()
        self.discovery_host = discovery_host
        self.discovery_port = discovery_port
        self.websocket = None
        self.peer_connection = None
        self.data_channel = None
        self._event_loop = None
        self._running = False

        # Initialize WebRTC connection using TURN servers only
        self.webrtc_connection = WebRTCConnection([
            TURN_CONFIG,
            STUN_CONFIG
        ])

    async def start_async(self):
        """Start the async event loop in the background."""
        self._running = True
        self._event_loop = asyncio.get_event_loop()

    async def connect(self, host_username: str, **kwargs) -> bool:
        try:
            logging.info(f"Attempting connection to {host_username}...")
            self._reset_webrtc_state()

            # Lookup host information
            host_info = await self._lookup_host(host_username)
            if not host_info:
                logging.error(f"Host '{host_username}' lookup failed.")
                return False

            # Unpack the tuple returned by _lookup_host
            ngrok_url, turn_server, turn_username, turn_password = host_info
            logging.info(f"Connecting to Ngrok URL: {ngrok_url}")

            # Extract the TURN server and port from turn_server (which is in "ip:port" format)
            turn_ip, turn_port = turn_server.split(":")

            # Configure TURN server
            turn_config = {
                "urls": f"turn:{turn_ip}:{turn_port}",
                "username": turn_username,
                "password": turn_password,
                "credential": "password",
            }
            self.peer_connection.add_ice_server(turn_config)

            # Proceed with WebRTC signaling
            self.data_channel = self.peer_connection.create_data_channel("signaling")
            self.data_channel.onopen = self._on_data_channel_open
            self.data_channel.onmessage = self._on_message
            self.data_channel.onclose = self._on_channel_close

            # Establish the connection using Ngrok URL
            connection_info = {"type": "connection_request", "target_url": ngrok_url, "sdp": ""}
            logging.info(f"Sending connection request to Ngrok URL: {ngrok_url}.")
            await self._send_through_turn(connection_info)

            # Await connection establishment
            async with asyncio.timeout(30):
                while not self.is_connected():
                    await asyncio.sleep(0.1)

            logging.info("Connection established.")
            return True

        except Exception as e:
            logging.error(f"Connection error: {e}")
            return False

    def _reset_webrtc_state(self):
        """Fully reset WebRTC connection and state."""
        if self.peer_connection:
            try:
                # Close the existing connection gracefully
                self.peer_connection.close()
            except Exception as e:
                logging.error(f"Error closing peer connection: {e}")

        # Clear references
        self.peer_connection = None
        self.data_channel = None

        # Reinitialize the WebRTC connection
        logging.info("Reinitializing WebRTC connection.")
        self.peer_connection = self._initialize_webrtc_connection()
        self.peer_connection.onicecandidate = self._on_ice_candidate
        self.peer_connection.oniceconnectionstatechange = self._on_ice_connection_state_change
        self.peer_connection.ondatachannel = self._on_data_channel

    def _initialize_webrtc_connection(self):
        """Initialize a new WebRTC connection."""
        connection = WebRTCConnection([TURN_CONFIG,
            STUN_CONFIG])  # Adjust this to your specific library's API
        return connection

    async def _send_through_turn(self, data: dict):
        """Send data through TURN server's data channel"""
        if self.data_channel and self.data_channel.readyState == "open":
            try:
                logging.info("Tried to send data through data channel to turn")
                await self.data_channel.send(json.dumps(data))
            except Exception as e:
                logging.error(f"Error sending through TURN: {e}")
                raise

    def is_connected(self) -> bool:
        """Check if we have an established connection"""
        return (self.peer_connection and
                self.peer_connection.iceConnectionState == RTCIceConnectionState.CONNECTED and
                self.data_channel and
                self.data_channel.readyState == "open")

    async def _on_ice_candidate(self, candidate):
        """Handle new ICE candidates"""
        if candidate and self.is_connected():
            await self._send_through_turn({
                "type": "ice-candidate",
                "candidate": asdict(candidate)
            })

    def _on_data_channel_open(self):
        """Handle data channel opening"""
        logging.info("Data channel opened")
        self.connection_established.emit()

    async def _on_ice_connection_state_change(self):
        """Handle ICE connection state changes"""
        state = self.peer_connection.iceConnectionState
        logging.info(f"ICE connection state changed to: {state}")

        if state == RTCIceConnectionState.FAILED:
            self.connection_failed.emit("ICE connection failed")
            logging.error("ICE connection failed. Check TURN server and signaling.")
        elif state == RTCIceConnectionState.CONNECTED:
            logging.info("ICE connection succeeded.")

    async def _on_message(self, message: str):
        """Handle incoming messages"""
        try:
            data = json.loads(message)
            if data["type"] == "answer":
                await self.peer_connection.set_remote_description(
                    RTCSessionDescription(type="answer", sdp=data["sdp"])
                )
            elif data["type"] == "ice-candidate":
                await self.peer_connection.add_ice_candidate(
                    RTCIceCandidate(**data["candidate"])
                )
            else:
                self.message_received.emit(data)
        except Exception as e:
            logging.error(f"Message handling error: {e}")

    async def send_message(self, data: Dict[str, Any]):
        """Send a message through the established connection"""
        if not self.is_connected():
            raise ConnectionError("No established connection")
        await self._send_through_turn(data)

    async def setup_turn_connection(self, turn_server_url: str, username: str, password: str) -> bool:
        if not self.peer_connection:
            logging.error("Peer connection is not initialized.")
            return False

        try:
            turn_config = {
            "urls": turn_server_url,
            "username": username,
            "credential": password}

            logging.info("Configuring TURN server...")
            self.peer_connection.add_ice_server(turn_config)

            # Send TURN config to signaling server for verification (optional)
            if self.websocket:
                logging.info(f"Websocket value is {self.websocket}\n")

                await self.websocket.send(json.dumps({
                    "type": "turn-server",
                    "turn_config": turn_config
                }))
                # Await acknowledgment
                async for message in asyncio.wait_for(self.websocket, timeout=10):
                    data = json.loads(message)
                    if data.get("type") == "turn-ack":
                        logging.info("TURN server acknowledged.")
                        return True

            print(f"Self.websocket value is {self.websocket}\n")
        except asyncio.TimeoutError:
            logging.error("TURN server acknowledgment timed out.")
        except Exception as e:
            logging.error(f"Error configuring TURN server: {e}")
        return False

    async def fallback_to_turn(self):
        RETRY_LIMIT = 3
        retry_count = 0
        while retry_count < RETRY_LIMIT:
            try:
                await asyncio.wait_for(self.setup_turn_connection(TURN_SERVER, TURN_USERNAME, TURN_PASSWORD), timeout=10)
                break
            except asyncio.TimeoutError:
                logging.error(f"TURN connection attempt {retry_count + 1} timed out.")
                retry_count += 1
            except Exception as e:
                retry_count += 1
                logging.error(f"TURN connection attempt {retry_count} failed: {e}")
                if retry_count >= RETRY_LIMIT:
                    raise

    async def _lookup_host(self, username: str) -> Optional[tuple]:
        """
        Enhanced lookup to retrieve Ngrok URL and TURN server details.
        """
        try:
            reader, writer = await asyncio.open_connection(
            self.discovery_host,
            self.discovery_port)

            # Send the lookup request
            writer.write(f"LOOKUP {username}\n".encode())
            await writer.drain()

            # Receive the response
            response = (await reader.readline()).decode().strip()
            writer.close()
            await writer.wait_closed()

            if response == "NOT_FOUND":
                logging.warning(f"Host {username} not found.")
                return None

            # Expecting the format: ip:port,turn_server_credential,ngrok_url
            parts = response.split(",")
            if len(parts) < 3:
                logging.error(f"Unexpected response format: {response}")
                return None

            ip_port = parts[0].strip()  # e.g., '129.32.225.8:51520'
            turn_info = parts[1].strip()  # e.g., '18.116.1.76:3478 public-user public-password'
            ngrok_url = parts[2].strip()  # e.g., 'https://dd03-129-32-225-8.ngrok-free.app'

            # Now we need to extract the TURN server, username, and password from the turn_info
            turn_parts = turn_info.split(" ")
            if len(turn_parts) < 3:
                logging.error(f"Invalid TURN server credentials: {turn_info}")
                return None

            turn_server = turn_parts[0].split(":")[0]  # e.g., '18.116.1.76'
            turn_port = turn_parts[0].split(":")[1]  # e.g., '3478'
            turn_username = turn_parts[1]  # e.g., 'public-user'
            turn_password = turn_parts[2]  # e.g., 'public-password'

            logging.info(
                f"Resolved Ngrok URL: {ngrok_url}, TURN Server: {turn_server}:{turn_port}, TURN Username: {turn_username}")

            return ngrok_url, f"{turn_server}:{turn_port}", turn_username, turn_password

        except Exception as e:
            logging.error(f"Error during host lookup: {e}")
            return None

    def _on_data_channel(self, channel: DataChannel):
        """Handle incoming data channel."""
        logger.info(f"Data channel received: {channel.label}")
        if channel.label == "drawing":
            self.data_channel = channel
            channel.onmessage = self._on_message
            channel.onclose = self._on_channel_close
            self.connection_established.emit()

    def _on_channel_close(self):
        logging.info("Data channel closed. Cleaning up resources.")
        self.data_channel = None
        if self.peer_connection and self.peer_connection.iceConnectionState == 'closed':
            self._reset_webrtc_state()

    async def send_drawing_data(self, data: Dict[str, Any]):
        """Send drawing data through the data channel"""
        if self.data_channel and self.data_channel.readyState == "open":
            try:
                await self.data_channel.send(json.dumps(data))
            except Exception as e:
                print(f"Error sending drawing data: {e}")

    async def close(self):
        """Close all connections."""
        self._running = False
        if self.peer_connection:
            self.peer_connection.close()
        if self.websocket:
            await self.websocket.close()


