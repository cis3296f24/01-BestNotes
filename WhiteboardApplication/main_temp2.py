import socket
import threading
import pickle
import sys
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QMainWindow, QGraphicsScene, QGraphicsView, QPushButton, QColorDialog, QVBoxLayout, QWidget, QApplication, QGraphicsTextItem

from WhiteboardApplication.whiteboard_server import WhiteboardServer

# Whiteboard Client class to handle sending and receiving data
class WhiteboardClient(QObject):
    update_drawing_signal = Signal(dict)
    create_text_signal = Signal(dict)

    def __init__(self, host='your-server-ip', port=12345):  # Replace with your public server IP or DNS
        super().__init__()
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((host, port))  # Connect to the server's IP and port
        self.receive_thread = threading.Thread(target=self.receive_data)
        self.receive_thread.start()

    def send_data(self, data):
        self.client_socket.send(pickle.dumps(data))

    def receive_data(self):
        while True:
            data = self.client_socket.recv(1024)
            if data:
                data = pickle.loads(data)
                if data["action"] == "draw":
                    self.update_drawing_signal.emit(data["line"])
                elif data["action"] == "create_text":
                    self.create_text_signal.emit(data["text"])

    def close(self):
        self.client_socket.close()


# Board Scene class to handle drawing and text box creation
class BoardScene(QGraphicsScene):
    def __init__(self, parent=None, client=None):
        super().__init__(parent)
        self.setSceneRect(-500, -500, 1000, 1000)
        self.client = client
        self.drawing = False
        self.previous_position = None
        self.pathItem = None
        self.pen_color = QColor(0, 0, 0)
        self.pen_width = 2
        self.text_boxes = []
        self.current_text_box = None

        self.client.update_drawing_signal.connect(self.update_drawing)
        self.client.create_text_signal.connect(self.create_text_box_from_data)

    def mousePressEvent(self, event):
        scene_pos = event.scenePos()
        if self.current_text_box:
            self.current_text_box.setTextInteractionFlags(Qt.TextEditorInteraction)
            self.addItem(self.current_text_box)
            self.current_text_box = None
        elif event.button() == Qt.LeftButton:
            self.drawing = True
            self.previous_position = scene_pos
            self.pathItem = self.addLine(self.previous_position.x(), self.previous_position.y(),
                                         self.previous_position.x(), self.previous_position.y(), QPen(self.pen_color, self.pen_width))

            drawing_data = {
                "action": "draw",
                "line": {"x1": self.previous_position.x(), "y1": self.previous_position.y(),
                         "x2": self.previous_position.x(), "y2": self.previous_position.y()}
            }
            self.client.send_data(drawing_data)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drawing and self.previous_position:
            scene_pos = event.scenePos()
            self.pathItem.setLine(self.previous_position.x(), self.previous_position.y(),
                                  scene_pos.x(), scene_pos.y())

            drawing_data = {
                "action": "draw",
                "line": {"x1": self.previous_position.x(), "y1": self.previous_position.y(),
                         "x2": scene_pos.x(), "y2": scene_pos.y()}
            }
            self.client.send_data(drawing_data)
            self.previous_position = scene_pos
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drawing = False
        self.previous_position = None
        super().mouseReleaseEvent(event)

    def set_pen_color(self, color):
        self.pen_color = color

    def set_pen_width(self, width):
        self.pen_width = width

    def create_text_box(self):
        text_item = QGraphicsTextItem("Click to edit text")
        text_item.setTextInteractionFlags(Qt.TextEditorInteraction)
        text_item.setDefaultTextColor(self.pen_color)
        self.addItem(text_item)
        self.text_boxes.append(text_item)
        self.current_text_box = text_item

        text_data = {
            "action": "create_text",
            "text": {"x": 100, "y": 100, "text": "Click to edit text"}
        }
        self.client.send_data(text_data)

    def create_text_box_from_data(self, data):
        text_item = QGraphicsTextItem(data["text"])
        text_item.setTextInteractionFlags(Qt.TextEditorInteraction)
        text_item.setDefaultTextColor(self.pen_color)
        text_item.setPos(data["x"], data["y"])
        self.addItem(text_item)

    def update_drawing(self, line_data):
        line = self.addLine(line_data["x1"], line_data["y1"], line_data["x2"], line_data["y2"],
                            QPen(self.pen_color, self.pen_width))


# Main window to display the UI
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Collaborative Whiteboard")
        self.setGeometry(100, 100, 800, 600)

        self.client = WhiteboardClient()
        self.client.main_window = self
        self.scene = BoardScene(self, client=self.client)
        self.view = QGraphicsView(self.scene, self)
        self.setCentralWidget(self.view)

        self.pen_button = QPushButton("Pen", self)
        self.pen_button.clicked.connect(self.select_pen)
        self.color_button = QPushButton("Color", self)
        self.color_button.clicked.connect(self.select_color)
        self.text_button = QPushButton("Text Box", self)
        self.text_button.clicked.connect(self.create_text_box)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.pen_button)
        self.layout.addWidget(self.color_button)
        self.layout.addWidget(self.text_button)

        self.widget = QWidget()
        self.widget.setLayout(self.layout)
        self.setMenuWidget(self.widget)

    def select_pen(self):
        self.scene.set_pen_color(QColor(0, 0, 0))

    def select_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.scene.set_pen_color(color)

    def create_text_box(self):
        self.scene.create_text_box()


if __name__ == '__main__':
    # Start the server in a separate thread
    server = WhiteboardServer()
    server.start()

    # Start the client application
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())