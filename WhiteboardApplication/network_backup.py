from PySide6.QtNetwork import QTcpServer, QTcpSocket, QHostAddress
from PySide6.QtCore import QObject, Signal, QByteArray, QPointF
from PySide6.QtGui import QPainterPath
import json

class CollabServer(QObject):
    clientConnected = Signal(str)
    clientDisconnected = Signal(str)
    drawingReceived = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server = QTcpServer(self)
        self.clients = {}  # {socket: username}
        self.server.newConnection.connect(self._handle_new_connection)

    def start(self, port: int = 5000):
        # Start server on localhost at the specified port
        if not self.server.listen(QHostAddress.LocalHost, port):
            raise RuntimeError(f"Could not start server on port {port}")
        print(f"Server started on port {port}")
        return self.server.serverPort()

    def _handle_new_connection(self):
        socket = self.server.nextPendingConnection()
        print(f"New connection from {socket.peerAddress().toString()}:{socket.peerPort()}")
        socket.readyRead.connect(lambda: self._handle_data(socket))
        socket.disconnected.connect(lambda: self._handle_disconnect(socket))

    def _handle_data(self, socket: QTcpSocket):
        data = socket.readAll().data().decode()
        print(f"Received data from {socket.peerAddress().toString()}: {data}")
        try:
            message = json.loads(data)
            if message['type'] == 'join':
                username = message['username']
                self.clients[socket] = username
                self.clientConnected.emit(username)
                print(f"Client {username} joined.")
            elif message['type'] == 'drawing':
                self.drawingReceived.emit(message['data'])
                self._broadcast(data, exclude=socket)  # Broadcast to all clients except the sender
        except json.JSONDecodeError:
            print("Failed to decode JSON message.")

    def _handle_disconnect(self, socket: QTcpSocket):
        if socket in self.clients:
            username = self.clients[socket]
            del self.clients[socket]
            print(f"Client {username} disconnected.")
            self.clientDisconnected.emit(username)

    def _broadcast(self, data: str, exclude: QTcpSocket = None):
        for socket in self.clients:
            if socket != exclude:  # Don't send back to the sender
                print(f"Broadcasting data to {socket.peerAddress().toString()}")
                socket.write(QByteArray(data.encode()))


class CollabClient(QObject):
    connected = Signal()
    disconnected = Signal()
    drawingReceived = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.socket = QTcpSocket(self)
        self.socket.connected.connect(self.connected)
        self.socket.disconnected.connect(self.disconnected)
        self.socket.readyRead.connect(self._handle_data)
        self.socket.errorOccurred.connect(self._handle_socket_error)

    def connect_to_host(self, host: str = '127.0.0.1', port: int = 5000, username: str = 'Guest'):
        self.username = username
        print(f"Attempting to connect to {host}:{port}...")
        self.socket.connectToHost(host, port)

        # Wait for connection for 1 second
        if self.socket.waitForConnected(1000):
            print(f"Connected to {host}:{port}")
            self._send_message({
                'type': 'join',
                'username': username
            })
            return True
        else:
            print(f"Connection failed: {self.socket.errorString()}")
            return False

    def send_drawing(self, drawing_data: dict):
        if self.socket.isOpen():  # Check if socket is open before sending
            print("Sending drawing data...")
            self._send_message({
                'type': 'drawing',
                'data': drawing_data
            })
        else:
            print("Socket is not open. Cannot send drawing data.")

    def _send_message(self, message: dict):
        # Ensure socket is connected before sending message
        if self.socket.isOpen():
            try:
                json_data = json.dumps(message)
                self.socket.write(QByteArray(json_data.encode()))
            except Exception as e:
                print(f"Error sending message: {e}")
        else:
            print("Socket is not open. Cannot send message.")

    def _handle_data(self):
        buffer = self.socket.readAll().data()
        try:
            messages = buffer.decode().split('\n')
            for msg in messages:
                if msg.strip():
                    message = json.loads(msg)
                    if message['type'] == 'drawing':
                        self.drawingReceived.emit(message['data'])  # Emit signal to update canvas
        except (json.JSONDecodeError, UnicodeDecodeError):
            print("Failed to handle incoming data.")

    def _handle_socket_error(self, error):
        print(f"Socket error occurred: {self.socket.errorString()}")
