from WhiteboardApplication.resize_handle_image import ResizablePixmapItem
from PySide6.QtCore import QPointF, QRectF, Qt, QSizeF
from PySide6.QtGui import QColor, QPen, QPainterPath, QBrush, QTransform
from PySide6.QtWidgets import QGraphicsScene, QGraphicsPathItem, QGraphicsEllipseItem, QMessageBox
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
        self.sync = None

        # Highlighter
        self.path_highlighter = None
        self.previous_position_highlighter = None
        self.highlighting= False
        self.color_highlighter = QColor(255, 255, 0, 30)
        self.size_highlighter = 10
        self.pathItem_highlighter = None

        #Added flags to check which button is being pressed, and if text boxes are being dragged
        self.is_text_box_selected = False
        self.dragging_text_box = False
        self.drawing_enabled = False
        self.highlighting_enabled = False
        self.erasing_enabled = False
        self.active_tool = None

        self.undo_list = []
        self.redo_list = []
        self.highlight_items = []
        self.i = 1
        self.j = 1
        self.highlight_radius_options = [10, 20, 30, 40]
        self.pen_radius_options = [1,5,10,20]

    #Adds an action to the undo list (or a list of items in the case of textbox), by treating every action as a list
    def add_item_to_undo(self, item):
        """Add a single item or group of items to the undo list and clear redo list"""
        # Clear redo list to ensure correct redo functionality
        self.redo_list.clear()

        # Add item (or list of items if it's a group) to the undo list
        self.undo_list.append([item])
        print("Added to undo:", item)

    #Pops action of undo stack to undo, and adds it to redo in case user wants to redo the action
    def undo(self):
        if self.sync:
            print("Sync Undo\n")
            self.sync.sync_undo()

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

    #Pops an action off the redo stack and adds it back to undo to redo and action
    def redo(self):
        if self.sync:
            print("Sync Redo\n")
            self.sync.sync_redo()

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

    #Adds text box and resizing handles as a group so they are undone at once
    def add_text_box(self, text_box_item):
        if self.sync:
            self.sync.sync_textbox_create(text_box_item)
            text_box_item.contentChanged.connect(
                lambda: self.sync.sync_textbox_content(text_box_item)
            )
            text_box_item.moved.connect(
                lambda: self.sync.sync_textbox_move(text_box_item)
            )
        self.addItem(text_box_item)
        self.add_item_to_undo(text_box_item)  # For complex items, group with handles if needed
        print("TextBox added to scene:", text_box_item)

    def add_image(self, pixmap_item):
        self.addItem(pixmap_item)
        self.add_item_to_undo(pixmap_item)
        print("Image added to scene:", pixmap_item)

    def change_color(self, color):
        self.color = color

    def change_size(self, size):
        self.size = size

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

    #A basic eraser, created as a hold so text box function could be implemented
    def erase(self, position):
        if self.sync:
            self.sync.sync_eraser(position)

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

    def open_video_player(self):
        print("Video button clicked")
        self.player = MediaPlayer()
        self.player.show()
        self.player.resize(640, 480)

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
                self.highlighting_enabled = False
                self.highlighting = False
            elif isinstance(item, ResizablePixmapItem):
                print("Imaged selected")
                self.drawing = False
                #self.is_image_box_selected = True
                #self.selected_image_box = item
                #self.start_pos = event.scenePos()
                #self.dragging_image_box = True
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
                    print("Highlighter tool active")
                    self.highlighting = True
                    self.path_highlighter = QPainterPath()
                    self.previous_position_highlighter = event.scenePos()
                    self.path_highlighter.moveTo(self.previous_position_highlighter)
                    self.pathItem_highlighter = QGraphicsPathItem()
                    my_pen = QPen(self.color_highlighter, self.size_highlighter)
                    my_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    self.pathItem_highlighter.setPen(my_pen)
                    self.addItem(self.pathItem_highlighter)
                elif self.active_tool == "eraser":
                    print("Eraser tool active")
                    self.drawing = False
                    self.erase(event.scenePos())
                elif self.active_tool == "cursor":
                    print("Cursor active")
                    self.drawing = False
        elif event.button() == Qt.RightButton:
            if self.active_tool == "highlighter":
                self.highlighting = True
                self.path_highlighter = QPainterPath()
                self.previous_position_highlighter = event.scenePos()
                self.path_highlighter.moveTo(self.previous_position_highlighter)
                self.pathItem_highlighter = QGraphicsPathItem()
                self.size_highlighter = self.highlight_radius_options[self.i]
                my_pen = QPen(self.color_highlighter, self.size_highlighter)
                my_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                self.pathItem_highlighter.setPen(my_pen)
                self.addItem(self.pathItem_highlighter)
                self.add_item_to_undo(self.pathItem_highlighter)
                self.i += 1
                if self.i >= len(self.highlight_radius_options):
                    self.i = 0
            elif self.active_tool == "pen":
                self.drawing = True
                self.path = QPainterPath()
                self.previous_position = event.scenePos()
                self.path.moveTo(self.previous_position)
                self.pathItem = QGraphicsPathItem()
                self.size = self.pen_radius_options[self.j]
                my_pen = QPen(self.color, self.size)
                my_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                self.pathItem.setPen(my_pen)
                self.addItem(self.pathItem)
                self.add_item_to_undo(self.pathItem)
                self.j += 1
                if self.j >= len(self.pen_radius_options):
                    self.j = 0

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging_text_box and self.selected_text_box:
            self.drawing = False
            self.highlight_enabled = False
            self.highlighting = False
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
        elif self.highlighting:
            print("highlighting")
            curr_position = event.scenePos()
            self.path_highlighter.lineTo(curr_position)
            self.pathItem_highlighter.setPath(self.path_highlighter)
            self.previous_position_highlighter = curr_position

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton or event.button() == Qt.RightButton:
            if self.drawing and self.pathItem and self.sync:
                self.sync.sync_drawing(self.pathItem)
            elif self.highlighting and self.pathItem_highlighter and self.sync:
                self.sync.sync_drawing(self.pathItem_highlighter, True)
            if self.dragging_text_box:
                print("Finished dragging box")
                self.dragging_text_box = False
            elif self.drawing:
                # Add the completed path to the undo stack when drawing is finished so it can be deleted or added back with undo
                self.add_item_to_undo(self.pathItem)
                print("Path item added to undo stack:", self.pathItem)
            elif self.active_tool == "highlighter":
                self.add_item_to_undo(self.pathItem_highlighter)
                print("Path item added to undo stack:", self.pathItem_highlighter)
            self.drawing = False
            self.highlighting = False
            self.highlighting_enabled = False
            self.is_text_box_selected = False

        super().mouseReleaseEvent(event)
    #Marks which tool (pen, eraser, highlighter) is being used so multiple don't run at once
    def set_active_tool(self, tool):
        self.active_tool = tool
