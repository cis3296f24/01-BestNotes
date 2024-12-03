import ssl
import socket
import threading
import json
import os
import uuid

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
from web_rtc_connection import WebRTCConnection, RTCSessionDescription, RTCIceCandidate, DataChannel

#install websockets
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to capture all logs
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # Logs will be displayed in the console
)

'''
       self.webrtc_connection = WebRTCConnection(
           ice_servers=[{'urls': TURN_SERVER, 'username': TURN_USERNAME, 'credential': TURN_PASSWORD},
                        {'urls': self.STUN_SERVER}]
       )
       '''

TURN_CONFIG = {
            "urls": TURN_SERVER,
            "username": TURN_USERNAME,
            "credential": TURN_PASSWORD
        }

STUN_CONFIG = {
        "urls": "stun:stun.l.google.com:19302"
        }

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
        self.peer_connections = None
        self.server_socket_lock = threading.Lock()
        self.websocket_clients = {}  # To store websocket connections for each client
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


    def start(self, username):
        """Start the CollabServer."""
        """Start the CollabServer."""
        self.ssl_key_path, self.ssl_cert_path = self.load_config()
        if not self.ssl_key_path or not self.ssl_cert_path:
            print("SSL configuration is missing. Server cannot start.")
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

        # Start the server
        loop = asyncio.get_event_loop()
        loop.create_task(self.start_signaling_server())
        print(f"Signaling server starting on {self.user_ip}:{self.user_port}")
        '''
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

        # Create QApplication instance if it doesn't exist already
        app = QApplication.instance() or QApplication([])

        # Integrate asyncio loop with Qt event loop
        loop = asyncio.get_event_loop()

        # Start the server thread to handle socket communication
        self.server_thread = threading.Thread(target=self.run_server)
        self.server_thread.start()

        # Use QTimer to schedule asyncio tasks within the Qt event loop
        def run_async_tasks():
            loop.run_forever()

        timer = QTimer()
        timer.timeout.connect(run_async_tasks)
        timer.start(50)  # Run every 50ms

        # Start WebSocket server as an asyncio task
        loop.create_task(self.run_asyncio_loop())
        '''

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
        self.peer_connections[client_id] = {
            'websocket': websocket,
            'connection': None
        }

        try:
            async for message in websocket:
                data = json.loads(message)

                if data["type"] == "offer":
                    # Create peer connection for this client
                    peer_conn = self.webrtc_connection
                    peer_conn.onicecandidate = lambda c: self._on_ice_candidate(client_id, c)
                    self.peer_connections[client_id]['connection'] = peer_conn

                    # Set remote description (client's offer)
                    await peer_conn.set_remote_description(
                        RTCSessionDescription(type="offer", sdp=data["sdp"])
                    )

                    # Create and send answer
                    answer = await peer_conn.create_answer()
                    await peer_conn.set_local_description(answer)
                    await websocket.send(json.dumps({
                        "type": "answer",
                        "sdp": answer.sdp
                    }))

                elif data["type"] == "ice-candidate":
                    if self.peer_connections[client_id]['connection']:
                        await self.peer_connections[client_id]['connection'].add_ice_candidate(
                            RTCIceCandidate(**data["candidate"])
                        )

        except Exception as e:
            logging.error(f"Error in signaling handler: {e}")
        finally:
            if client_id in self.peer_connections:
                del self.peer_connections[client_id]

    '''
    async def handle_signaling(self, websocket, path):
        """Handle WebRTC signaling"""
        client_id = str(uuid.uuid4())
        self.peer_connections[client_id] = websocket
        logging.info(f"Client {client_id} connected to signaling server")

        try:
            async for message in websocket:
                data = json.loads(message)
                logging.debug(f"Received message from {client_id}: {data}")

                message_type = data.get('type')
                if message_type == 'offer':
                    await self.broadcast_message(message, exclude=client_id)
                elif message_type == 'answer':
                    if 'target' in data:
                        target_id = data['target']
                        if target_id in self.peer_connections:
                            await self.peer_connections[target_id].send(message)
                elif message_type == 'ice-candidate':
                    await self.broadcast_message(message, exclude=client_id)

        except Exception as e:
            logging.error(f"Error in signaling handler: {e}")
        finally:
            logging.info(f"Client {client_id} disconnected from signaling server")
            del self.peer_connections[client_id]
    '''

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
            print(f"Server bound successfully")
            self.server_socket.listen(5)
            print(f"Server listening on {self.user_ip}:{self.user_port}")
        except socket.error as e:
            print(f"Socket error during server setup: {e}")
            return

        self.running = True
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                print(f"Client connected: {client_address}")
                self.clients.append(client_socket)
                threading.Thread(target=self.handle_client, args=(client_socket,)).start()
            except Exception as e:
                print(f"Error accepting client connection: {e}")

    def handle_client(self, client_socket):
        """Handle communication with a connected client."""
        try:
            while self.running:
                message = client_socket.recv(1024)
                if not message:
                    break
                print(f"Message received from client: {message.decode()}")
                # Handle messages, e.g., send a response
                client_socket.sendall(b"Message received")
        except Exception as e:
            print(f"Error handling client communication: {e}")
        finally:
            self.clients.remove(client_socket)
            client_socket.close()

    def stop(self):
        """Stop the server and close all connections."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        print("Server stopped.")

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

        self.webrtc_connection = WebRTCConnection([
            TURN_CONFIG,
            STUN_CONFIG
        ])

    async def start_async(self):
        """Start the async event loop in the background."""
        self._running = True
        self._event_loop = asyncio.get_event_loop()

    async def connect(self, host_username: str) -> bool:
        try:
            # Look up host
            ip, port = await self._lookup_host(host_username)
            if not ip or not port:
                raise ConnectionError(f"Host '{host_username}' not found.")

            # Connect to signaling server first
            ws_url = f"ws://{ip}:{port}"
            print(f"Trying to connect to WebSocket server at {ws_url}.")
            self.websocket = await websockets.connect(ws_url)

            # Initialize peer connection after websocket is established
            self.peer_connection = self.webrtc_connection
            self.peer_connection.onicecandidate = self._on_ice_candidate
            self.peer_connection.ondatachannel = self._on_data_channel

            # Create data channel after peer connection is initialized
            self.data_channel = self.peer_connection.create_data_channel("drawing")
            self.data_channel.onopen = self._on_data_channel_open
            self.data_channel.onmessage = self._on_message

            # Now create and send offer
            try:
                offer = await self.peer_connection.create_offer()
                await self.peer_connection.set_local_description(offer)

                await self.websocket.send(json.dumps({
                    "type": "offer",
                    "sdp": offer.sdp
                }))
            except Exception as e:
                print(f"Error creating/sending offer: {e}")
                return False

            # Wait for answer with timeout
            try:
                async with asyncio.timeout(10):  # 10 second timeout
                    async for message in self.websocket:
                        data = json.loads(message)
                        if data["type"] == "answer":
                            await self.peer_connection.set_remote_description(
                                RTCSessionDescription(type="answer", sdp=data["sdp"])
                            )
                            return True
                        elif data["type"] == "ice-candidate":
                            await self.peer_connection.add_ice_candidate(
                                RTCIceCandidate(**data["candidate"])
                            )
            except asyncio.TimeoutError:
                raise ConnectionError("Connection timed out waiting for answer")

            return False

        except Exception as e:
            logging.error(f"Connection failed: {e}")
            self.connection_failed.emit(str(e))
            return False

    async def fallback_to_turn(self):
        RETRY_LIMIT = 3
        retry_count = 0
        while retry_count < RETRY_LIMIT:
            try:
                # Set a timeout for the TURN connection setup (e.g., 10 seconds)
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

    async def setup_turn_connection(self, turn_server_url: str, username: str, password: str):
        if not self.websocket:
            logging.error("WebSocket is None. Cannot configure TURN server.")
            return

        try:
            turn_config = {
                "urls": TURN_SERVER,
                "username": TURN_USERNAME,
                "credential": TURN_PASSWORD
            }
            logging.info("Sending TURN configuration to the signaling server.")
            if self.websocket:
                await self.websocket.send(json.dumps({
                    "type": "turn-server",
                    "turn_config": turn_config
                }))
            else:
                raise ConnectionError("WebSocket is not available for TURN configuration.")

            # Wait for acknowledgment of TURN configuration with a timeout (e.g., 10 seconds)
            async for message in asyncio.wait_for(self.websocket, timeout=10):
                data = json.loads(message)
                if data.get("type") == "turn-ack":
                    logging.info("TURN server acknowledged.")
                    break
        except asyncio.TimeoutError:
            logging.error("TURN server acknowledgment timed out.")
            raise
        except Exception as e:
            logging.error(f"Error sending TURN configuration: {e}")
            raise


    async def _lookup_host(self, username: str) -> tuple[Optional[str], Optional[int]]:
        """Lookup host details from discovery server."""
        try:
            reader, writer = await asyncio.open_connection(
                self.discovery_host,
                self.discovery_port
            )
            writer.write(f"LOOKUP {username}\n".encode())
            await writer.drain()

            response = (await reader.readline()).decode().strip()
            writer.close()
            await writer.wait_closed()

            if response == "NOT_FOUND":
                return None, None

            ip, port = response.split(":")
            return ip.strip(), int(port.strip())

        except Exception as e:
            logger.error(f"Lookup error: {str(e)}")
            return None, None

    def _on_ice_candidate(self, candidate: RTCIceCandidate):
        """Handle new ICE candidates."""
        if candidate and self.websocket:
            message = {
                'type': 'candidate',
                'candidate': asdict(candidate)
            }
            asyncio.create_task(self.websocket.send(json.dumps(message)))

    def _on_data_channel_open(self):
        """Handle data channel opening"""
        print("Data channel opened")
        self.connection_established.emit()

    def _on_data_channel(self, channel: DataChannel):
        """Handle incoming data channel."""
        logger.info(f"Data channel received: {channel.label}")
        if channel.label == "drawing":
            self.data_channel = channel
            channel.onmessage = self._on_message
            channel.onclose = self._on_channel_close
            self.connection_established.emit()

    def _on_message(self, message: str):
        """Handle incoming messages."""
        try:
            data = json.loads(message)
            self.message_received.emit(data)
        except Exception as e:
            logger.error(f"Message handling error: {str(e)}")

    def _on_channel_close(self):
        """Handle data channel closure."""
        logger.info("Data channel closed")
        self.data_channel = None

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

    '''
        async def connect(self, host_username: str) -> bool:
            """Establish a connection to the host using WebSocket and attempt P2P setup."""
            try:
                logging.info(f"Looking up host '{host_username}' in discovery server.")
                ip, port = await self._lookup_host(host_username)
                if not ip or not port:
                    raise ConnectionError(f"Host '{host_username}' not found.")

                ws_url = f"ws://{ip}:{port}"
                logging.info(f"Attempting to connect to WebSocket server at {ws_url}.")

                # Set a timeout for the WebSocket connection attempt (e.g., 10 seconds)
                try:
                    self.websocket = await asyncio.wait_for(websockets.connect(ws_url), timeout=10)
                    if not self.websocket:
                        raise ConnectionError("WebSocket connection is None.")
                    logging.info("WebSocket connection established.")
                except asyncio.TimeoutError:
                    logging.error(f"WebSocket connection attempt timed out after 10 seconds.")
                    await self.fallback_to_turn()
                    return False
                except Exception as ws_error:
                    logging.error(f"WebSocket connection failed: {ws_error}")
                    self.websocket = None
                    await self.fallback_to_turn()
                    return False

                 # Handle incoming WebSocket messages and set up WebRTC connection
                async for message in self.websocket:
                    try:
                        data = json.loads(message)
                        logging.debug(f"Received WebSocket message: {data}")

                        if data['type'] == 'answer':
                            logging.info("Received SDP answer. Setting remote description.")
                            await self.peer_connection.set_remote_description(
                                RTCSessionDescription(type='answer', sdp=data['sdp'])
                            )
                            return True
                        elif data['type'] == 'ice-candidate':
                            logging.info("Received ICE candidate. Adding to connection.")
                            await self.peer_connection.add_ice_candidate(
                                RTCIceCandidate(**data['candidate'])
                            )
                            return True

                    except Exception as e:
                        logging.error(f"Error processing WebSocket message: {e}")
                        return False
            except Exception as e:
                logging.error(f"Failed to connect: {e}")
                return False

        '''


