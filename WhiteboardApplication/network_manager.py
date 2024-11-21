import os
import ssl
import socket
import json
import threading

from PySide6.QtGui import QColor, QPen, QPainterPath, QBrush
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsEllipseItem
from PySide6.QtCore import Qt, QRectF

from WhiteboardApplication.text_box import TextBox

class CollabServer:
    def __init__(self, port=5050):
        self.port = port
        self.server_socket = None
        self.clients = []  # List to hold connected clients

        # Load config file to get paths to SSL key and certificate
        self.load_config()

    def load_config(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Parent directory
        config_file = os.path.join(base_dir, 'config.json')

        with open(config_file, 'r') as f:
            config = json.load(f)
            ssl_key_relative_path = config.get('ssl_key_path', 'ssl/server.key')
            ssl_cert_relative_path = config.get('ssl_cert_path', 'ssl/server.crt')

        self.ssl_key_path = ssl_key_relative_path
        self.ssl_cert_path = ssl_cert_relative_path

    def start(self):
        try:
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            context.load_cert_chain(certfile=self.ssl_cert_path, keyfile=self.ssl_key_path)
            context.verify_mode = ssl.CERT_NONE

            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket = context.wrap_socket(self.server_socket, server_side=True)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)

            print(f"Server started on port {self.port} with SSL.")
            while True:
                client_socket, addr = self.server_socket.accept()
                print(f"Connection from {addr}")
                threading.Thread(target=self.handle_client, args=(client_socket,)).start()
        except Exception as e:
            print(f"Server error (network_manager): {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()

    def handle_client(self, client_socket):
        self.clients.append(client_socket)
        try:
            while True:
                data = client_socket.recv(1024).decode()
                if data:
                    print(f"Received (network_manager): {data}")
                    self.broadcast(data, client_socket)  # Send the received data to all clients
                else:
                    break
        except Exception as e:
            print(f"Client error (network_manager): {e}")
        finally:
            self.clients.remove(client_socket)
            client_socket.close()

    def broadcast(self, message, sender_socket):
        """Broadcast message to all clients except the sender."""
        for client in self.clients:
            if client != sender_socket:
                try:
                    client.sendall(message.encode())
                except Exception as e:
                    print(f"Broadcast error (network_manager): {e}")

class CollabClient:
    def __init__(self, server_host="localhost", server_port=5050):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = None

    def connect(self):
        try:
            # Create SSL context and disable certificate verification
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            context.check_hostname = False  # Disable hostname checking
            context.verify_mode = ssl.CERT_NONE  # Disable certificate verification

            # Wrap the socket with the context
            self.socket = context.wrap_socket(
                socket.socket(socket.AF_INET, socket.SOCK_STREAM),
                server_hostname=self.server_host
            )

            # Connect to the server
            self.socket.connect((self.server_host, self.server_port))
            print("Connected to server.")
        except Exception as e:
            print(f"Connection error (network_manager): {e}")

    def send(self, message):
        try:
            self.socket.sendall(message.encode())
            response = self.socket.recv(1024).decode()
            print(f"Server response (network_manager): {response}")
        except Exception as e:
            print(f"Send error (network_manager): {e}")
        finally:
            self.socket.close()
            self.socket = None

    def send_drawing(self, drawing_data):
        print("Send drawing to server here")

    def drawing_received(self, drawing_data):
        """Process drawing data received from the server."""
        print(f"Processing drawing data (network_manager): {drawing_data}")

        # Ensure drawing data has the necessary keys
        if 'type' not in drawing_data or 'data' not in drawing_data:
            print("Invalid drawing data format received.")
            return

        drawing_type = drawing_data['type']
        data = drawing_data['data']

        # Handle drawing updates
        if drawing_type == 'path':
            color = QColor(data['color'])
            size = data['size']
            points = data['points']

            if points:
                path = QPainterPath()
                path.moveTo(points[0][0], points[0][1])  # Start the path at the first point
                for point in points[1:]:
                    path.lineTo(point[0], point[1])  # Add subsequent points to the path

                # Create a QGraphicsPathItem for the drawing
                path_item = QGraphicsPathItem(path)
                pen = QPen(color, size)
                pen.setCapStyle(Qt.RoundCap)
                path_item.setPen(pen)

                # Add the drawing to the board scene
                self.board_scene.addItem(path_item)

        elif drawing_type == 'erase':
            x, y = data['x'], data['y']
            radius = data.get('radius', 10)

            # Create a QRectF to target the eraser's area
            eraser_area = QRectF(x - radius, y - radius, radius * 2, radius * 2)
            items_to_remove = self.board_scene.items(eraser_area)
            for item in items_to_remove:
                self.board_scene.removeItem(item)

        elif drawing_type == 'highlight':
            x, y = data['x'], data['y']
            highlight_color = QColor(255, 255, 0, 50)  # Semi-transparent yellow
            highlight_item = QGraphicsEllipseItem(x - 10, y - 10, 20, 20)
            highlight_item.setBrush(QBrush(highlight_color))
            highlight_item.setPen(Qt.NoPen)
            self.board_scene.addItem(highlight_item)

        elif drawing_type == 'text_box':
            text = data['text']
            x, y = data['x'], data['y']

            # Create and position the text box
            text_box_item = TextBox()
            text_box_item.setPos(x, y)
            self.board_scene.addItem(text_box_item)

        elif drawing_type == 'undo':
            print("Undo")

        elif drawing_type == 'redo':
            print("Redo")

        else:
            print(f"Unknown drawing type received (network_manager): {drawing_type}")