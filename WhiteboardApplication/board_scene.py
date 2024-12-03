import json
from dataclasses import dataclass
from typing import List, Dict, Any
import time
import asyncio
import logger
from PySide6.QtCore import QPointF, QRectF, Qt, QSizeF
from PySide6.QtGui import QColor, QPen, QPainterPath, QBrush, QTransform
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsEllipseItem, QMessageBox
from WhiteboardApplication.Collab_Functionality.collab_manager import CollabServer, CollabClient
from WhiteboardApplication.text_box import TextBox
from WhiteboardApplication.video_player import MediaPlayer

#Sends information about actions made by a user so they can be broadcast to everyone else
@dataclass
class DrawingAction:
    """Represents a drawing action that can be serialized and shared."""
    action_type: str  # 'path', 'erase', 'highlight', 'text'
    data: Dict[str, Any]
    timestamp: float
    user_id: str

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
        self.username = None
        self.collab_client = None  # Use passed client or create a new one
        self.collab_server = None  # Default to None
        self.collaborators = []  # List of active collaborators

        self.data_channel = None
        self.action_buffer = []
        self.last_sync_timestamp = 0
        self.remote_paths = {}
        self.event_loop = None

    def set_collab_client(self, collab_client: CollabClient):
        """Set up collaboration client and connect signals."""
        self.collab_client = collab_client
        self.collab_client.connection_established.connect(self._on_connection_established)
        self.collab_client.message_received.connect(self.handle_remote_action)

        # Start the async event loop
        self._event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._event_loop)
        self._event_loop.create_task(self.collab_client.start_async())

    def _on_connection_established(self):
        """Handle successful connection establishment."""
        logger.info("Drawing connection established")
        QMessageBox.information(None, "Connected", "Drawing connection established")

    def broadcast_drawing_data(self, data: Dict[str, Any]):
        """Broadcast drawing data to peers."""
        if not self.collab_client or not self._event_loop:
            logger.warning("Collaboration not set up")
            return

        asyncio.run_coroutine_threadsafe(
            self.collab_client.send_drawing_data(data),
            self._event_loop
        )

    def set_username(self, username):
        """Sets the username and initializes collaboration setup."""
        self.username = username
        print(f"Username set for BoardScene: {username}")

        # Trigger collaboration setup now that username is set
        #self.setup_collaboration()

    '''
    def set_collab_client(self, collab_client):
        print("Collab client set same as main")
        self.collab_client = collab_client

        self.setup_collaboration()
    '''

    def serialize_action(self, action_type: str, data: Dict[str, Any]) -> str:
        """Convert a drawing action to JSON string."""
        action = DrawingAction(
            action_type=action_type,
            data=data,
            timestamp=time.time(),
            user_id=self.username
        )
        return json.dumps({
            'type': action.action_type,
            'data': action.data,
            'timestamp': action.timestamp,
            'user_id': action.user_id
        })

    def handle_remote_action(self, message):
        """Process drawing actions received from other users."""
        try:
            action = json.loads(message)

            # Ignore our own actions
            if action['user_id'] == self.username:
                return

            if action['type'] == 'path':
                self.apply_remote_path(action['data'])
            elif action['type'] == 'path_start':
                self.start_remote_path(action['data'])
            elif action['type'] == 'path_end':
                self.end_remote_path(action['data'])
            elif action['type'] == 'erase':
                self.apply_remote_erase(action['data'])
            elif action['type'] == 'highlight':
                self.apply_remote_highlight(action['data'])
            elif action['type'] == 'highlight_radius_change':
                self.apply_remote_highlight_radius(action['data'])
            elif action['type'] == 'text_select':
                self.apply_remote_text_select(action['data'])
            elif action['type'] == 'text_move':
                self.apply_remote_text_move(action['data'])
            elif action['type'] == 'text_drop':
                self.apply_remote_text_drop(action['data'])

        except Exception as e:
            print(f"Error handling remote action: {e}")

    def apply_remote_path(self, data):
        """Apply a remote drawing path."""
        path = QPainterPath()
        points = data['points']
        if points:
            path.moveTo(points[0][0], points[0][1])
            for point in points[1:]:
                path.lineTo(point[0], point[1])

        path_item = QGraphicsPathItem(path)
        pen = QPen(QColor(data['color']), data['size'])
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        path_item.setPen(pen)
        self.addItem(path_item)
        self.add_item_to_undo(path_item)

    def start_remote_path(self, data):
        """Start a new remote drawing path."""
        path = QPainterPath()
        path.moveTo(data['x'], data['y'])
        path_item = QGraphicsPathItem(path)
        pen = QPen(QColor(data['color']), data['size'])
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        path_item.setPen(pen)
        self.addItem(path_item)
        # Store the path item for future updates
        self.remote_paths[data['user_id']] = path_item

    def end_remote_path(self, data):
        """Finish a remote drawing path."""
        if data['user_id'] in self.remote_paths:
            path_item = self.remote_paths[data['user_id']]
            self.add_item_to_undo(path_item)
            del self.remote_paths[data['user_id']]

    def apply_remote_text_select(self, data):
        """Handle remote text box selection."""
        # You might want to highlight the text box or show some visual feedback
        for item in self.items():
            if isinstance(item, TextBox) and id(item) == data['text_id']:
                item.setSelected(True)
                break

    def apply_remote_text_move(self, data):
        """Handle remote text box movement."""
        for item in self.items():
            if isinstance(item, TextBox) and id(item) == data['text_id']:
                item.setPos(data['x'], data['y'])
                break

    def apply_remote_text_drop(self, data):
        """Handle remote text box drop."""
        for item in self.items():
            if isinstance(item, TextBox) and id(item) == data['text_id']:
                item.setPos(data['x'], data['y'])
                item.setSelected(False)
                break

    def apply_remote_highlight_radius(self, data):
        """Handle remote highlight radius change."""
        self.highlight_radius = data['radius']

    def apply_remote_erase(self, data):
        """Apply a remote erase action."""
        position = QPointF(data['x'], data['y'])
        self.erase(position)

    def apply_remote_highlight(self, data):
        """Apply a remote highlight action."""
        position = QPointF(data['x'], data['y'])
        self.highlight(position)

    def apply_remote_text(self, data):
        """Apply a remote text box action."""
        text_box = TextBox()
        text_box.setPlainText(data['text'])
        text_box.setPos(data['x'], data['y'])
        self.add_text_box(text_box)

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
        print(f"Active Tool: {self.active_tool}")

        if event.button() == Qt.LeftButton:
            if isinstance(item, TextBox):
                print("Box selected")
                self.drawing = False
                self.is_text_box_selected = True
                self.selected_text_box = item
                self.start_pos = event.scenePos()
                self.dragging_text_box = True

                # Broadcast text box selection
                self.broadcast_drawing_data({
                    'type': 'text_select',
                    'text_id': id(item),  # Use object id as unique identifier
                    'x': event.scenePos().x(),
                    'y': event.scenePos().y()
                })
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

                    # Broadcast initial pen position
                    self.broadcast_drawing_data({
                        'type': 'path_start',
                        'color': self.color.name(),
                        'size': self.size,
                        'x': self.previous_position.x(),
                        'y': self.previous_position.y()
                    })
                elif self.active_tool == "highlighter":
                    print("Highlight tool active")
                    self.drawing = False
                    self.highlight(event.scenePos())  # This already broadcasts
                elif self.active_tool == "eraser":
                    print("Eraser tool active")
                    self.drawing = False
                    self.erase(event.scenePos())  # This already broadcasts
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

            # Broadcast highlight radius change
            self.broadcast_drawing_data({
                'type': 'highlight_radius_change',
                'radius': self.highlight_radius
            })

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging_text_box and self.selected_text_box:
            self.drawing = False
            print("Dragging box")
            delta = event.scenePos() - self.start_pos
            new_pos = self.selected_text_box.pos() + delta
            self.selected_text_box.setPos(new_pos)
            self.start_pos = event.scenePos()

            # Broadcast text box movement
            self.broadcast_drawing_data({
            'type': 'text_move',
            'text_id': id(self.selected_text_box),
            'x': new_pos.x(),
            'y': new_pos.y()
            })
        elif self.drawing:
            print("drawing")
            curr_position = event.scenePos()
            self.path.lineTo(curr_position)
            self.pathItem.setPath(self.path)

            # Broadcast path segment
            self.broadcast_drawing_data({
                'type': 'path',
                'color': self.color.name(),
                'size': self.size,
                'points': [(self.previous_position.x(), self.previous_position.y()),
                       (curr_position.x(), curr_position.y())]
            })

            self.previous_position = curr_position
        elif self.active_tool == "highlighter":
            print("highlighting")
            self.highlight(event.scenePos())  # This already broadcasts

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.dragging_text_box:
                print("Finished dragging box")
                self.dragging_text_box = False

                # Broadcast text box drop
                final_pos = self.selected_text_box.pos()
                self.broadcast_drawing_data({
                    'type': 'text_drop',
                    'text_id': id(self.selected_text_box),
                    'x': final_pos.x(),
                    'y': final_pos.y()
                })
            elif self.drawing:
                self.add_item_to_undo(self.pathItem)
                print("Path item added to undo stack:", self.pathItem)

                # Broadcast path completion
                self.broadcast_drawing_data({
                    'type': 'path_end',
                    'path_id': id(self.pathItem)
                })
            elif self.highlight:
                self.add_item_to_undo(self.pathItem)
                print("Path item added to undo stack:", self.pathItem)

                # Broadcast highlight completion
                self.broadcast_drawing_data({
                    'type': 'highlight_end',
                    'highlight_id': id(self.pathItem)
                })

            self.drawing = False
            self.is_text_box_selected = False

        super().mouseReleaseEvent(event)

    '''
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
    '''

'''
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
   '''