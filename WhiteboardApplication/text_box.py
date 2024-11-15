from PySide6.QtWidgets import (
    QGraphicsTextItem, QGraphicsRectItem, QGraphicsItem, QColorDialog, QFontDialog, QMenu, QGraphicsItemGroup, QGraphicsEllipseItem
)
from PySide6.QtGui import QFont, QPen, QColor, QBrush
from PySide6.QtCore import Qt, QPointF, QRectF
from WhiteboardApplication.resize_handles import ResizeHandle

class TextBox(QGraphicsTextItem):
    def __init__(self):
        super().__init__()

        # Set default text, font, and color
        self.setPlainText("Type Here")
        self.setFont(QFont("Arial", 12))
        self.setDefaultTextColor(Qt.black)

        # Enable the text box to be moved, selected, and focused
        self.setFlags(QGraphicsTextItem.ItemIsMovable |
                      QGraphicsTextItem.ItemIsSelectable |
                      QGraphicsTextItem.ItemIsFocusable)

        # Allow text editing within the box
        self.setTextInteractionFlags(Qt.TextEditorInteraction)

        # Create background rectangle
        self.background = QGraphicsRectItem(self)
        self.background.setBrush(QColor(255, 255, 255, 127))
        self.background.setPen(QPen(Qt.black))
        self.background.setFlag(QGraphicsItem.ItemStacksBehindParent)

        # Define color mapping for resize handles
        handle_colors = {
            'topleft': QColor(255, 0, 0),     # Red doesn't work
            'top': QColor(0, 255, 0),         # Green doesn't work
            'topright': QColor(0, 0, 255),    # Blue
            'right': QColor(255, 255, 0),     # Yellow doesn't work
            'bottomright': QColor(255, 0, 255), # Magenta
            'bottom': QColor(0, 255, 255),    # Cyan
            'bottomleft': QColor(255, 128, 0), # Orange
            'left': QColor(128, 0, 255)       # Purple
        }

        self.handles = {}
        for position in handle_colors:
            handle = ResizeHandle(position, handle_colors[position], self)
            self.handles[position] = handle

        # Set initial size
        self.resize(200, 100)

        # Update handle positions
        self.updateHandlePositions()

        # Initially hide handles
        self.updateHandlesVisibility()

        # Variable to track if resizing is happening
        self.resizing = False

        #Variable to track if drawing is disabled
        self.drawing_disabled = False

    def resize(self, width, height):
        # Update the text document size
        self.setTextWidth(width)

        # Update the background rectangle
        self.background.setRect(0, 0, width, height)

        # Update handle positions
        self.updateHandlePositions()

    def updateHandlePositions(self):
        rect = self.background.rect()
        handle_size = self.handles['topleft'].rect().width()

        # Position mapping for each handle
        positions = {
            'topleft': (0, 0),
            'top': (rect.width() / 2 - handle_size / 2, 0),
            'topright': (rect.width() - handle_size, 0),
            'right': (rect.width() - handle_size, rect.height() / 2 - handle_size / 2),
            'bottomright': (rect.width() - handle_size, rect.height() - handle_size),
            'bottom': (rect.width() / 2 - handle_size / 2, rect.height() - handle_size),
            'bottomleft': (0, rect.height() - handle_size),
            'left': (0, rect.height() / 2 - handle_size / 2)
        }

        # Update each handle position
        for position, (x, y) in positions.items():
            self.handles[position].setPos(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Check if the click is on a resize handle
            if any(handle.contains(event.pos()) for handle in self.handles.values()):
                self.resizing = True
            else:
                # Show handles when the box is selected
                self.updateHandlesVisibility()
                # Set focus to the text box when left-clicked
                self.setFocus()

            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not self.drawing_disabled:
            # Process move or drawing events only if drawing is enabled
            super().mouseMoveEvent(event)
        else:
            event.ignore()


    def mouseReleaseEvent(self, event):
        self.resizing = False  # Reset resizing state on mouse release
        super().mouseReleaseEvent(event)
        # Update handle visibility based on selection
        self.updateHandlesVisibility()

    def boundingRect(self):
        return self.background.rect()

    def shape(self):
        return self.background.shape()

    #Creates context menu to change fonts, delete, and style text
    def contextMenuEvent(self, event):
        # Create a context menu
        context_menu = QMenu()
        change_color_action = context_menu.addAction("Change Color")
        change_text_action = context_menu.addAction("Change Text")
        bold_action = context_menu.addAction("Bold")
        italic_action = context_menu.addAction("Italic")
        underline_action = context_menu.addAction("Underline")
        delete_action = context_menu.addAction("Delete Box")

        # Execute the menu and capture the action
        action = context_menu.exec_(event.screenPos())

        if action == change_color_action:
            self.change_color()
        elif action == change_text_action:
            self.change_font()
        elif action == bold_action:
            self.bold()
        elif action == italic_action:
            self.italic()
        elif action == underline_action:
            self.underline()
        elif action == delete_action:
            self.delete()

    def change_color(self):
        new_color = QColorDialog.getColor()
        if new_color.isValid():
            cursor = self.textCursor()
            fmt = cursor.charFormat()
            fmt.setForeground(new_color)
            cursor.mergeCharFormat(fmt)

    def change_font(self):
        ok, font = QFontDialog.getFont()
        if ok:
            self.setFont(font)

    def bold(self):
        cursor = self.textCursor()
        fmt = cursor.charFormat()
        fmt.setFontWeight(QFont.Bold if fmt.fontWeight() != QFont.Bold else QFont.Normal)
        cursor.mergeCharFormat(fmt)

    def italic(self):
        cursor = self.textCursor()
        fmt = cursor.charFormat()
        fmt.setFontItalic(not fmt.fontItalic())
        cursor.mergeCharFormat(fmt)

    def underline(self):
        cursor = self.textCursor()
        fmt = cursor.charFormat()
        fmt.setFontUnderline(not fmt.fontUnderline())
        cursor.mergeCharFormat(fmt)

    def delete(self):
        scene = self.scene()
        if scene:
            scene.removeItem(self)
            self.deleteLater()

    def updateHandlesVisibility(self):
        # Show or hide handles based on the selection state
        for handle in self.handles.values():
            handle.setVisible(self.isSelected())