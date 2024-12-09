import json
from WhiteboardApplication.text_box import TextBox
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from firebase_admin import db
from PySide6.QtCore import QPointF, Qt, Signal, QObject, QTimer
import time
from PySide6.QtGui import QPainterPath, QPen, QColor
from PySide6.QtWidgets import QGraphicsPathItem


@dataclass
class DrawingAction:
    action_type: str
    user_id: str  # Add user_id to track who performed the action
    points: list = None
    color: str = None
    size: int = None
    text_content: str = None
    text_position: dict = None
    text_id: str = None  # Unique identifier for textboxes
    timestamp: float = field(default_factory=time.time)


class WhiteboardSync(QObject):
    action_received = Signal(dict)

    def __init__(self, board_scene, meeting_id, user_id):
        super().__init__()
        self.scene = board_scene
        self.meeting_id = meeting_id
        self.user_id = user_id  # Store the current user's ID
        self.actions_ref = db.reference(f"meetings/{meeting_id}/actions")
        self.local_action = False
        self.text_boxes = {}  # Store text box references by ID

        # Per-user undo/redo stacks
        self.user_undo_stacks = {}
        self.user_redo_stacks = {}

        self.action_received.connect(self.handle_remote_action)
        QTimer.singleShot(0, self.setup_listeners)

    def setup_listeners(self):
        """Set up Firebase listeners for all action types"""

        def action_handler(event):
            if event.event_type == "put" and event.data and not self.local_action:
                # Emit signal instead of directly handling the action
                self.action_received.emit(event.data)

        try:
            self.actions_ref.listen(action_handler)
        except Exception as e:
            print(f"Error setting up listener: {e}")

    def replay_drawing(self, action: DrawingAction):
        """Recreate a drawing action on the local board"""
        try:
            if not action.points:
                return

            path = QPainterPath()
            first_point = True

            for point in action.points:
                pos = QPointF(point['x'], point['y'])
                if first_point:
                    path.moveTo(pos)
                    first_point = False
                else:
                    path.lineTo(pos)

            path_item = QGraphicsPathItem()
            pen = QPen(QColor(action.color), action.size)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            path_item.setPen(pen)
            path_item.setPath(path)

            self.scene.addItem(path_item)
            self.scene.add_item_to_undo(path_item)
        except Exception as e:
            print(f"Error replaying drawing: {e}")

    def replay_erasing(self, action: DrawingAction):
        """Recreate an erasing action on the local board"""
        try:
            if not action.points:
                return

            for point in action.points:
                self.scene.erase(QPointF(point['x'], point['y']))
        except Exception as e:
            print(f"Error replaying erasing: {e}")

    def handle_remote_action(self, action_data: Dict[str, Any]):
        """Process incoming actions from other users"""
        try:
            if action_data['user_id'] == self.user_id:
                return  # Ignore our own actions coming back from Firebase

            action = DrawingAction(**action_data)

            if action.action_type in ['pen', 'highlighter']:
                self.replay_drawing(action)
            elif action.action_type == 'eraser':
                self.replay_erasing(action)
            elif action.action_type == 'textbox_create':
                self.replay_textbox_create(action)
            elif action.action_type == 'textbox_move':
                self.replay_textbox_move(action)
            elif action.action_type == 'textbox_content':
                self.replay_textbox_content(action)
            elif action.action_type == 'undo':
                self.replay_undo(action)
            elif action.action_type == 'redo':
                self.replay_redo(action)

            # Store action in appropriate user's undo stack
            if action.action_type not in ['undo', 'redo']:
                if action.user_id not in self.user_undo_stacks:
                    self.user_undo_stacks[action.user_id] = []
                self.user_undo_stacks[action.user_id].append(action)
        except Exception as e:
            print(f"Error handling remote action: {e}")

    def replay_undo(self, action: DrawingAction):
        """Replay an undo action for all users."""
        try:
            if action.action_type in ['pen', 'highlighter']:
                self.remove_drawing(action)
            elif action.action_type == 'textbox_create':
                self.remove_textbox(action)
        except Exception as e:
            print(f"Error replaying undo: {e}")

    def replay_redo(self, action: DrawingAction):
        """Replay a redo action for all users."""
        try:
            if action.action_type in ['pen', 'highlighter']:
                self.replay_drawing(action)
            elif action.action_type == 'textbox_create':
                self.replay_textbox_create(action)
        except Exception as e:
            print(f"Error replaying redo: {e}")

    def remove_drawing(self, action: DrawingAction):
        """Custom method to remove drawing items."""
        try:
            # Find and remove the drawn path from the scene
            for item in self.scene.items():
                if isinstance(item, QGraphicsPathItem):
                    if item.pen().color().name() == action.color and \
                            item.pen().width() == action.size:
                        self.scene.removeItem(item)
                        break
        except Exception as e:
            print(f"Error removing drawing: {e}")

    def remove_textbox(self, action: DrawingAction):
        """Remove a textbox based on the action."""
        text_box = self.text_boxes.pop(action.text_id, None)
        if text_box:
            self.scene.removeItem(text_box)

    def reverse_textbox_action(self, action: DrawingAction):
        """Reverse a textbox action (move or content change)."""
        text_box = self.text_boxes.get(action.text_id)
        if not text_box:
            return
        if action.action_type == 'textbox_move':
            # Reverse the move action (restore previous position)
            text_box.setPos(QPointF(action.text_position['x'], action.text_position['y']))
        elif action.action_type == 'textbox_content':
            # Reverse the content change
            text_box.setPlainText(action.text_content)

    def sync_undo(self):
        """Sync an undo action for the current user"""
        if self.local_action:
            return

        try:
            self.local_action = True
            if self.user_id in self.user_undo_stacks and self.user_undo_stacks[self.user_id]:
                last_action = self.user_undo_stacks[self.user_id].pop()
                if self.user_id not in self.user_redo_stacks:
                    self.user_redo_stacks[self.user_id] = []
                self.user_redo_stacks[self.user_id].append(last_action)

                action = DrawingAction(
                    action_type='undo',
                    user_id=self.user_id,
                    points=last_action.points,
                    color=last_action.color,
                    size=last_action.size,
                    text_content=last_action.text_content,
                    text_position=last_action.text_position,
                    text_id=last_action.text_id
                )
                self.actions_ref.push(vars(action))
        finally:
            self.local_action = False

    def sync_redo(self):
        """Sync a redo action for the current user"""
        if self.local_action:
            return

        try:
            self.local_action = True
            if self.user_id in self.user_redo_stacks and self.user_redo_stacks[self.user_id]:
                last_action = self.user_redo_stacks[self.user_id].pop()
                self.user_undo_stacks[self.user_id].append(last_action)

                action = DrawingAction(
                    action_type='redo',
                    user_id=self.user_id,
                    points=last_action.points,
                    color=last_action.color,
                    size=last_action.size,
                    text_content=last_action.text_content,
                    text_position=last_action.text_position,
                    text_id=last_action.text_id
                )
                self.actions_ref.push(vars(action))
        finally:
            self.local_action = False

    def replay_textbox_create(self, action: DrawingAction):
        """Handle creation of a new textbox"""
        text_box = TextBox()
        text_box.setPlainText(action.text_content or '')
        text_box.setPos(QPointF(action.text_position['x'], action.text_position['y']))
        self.text_boxes[action.text_id] = text_box
        self.scene.addItem(text_box)

    def replay_textbox_move(self, action: DrawingAction):
        """Handle movement of an existing textbox"""
        text_box = self.text_boxes.get(action.text_id)
        if text_box:
            text_box.setPos(QPointF(action.text_position['x'], action.text_position['y']))

    def replay_textbox_content(self, action: DrawingAction):
        """Handle content changes in an existing textbox"""
        text_box = self.text_boxes.get(action.text_id)
        if text_box:
            text_box.setPlainText(action.text_content)

    def sync_drawing(self, path_item, is_highlighter=False):
        """Sync a drawing action to Firebase"""
        self.local_action = True
        try:
            path = path_item.path()
            points = []
            for i in range(path.elementCount()):
                element = path.elementAt(i)
                points.append({'x': element.x, 'y': element.y})

            action = DrawingAction(
                action_type='highlighter' if is_highlighter else 'pen',
                user_id=self.user_id,  # Add the user_id from the class instance
                points=points,
                color=path_item.pen().color().name(),
                size=path_item.pen().width()
            )

            self.actions_ref.push(vars(action))
        finally:
            self.local_action = False

    def sync_eraser(self, point: QPointF):
        """Sync an eraser action to Firebase"""
        self.local_action = True
        try:
            action = DrawingAction(
                action_type='eraser',
                user_id=self.user_id,  # Add the user_id here as well
                points=[{'x': point.x(), 'y': point.y()}]
            )
            self.actions_ref.push(vars(action))
        finally:
            self.local_action = False

    def sync_textbox_create(self, text_box):
        """Sync creation of a new textbox"""
        if self.local_action:
            return

        try:
            self.local_action = True
            text_id = str(time.time())  # Generate unique ID
            action = DrawingAction(
                action_type='textbox_create',
                user_id=self.user_id,
                text_content=text_box.toPlainText(),
                text_position={'x': text_box.pos().x(), 'y': text_box.pos().y()},
                text_id=text_id
            )
            self.text_boxes[text_id] = text_box
            self.actions_ref.push(vars(action))
        finally:
            self.local_action = False

    def sync_textbox_move(self, text_box):
        """Sync movement of a textbox"""
        if self.local_action:
            return

        try:
            self.local_action = True
            text_id = next((k for k, v in self.text_boxes.items() if v == text_box), None)
            if text_id:
                action = DrawingAction(
                    action_type='textbox_move',
                    user_id=self.user_id,
                    text_position={'x': text_box.pos().x(), 'y': text_box.pos().y()},
                    text_id=text_id
                )
                self.actions_ref.push(vars(action))
        finally:
            self.local_action = False

    def sync_textbox_content(self, text_box):
        """Sync content changes in a textbox"""
        if self.local_action:
            return

        try:
            self.local_action = True
            text_id = next((k for k, v in self.text_boxes.items() if v == text_box), None)
            if text_id:
                action = DrawingAction(
                    action_type='textbox_content',
                    user_id=self.user_id,
                    text_content=text_box.toPlainText(),
                    text_id=text_id
                )
                self.actions_ref.push(vars(action))
        finally:
            self.local_action = False

