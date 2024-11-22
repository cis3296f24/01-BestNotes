import json
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPen, QPainterPath, QBrush
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsEllipseItem
from WhiteboardApplication.Collab_Functionality.collab_manager import CollabServer, CollabClient
from WhiteboardApplication.text_box import TextBox

class BoardScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.setSceneRect(0, 0, 600, 500)

        self.path = None
        self.previous_position = None
        self.drawing = False
        self.color = QColor("#000000")
        self.size = 1
        self.pathItem = None

        # Tool state
        self.active_tool = None
        self.drawing_enabled = False
        self.highlighting_enabled = False
        self.erasing_enabled = False

        # Undo/Redo
        self.undo_list = []
        self.redo_list = []

        # Collaboration client setup
        #self.collab_client = CollabClient(board_scene=self)
        self.username = None
        self.collab_client = None  # Use passed client or create a new one
        self.collab_server = None  # Default to None
        self.collaborators = []  # List of active collaborators

    def set_username(self, username):
        """Sets the username and initializes collaboration setup."""
        self.username = username
        print(f"Username set for BoardScene: {username}")

        # Trigger collaboration setup now that username is set
        #self.setup_collaboration()

    def set_collab_client(self, collab_client):
        print("Collab client set same as main")
        self.collab_client = collab_client

        self.setup_collaboration()
        
    def setup_collaboration(self):
        """Connect the collaboration client."""
        if not self.username:
            print("Error: Username not set. Cannot initialize collaboration.")
            return

        try:
            # Ensure collab_client is set and connected
            if self.collab_client and self.collab_client.connect_to_discovery_server():
                print(f"Collaboration client connected successfully as {self.username}.")
            else:
                print("Collaboration client failed to connect.")
        except Exception as e:
            print(f"Error setting up collaboration: {e}")

    def change_color(self, color):
        self.color = color

    def change_size(self, size):
        self.size = size

    def set_active_tool(self, tool):
        """Set the currently active tool (pen, eraser, etc.)."""
        self.active_tool = tool

    def add_item_to_undo(self, item):
        """Add an item to the undo stack and clear the redo stack."""
        self.undo_list.append([item])
        self.redo_list.clear()

    def undo(self):
        if self.undo_list:
            item_group = self.undo_list.pop()
            for item in item_group:
                self.removeItem(item)
            self.redo_list.append(item_group)

        self.broadcast_drawing_data({})

    def redo(self):
        if self.redo_list:
            item_group = self.redo_list.pop()
            for item in item_group:
                self.addItem(item)
            self.undo_list.append(item_group)

        self.broadcast_drawing_data({})

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.active_tool == "pen":
                self.drawing = True
                self.path = QPainterPath()
                self.previous_position = event.scenePos()
                self.path.moveTo(self.previous_position)
                self.pathItem = QGraphicsPathItem()
                pen = QPen(self.color, self.size)
                pen.setCapStyle(Qt.RoundCap)
                self.pathItem.setPen(pen)
                self.addItem(self.pathItem)

            elif self.active_tool == "eraser":
                self.erase(event.scenePos())

            elif self.active_tool == "highlighter":
                self.highlight(event.scenePos())

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drawing and self.active_tool == "pen":
            current_position = event.scenePos()
            self.path.lineTo(current_position)
            self.pathItem.setPath(self.path)

            # Broadcast drawing data
            self.broadcast_drawing_data({
                'type': 'path',
                'color': self.color.name(),
                'size': self.size,
                'points': [(self.previous_position.x(), self.previous_position.y()),
                           (current_position.x(), current_position.y())]
            })

            # Send drawing update
            new_path_segment = self.path  # This represents the updated drawing path
            self.send_drawing_update(new_path_segment)

            # Update the previous position
            self.previous_position = current_position

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drawing:
            self.add_item_to_undo(self.pathItem)
            self.drawing = False

        super().mouseReleaseEvent(event)

    def erase(self, position):
        eraser_radius = 10
        items_to_remove = self.items(QRectF(position.x() - eraser_radius, position.y() - eraser_radius,
                                            eraser_radius * 2, eraser_radius * 2))
        for item in items_to_remove:
            self.removeItem(item)

            # Broadcast erasing data
            self.broadcast_drawing_data({
                'type': 'erase',
                'x': position.x(),
                'y': position.y(),
                'radius': eraser_radius
            })

    def highlight(self, position):
        highlight_color = QColor(255, 255, 0, 50)
        highlight_item = QGraphicsEllipseItem(position.x() - 10, position.y() - 10, 20, 20)
        highlight_item.setBrush(QBrush(highlight_color))
        highlight_item.setPen(Qt.NoPen)
        self.addItem(highlight_item)
        self.add_item_to_undo(highlight_item)

        # Broadcast highlighting data
        self.broadcast_drawing_data({
            'type': 'highlight',
            'x': position.x(),
            'y': position.y()
        })

    def add_text_box(self, text_box_item):
        self.addItem(text_box_item)
        self.add_item_to_undo(text_box_item)

        # Broadcast text box data
        self.broadcast_drawing_data({
            'type': 'text_box',
            'text': text_box_item.toPlainText(),
            'x': text_box_item.pos().x(),
            'y': text_box_item.pos().y()
        })

    def broadcast_drawing_data(self, data):
        """Send drawing data to all collaborators."""
        for collaborator in self.collaborators:
            collaborator.send_drawing(data)

    def apply_remote_drawing(self, drawing_data):
        """Apply drawing data received from collaborators."""
        if drawing_data['type'] == 'drawing':
            # Reconstruct the QPainterPath from the points
            path = QPainterPath()
            points = drawing_data['data']['points']
            if points:
                path.moveTo(points[0][0], points[0][1])  # Start the path at the first point
                for point in points[1:]:
                    path.lineTo(point[0], point[1])  # Add subsequent points to the path

            # Set the pen and apply the drawing to the scene
            pen = QPen(QColor(drawing_data['data']['color']), drawing_data['data']['size'])
            path_item = QGraphicsPathItem(path)
            path_item.setPen(pen)
            self.addItem(path_item)

    def send_drawing_update(self, path_segment):
        points = []
        for i in range(path_segment.elementCount()):
            element = path_segment.elementAt(i)
            points.append((element.x, element.y))

        try:
            self.collab_client.send_drawing({
                'type': 'drawing',
                'data': {
                    'points': points,
                    'color': self.color.name(),
                    'size': self.size
                }
            })
        except Exception as e:
            print(f"Error sending drawing update: {e}")