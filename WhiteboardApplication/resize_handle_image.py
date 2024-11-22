from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsSceneMouseEvent
from PySide6.QtGui import QPixmap, QCursor
from PySide6.QtCore import Qt, QRectF, QPointF


class ResizablePixmapItem(QGraphicsPixmapItem):
    def __init__(self, pixmap, *args, **kwargs):
        super().__init__(pixmap, *args, **kwargs)

        # Enable interaction with the item
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsFocusable)

        # Save the original pixmap to maintain quality during resizing
        self.original_pixmap = pixmap

        # Initialize resize handles
        self.handles = []
        self.handle_size = 10
        self.dragging_handle = None  # Keep track of the active handle
        self.create_handles()
        self.setHandlesVisible(False)  # Hide handles by default

    def create_handles(self):
        """Create resize handles at the corners of the pixmap."""
        for i in range(4):  # Four handles (top-left, top-right, bottom-left, bottom-right)
            handle = QGraphicsRectItem(-self.handle_size / 2, -self.handle_size / 2, self.handle_size, self.handle_size, self)
            handle.setBrush(Qt.black)  # Black handles for visibility
            handle.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, False)
            handle.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, False)
            handle.setZValue(1)  # Ensure handles are above the pixmap
            handle.setVisible(False)  # Initially invisible
            self.handles.append(handle)

        self.update_handles()

    def setHandlesVisible(self, visible):
        """Show or hide resize handles."""
        for handle in self.handles:
            handle.setVisible(visible)

    def update_handles(self):
        """Reposition the handles at the corners of the pixmap."""
        rect = self.boundingRect()
        handle_positions = [
            rect.topLeft(),
            rect.topRight(),
            rect.bottomLeft(),
            rect.bottomRight(),
        ]

        for handle, position in zip(self.handles, handle_positions):
            handle.setPos(position)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """Show resize handles when the pixmap is clicked."""
        if event.button() == Qt.MouseButton.LeftButton:
            for i, handle in enumerate(self.handles):
                if handle.isUnderMouse():
                    self.dragging_handle = i
                    break
            else:
                self.dragging_handle = None
                self.setHandlesVisible(True)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        """Reset handle dragging state on mouse release."""
        self.dragging_handle = None
        super().mouseReleaseEvent(event)

    def focusOutEvent(self, event):
        """Hide resize handles when focus is lost (clicked outside)."""
        self.setHandlesVisible(False)
        super().focusOutEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle resizing when dragging a handle."""
        if self.dragging_handle is not None:
            self.resize(event.scenePos(), self.dragging_handle)
        else:
            super().mouseMoveEvent(event)

    def resize(self, mouse_pos, handle_index):
        """Resize the pixmap based on the selected handle, allowing smaller and larger scales."""
        rect = self.boundingRect()

        # Map mouse position to item coordinates
        local_pos = self.mapFromScene(mouse_pos)

        # Preserve the aspect ratio
        aspect_ratio = self.original_pixmap.width() / self.original_pixmap.height()

        # Calculate the new width and height based on the handle position
        if handle_index == 0:  # Top-left
            new_width = rect.right() - local_pos.x()
            new_height = new_width / aspect_ratio
        elif handle_index == 1:  # Top-right
            new_width = local_pos.x() - rect.left()
            new_height = new_width / aspect_ratio
        elif handle_index == 2:  # Bottom-left
            new_width = rect.right() - local_pos.x()
            new_height = new_width / aspect_ratio
        elif handle_index == 3:  # Bottom-right
            new_width = local_pos.x() - rect.left()
            new_height = new_width / aspect_ratio
        else:
            return

        # Ensure minimum size to prevent disappearing
        new_width = max(new_width, self.handle_size * 4)
        new_height = max(new_height, self.handle_size * 4)

        # Resize the pixmap
        scaled_pixmap = self.original_pixmap.scaled(new_width, new_height, Qt.AspectRatioMode.KeepAspectRatio)
        self.setPixmap(scaled_pixmap)

        # Update handles after resizing
        self.update_handles()
