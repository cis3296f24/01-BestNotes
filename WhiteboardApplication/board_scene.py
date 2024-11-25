import json
from PySide6.QtCore import QPointF, QRectF, Qt, QSizeF
from PySide6.QtGui import QColor, QPen, QPainterPath, QBrush, QTransform
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsEllipseItem
from WhiteboardApplication.Collab_Functionality.collab_manager import CollabServer, CollabClient
from WhiteboardApplication.text_box import TextBox
from WhiteboardApplication.video_player import MediaPlayer

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

        #Added flags to check which button is being pressed, and if text boxes are being dragged
        self.is_text_box_selected = False
        self.dragging_text_box = False
        self.drawing_enabled = False
        self.highlighting_enabled = False
        self.erasing_enabled = False
        self.active_tool = None

        # Undo/Redo
        self.undo_list = []
        self.redo_list = []
        self.highlight_items = []
        self.i = 1
        self.highlight_radius_options = [10, 20, 30, 40]
        self.highlight_radius = 10

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
        """Add a single item or group of items to the undo list and clear redo list"""
        # Clear redo list to ensure correct redo functionality
        self.redo_list.clear()

        # Add item (or list of items if it's a group) to the undo list
        self.undo_list.append([item])
        print("Added to undo:", item)

    #Pops action of undo stack to undo, and adds it to redo in case user wants to redo the action
    def undo(self):
        if not self.undo_list:
            print("Undo list is empty")
            return

        # Pop the last group of items from the undo stack
        item_group = self.undo_list.pop()
        for item in item_group:
            self.removeItem(item)
            print("Removed from scene (undo):", item)

        # Push the removed items to the redo stack
        self.redo_list.append(item_group)
        print("Added to redo stack:", item_group)


        self.broadcast_drawing_data({})

    #Pops an action off the redo stack and adds it back to undo to redo and action
    def redo(self):
        if not self.redo_list:
            print("Redo list is empty")
            return

        # Pop the last group of items from the redo stack
        item_group = self.redo_list.pop()
        for item in item_group:
            self.addItem(item)
            print("Added back to scene (redo):", item)

        # Push the redone items back to the undo stack
        self.undo_list.append(item_group)
        print("Restored to undo stack:", item_group)

        self.broadcast_drawing_data({})

    def highlight(self, position):
        highlight_color = QColor(255, 255, 0, 10)
        highlight_brush = QBrush(highlight_color)
        highlight_circle = QGraphicsEllipseItem(position.x() - self.highlight_radius,position.y() - self.highlight_radius,self.highlight_radius * 2,self.highlight_radius * 2)

        highlight_circle.setBrush(highlight_brush)
        highlight_circle.setPen(Qt.NoPen)

        self.addItem(highlight_circle)
        self.highlight_items.append(highlight_circle)

    def open_video_player(self):
        print("Video button clicked")
        self.player = MediaPlayer()
        self.player.show()
        self.player.resize(640, 480)

    def erase(self, position):
        eraser_radius = 10

        #Creates a 20 x 20 rectangle, using the current position and moving further left and up to set the left corner of the rectangle
        erase_item = self.items(QRectF(position - QPointF(eraser_radius, eraser_radius), QSizeF(eraser_radius * 2, eraser_radius * 2)))

        #Removes all items within the rectangle
        for item in erase_item:
            if item in self.highlight_items:
                self.removeItem(item)
                self.highlight_items.remove(item)
            elif isinstance(item, QGraphicsPathItem):
                self.removeItem(item)

                # Broadcast erasing data
            self.broadcast_drawing_data({
                'type': 'erase',
                'x': position.x(),
                'y': position.y(),
                'radius': eraser_radius
            })

    def highlight(self, position):
        highlight_color = QColor(255, 255, 0, 10)
        highlight_brush = QBrush(highlight_color)
        highlight_circle = QGraphicsEllipseItem(position.x() - self.highlight_radius,position.y() - self.highlight_radius,self.highlight_radius * 2,self.highlight_radius * 2)

        highlight_circle.setBrush(highlight_brush)
        highlight_circle.setPen(Qt.NoPen)

        self.addItem(highlight_circle)
        self.highlight_items.append(highlight_circle)

        # Broadcast highlighting data
        self.broadcast_drawing_data({
            'type': 'highlight',
            'x': position.x(),
            'y': position.y()
        })

    def add_text_box(self, text_box_item):
        self.addItem(text_box_item)
        self.add_item_to_undo(text_box_item)  # For complex items, group with handles if needed
        print("TextBox added to scene:", text_box_item)

        # Broadcast text box data
        self.broadcast_drawing_data({
            'type': 'text_box',
            'text': text_box_item.toPlainText(),
            'x': text_box_item.pos().x(),
            'y': text_box_item.pos().y()
        })

    def add_image(self, pixmap_item):
        self.addItem(pixmap_item)
        self.add_item_to_undo(pixmap_item)
        print("Image added to scene:", pixmap_item)

    #Used to turn drawing on or off so it doesn't interfere with dragging text boxes
    def enable_drawing(self, enable):
        self.drawing_enabled = enable
        # Ensure eraser is off when drawing is on
        if enable:
            self.erasing_enabled = False
            self.highlighting_enabled = False

    #Used to turn eraser on or off so it doesn't interfere with dragging text boxes
    def enable_eraser(self, enable):
        self.erasing_enabled = enable
        # Ensure drawing is off when erasing is on
        if enable:
            self.drawing_enabled = False
            self.highlighting_enabled = False

    def enable_highlighter(self, enable):
        self.highlighting_enabled = enable
        if enable:
            self.drawing_enabled = False
            self.erasing_enabled = False

    def mousePressEvent(self, event):
        item = self.itemAt(event.scenePos(), QTransform())
        print(f"Active Tool: {self.active_tool}")  # Debugging print

        if event.button() == Qt.LeftButton:
            if isinstance(item, TextBox):
                print("Box selected")
                self.drawing = False
                self.is_text_box_selected = True
                self.selected_text_box = item
                self.start_pos = event.scenePos()  # Store the start position for dragging
                self.dragging_text_box = True
            else:
                if self.active_tool == "pen":
                    print("Pen tool active")
                    self.drawing = True
                    self.path = QPainterPath()
                    self.previous_position = event.scenePos()
                    self.path.moveTo(self.previous_position)
                    self.pathItem = QGraphicsPathItem()
                    my_pen = QPen(self.color, self.size)
                    my_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    self.pathItem.setPen(my_pen)
                    self.addItem(self.pathItem)
                elif self.active_tool == "highlighter":
                    print("Highlight tool active")
                    self.drawing = False
                    self.highlight(event.scenePos())
                elif self.active_tool == "eraser":
                    print("Eraser tool active")
                    self.drawing = False
                    self.erase(event.scenePos())
                elif self.active_tool == "cursor":
                    print("Cursor active")
                    self.drawing = False
        elif event.button() == Qt.RightButton:
            self.active_tool = "highlighter"
            self.drawing = False
            self.highlight(event.scenePos())

            self.highlight_radius = self.highlight_radius_options[self.i]
            self.i += 1

            if self.i >= len(self.highlight_radius_options):
                self.i = 0

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging_text_box and self.selected_text_box:
            self.drawing = False
            print("Dragging box")
            delta = event.scenePos() - self.start_pos
            self.selected_text_box.setPos(self.selected_text_box.pos() + delta)
            self.start_pos = event.scenePos()
        elif self.drawing:
            print("drawing")
            curr_position = event.scenePos()
            self.path.lineTo(curr_position)
            self.pathItem.setPath(self.path)
            self.previous_position = curr_position

            # Broadcast drawing data
            self.broadcast_drawing_data({
                'type': 'path',
                'color': self.color.name(),
                'size': self.size,
                'points': [(self.previous_position.x(), self.previous_position.y()),
                       (curr_position.x(), curr_position.y())]
            })

            # Send drawing update
            new_path_segment = self.path  # This represents the updated drawing path
            self.send_drawing_update(new_path_segment)

            # Update the previous position
            self.previous_position = curr_position

        elif self.active_tool == "highlighter":
            print("highlighting")
            self.highlight(event.scenePos())

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.dragging_text_box:
                print("Finished dragging box")
                self.dragging_text_box = False
            elif self.drawing:
                # Add the completed path to the undo stack when drawing is finished so it can be deleted or added back with undo
                self.add_item_to_undo(self.pathItem)
                print("Path item added to undo stack:", self.pathItem)
            elif self.highlight:
                self.add_item_to_undo(self.pathItem)
                print("Path item added to undo stack:", self.pathItem)
            self.drawing = False
            self.is_text_box_selected = False

        super().mouseReleaseEvent(event)


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