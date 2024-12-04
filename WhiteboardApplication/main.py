import os
import pickle
import sys
from os.path import expanduser

from PySide6.QtWidgets import (
    QMainWindow,
    QGraphicsScene,
    QApplication,
    QGraphicsEllipseItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QColorDialog,
    QPushButton,
    QGraphicsTextItem,
    QToolBar,
    QFileDialog,
    QApplication,
    QLabel,
    QFileDialog,
    QGraphicsPixmapItem, QWidget, QTabWidget, QAbstractScrollArea, QSizePolicy, QGraphicsView, QHBoxLayout, QGridLayout,
    QScrollArea, QMenu
)

from PySide6.QtGui import (
    QPen,
    Qt,
    QPainter,
    QPainterPath,
    QColor,
    QBrush,
    QAction,
    QTransform, QBrush, QFont, QPixmap, QImageReader, QCursor, QDesktopServices
)

from PySide6.QtCore import (
    Qt, QRectF, QSizeF, QPointF, QSize, QRect, QDir, QUrl
)

from WhiteboardApplication.UI.board import Ui_MainWindow
from WhiteboardApplication.text_box import TextBox
from WhiteboardApplication.new_notebook import NewNotebook
from WhiteboardApplication.resize_handle_image import ResizablePixmapItem
from WhiteboardApplication.video_player import MediaPlayer
from WhiteboardApplication.Collab_Functionality.client import Client

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
        self.highlight_radius_options = [10, 25, 35, 50]
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
        self.addItem(text_box_item)
        self.add_item_to_undo(text_box_item)  # For complex items, group with handles if needed
        print("TextBox added to scene:", text_box_item)

    # def add_shape(self, shape_item):
    #     self.addItem(shape_item)
    #     self.add_item_to_undo(shape_item)  # For complex items, group with handles if needed
    #     print("Shape added to scene:", shape_item)

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

    def penColor(self, enable):
        self.change_color()

    #A basic eraser, created as a hold so text box function could be implemented
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

    # def highlight(self, position):
    #     highlight_color = QColor(255, 255, 0, 10)
    #     highlight_brush = QBrush(highlight_color)
    #     highlight_circle = QGraphicsEllipseItem(position.x() - self.highlight_radius,position.y() - self.highlight_radius,self.highlight_radius * 2,self.highlight_radius * 2)
    #
    #     highlight_circle.setBrush(highlight_brush)
    #     highlight_circle.setPen(Qt.NoPen)
    #
    #     self.addItem(highlight_circle)
    #     self.add_item_to_undo(highlight_circle)
    #     self.highlight_items.append(highlight_circle)

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
                elif self.active_tool == "colorpen":
                    print("Change color active")
                    self.drawing = True
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

    # def shapes_menu(self):
    #     shapes_menu = QMenu()
    #     ellipse_action = shapes_menu.addAction("Ellipse")
    #     rectangle_action = shapes_menu.addAction("Rectangle")
    #
    #     # Execute the menu and capture the action
    #     action = shapes_menu.exec(QCursor.pos())
    #
    #     if action == ellipse_action:
    #         self.shape_selected = "ellipse"
    #     elif action == rectangle_action:
    #         self.shape_selected = "rectangle"
    #
    # def get_shape_selected(self):
    #     return self.shape_selected



class MainWindow(QMainWindow, Ui_MainWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.client = None

        if hasattr(self, 'tb_actionImages'):
            print("actionImages is initialized.")
        else:
            print("actionImages is NOT initialized.")

        # Menus Bar: Files
        self.actionSave.triggered.connect(self.save)
        self.actionLoad.triggered.connect(self.load)
        self.actionNew.triggered.connect(self.new_tab)
        self.actionDocument.triggered.connect(self.display_help_doc)
        self.actionClose.triggered.connect(sys.exit)

        ############################################################################################################
        # Ensure all buttons behave properly when clicked
        self.list_of_buttons = [self.tb_actionCursor, self.tb_actionPen, self.tb_actionHighlighter, self.tb_actionEraser, self.tb_actionColorPen]

        self.tb_actionCursor.triggered.connect(self.button_clicked)
        self.tb_actionPen.triggered.connect(self.button_clicked)
        self.tb_actionHighlighter.triggered.connect(self.button_clicked)
        self.tb_actionEraser.triggered.connect(self.button_clicked)
        self.tb_actionColorPen.triggered.connect(self.button_clicked())

        #sharon helped me out by showing this below
        self.tb_actionText.triggered.connect(self.create_text_box)
        # self.tb_actionShapes.triggered.connect(self.shapes)
        #self.toolbar_actionLine.triggered.connect(self.tb_Line)
        self.tb_actionEraser.triggered.connect(self.button_clicked)
        self.tb_actionPen.triggered.connect(self.button_clicked)


        self.tb_actionVideos.triggered.connect(self.open_video_player)

        #fixing the eraser shit I messed up - RS
        menu = QMenu()
        menu.addAction("Erase Object", self.eraseObject_action)
        menu.addAction("Pen Eraser", self.penEraser_action)
        self.tb_actionEraser.setMenu(menu)

        self.eraser_color = QColor("#F3F3F3")



        self.current_color = QColor("#000000")

        ############################################################################################################

        self.actionClear.triggered.connect(self.clear_canvas)

        # Define what the tool buttons do
        ###########################################################################################################
        self.current_color = QColor("#000000")
        #self.tb_Pen.triggered.connect(lambda e: self.color_changed(self.current_color))
        # This eraser just changes stuff to white (#FFFFFF) and not to the proper background color of window... - RS 10/30
        # I used an online tool to find out the proper color of the background and updated it below... - RS 10/30
        #self.pb_Eraser.clicked.connect(lambda e: self.color_changed(QColor("#F3F3F3")))

        #self.pb_Color.clicked.connect(self.color_dialog)
        self.tb_actionUndo.triggered.connect(self.undo)
        self.tb_actionRedo.triggered.connect(self.redo)

        # Image
        self.tb_actionImages.triggered.connect(self.upload_image)
        ###########################################################################################################

        # self.scene = self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene()
        # self.gv_Canvas.setScene(self.scene)
        # self.gv_Canvas.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        self.redo_list = []

        self.new_tab()

        self.tb_actionPen.setChecked(True)
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool("pen")

        ## closes the tab/notebook when clicking the close button
        self.tabWidget.tabCloseRequested.connect(self.tabWidget.removeTab)

    #Upload Image
    def upload_image(self):
        print("Image Button clicked")
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.bmp)")
        if file_name:
            pixmap = QPixmap(file_name)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(500, 500, Qt.AspectRatioMode.KeepAspectRatio)
                pixmap_item = ResizablePixmapItem(pixmap)
                self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().add_image(pixmap_item)

    def open_video_player(self):
        # print("video button clicked")   #debug
        #create the player from board scene
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().open_video_player()

    # this finds the current tab and locates the canvas
    # inside that tab to access its scene
    def undo(self):
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().undo()

    def redo(self):
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().redo()

    # def shapes(self):
    #     self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().shapes_menu()

    def clear_canvas(self):
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().clear()

    # def color_dialog(self):
    #     color_dialog = QColorDialog()
    #     color_dialog.show()
    #     color_dialog.currentColorChanged.connect(lambda e: self.color_dialog_color_changed(color_dialog.currentColor()))
    #     self.current_color = color_dialog.currentColor()

    # def color_dialog_color_changed(self, current_color):
    #     self.color_changed(current_color)
    #     if self.tb_actionEraser.isChecked():
    #         self.tb_actionEraser.setChecked(False)
    #         self.tb_actionPen.setChecked(True)
    #
    def color_changed(self, color):
         self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().change_color(color)

    #Depending on which button is clicked, sets the appropriate flag so that operations
    #don't overlap


    #adding back in eraser menu functions - RS
    def eraseObject_action(self):
        print("Erase Object action")
        print("Eraser activated")  # Debugging print
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool("eraser")
        self.tb_actionPen.setChecked(False)  # Ensure pen is not active
        self.tb_actionCursor.setChecked(False)



    def penEraser_action(self):
        print("Pen Eraser action")
            # Enable pen mode, disable eraser
        print("Pen activated")  # Debugging print
        self.color_changed(self.eraser_color)
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool("pen")
        self.tb_actionEraser.setChecked(False)  # Ensure eraser is not active
        self.tb_actionCursor.setChecked(False)


    def button_clicked(self):
        sender_button = self.sender()

        # Toggle Cursor
        if sender_button == self.tb_actionCursor:
            if self.tb_actionCursor.isChecked():
                # disable pen, disable eraser
                print("Cursor activated")  # Debugging print
                self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool("cursor")
                self.tb_actionEraser.setChecked(False)
                self.tb_actionPen.setChecked(False)
                self.tb_actionHighlighter.setChecked(False)

        # Toggle Pen
        if sender_button == self.tb_actionPen:
            if self.tb_actionPen.isChecked():
                # Enable pen mode, disable eraser
                print("Pen activated")  # Debugging print
                # self.color_changed(self.current_color)
                self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool("pen")
                self.color_changed(self.current_color)
                self.tb_actionEraser.setChecked(False)  # Ensure eraser is not active
                self.tb_actionCursor.setChecked(False)
                self.tb_actionHighlighter.setChecked(False)
            else:
                # Deactivate drawing mode when button is clicked again
                print("Pen deactivated")  # Debugging print
                self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool(None)

        # Toggle Eraser
        elif sender_button == self.tb_actionEraser:
            if self.tb_actionEraser.isChecked():
                # Enable eraser mode, disable pen
                print("Eraser activated")  # Debugging print
                # self.color_changed(QColor("#F3F3F3"))
                self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool("eraser")
                self.tb_actionPen.setChecked(False)  # Ensure pen is not active
                self.tb_actionCursor.setChecked(False)
                self.tb_actionHighlighter.setChecked(False)
            else:
                # Deactivate erasing mode when button is clicked again
                print("Eraser deactivated")  # Debugging print
                self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool(None)

        elif sender_button == self.tb_actionHighlighter:
            if self.tb_actionHighlighter.isChecked():
                # Enable highlighter mode, disable pen & eraser
                print("Highlighter activated")  # Debugging print
                self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool("highlighter")
                self.tb_actionPen.setChecked(False)  # Ensure pen is not active
                self.tb_actionCursor.setChecked(False)
                self.tb_actionEraser.setChecked(False)
            else:
                # Deactivate erasing mode when button is clicked again
                print("Highlighter deactivated")  # Debugging print
                self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool(None)

        elif sender_button == self.tb_actionColorPen:
            if self.tb_actionColorPen.isChecked():
                # Enable color selector mode, disable eraser and higlighter
                print("Color selection activated")  # Debugging print
                self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool("colorpen")
                self.tb_actionPen.setChecked(True)  # Ensure pen is active
                self.tb_actionCursor.setChecked(False)
                self.tb_actionEraser.setChecked(False)
            else:
                # Deactivate erasing mode when button is clicked again
                print("Color selection deactivated")  # Debugging print
                self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool(None)

        elif sender_button == self.tb_actionText:
            if self.tb_actionText.isChecked():
                # Enable highlighter mode, disable pen & eraser
                print("Textbox activated")  # Debugging print
                self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool("highlighter")
                self.tb_actionPen.setChecked(False)  # Ensure pen is not active
                self.tb_actionCursor.setChecked(False)
                self.tb_actionEraser.setChecked(False)

    #Adds a text box using the method in BoardScene
    def create_text_box(self):
        # Create a text box item and add it to the scene
        text_box_item = TextBox()
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().add_text_box(text_box_item)


    ## Was unable to implement this during the duration of the last sprint.
    # def create_shape(self):
    #     if BoardScene.get_shape_selected == "rectangle":
    #         shape_item = QGraphicsRectItem(0, 0, 40, 20)
    #     elif BoardScene.get_shape_selected == "ellipse":
    #         shape_item = QGraphicsEllipseItem(0, 0, 40, 20)
    #     self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().add_shape(shape_item)

    # def change_background_color(self):
    #     # Open a color board and set the background color
    #     color = QColorDialog.getColor()
    #     if color.isValid():
    #         # Update backround color
    #         self.scene.setBackgroundBrush(color)

    def enable_eraser(self, enable):
        self.erasing_enabled = enable
        # Ensure drawing is off when erasing is on
        if enable:
            self.drawing_enabled = False
            self.highlighting_enabled = False

    def enable_highlighter(self, enable):
        self.highlighting_enabled = enable
        if enable:
            self.erasing_enabled = False
            self.drawing_enabled = False

    def display_help_doc(self):
        path = os.getcwd()
        path += "\\PDFs\\Help_Document.pdf"
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def save(self):
        directory, _filter = QFileDialog.getSaveFileName(self, "Save as Pickle", '', "Pickle (*.pkl)")

        if directory == "":
            return

        with open(directory, 'wb') as file:
            # noinspection PyTypeChecker
            pickle.dump(self.serialize_items(), file, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self):
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().clear()
        directory, _filter = QFileDialog.getOpenFileName()
        with open(directory, 'rb') as file:
            items_data = pickle.load(file)
            self.deserialize_items(items_data)

    def serialize_items(self):
        items_data = []
        for item in self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().items():
            if isinstance(item, TextBox):
                items_data.append({
                    'type': 'TextBox',
                    'text': item.toPlainText(),
                    'font': self.serialize_font(item.font()),
                    'color': self.serialize_color(item.defaultTextColor()),
                    'rotation': item.rotation(),
                    'transform': self.serialize_transform(item.transform()),
                    'x': item.pos().x(),
                    'y': item.pos().y(),
                    'name': item.toolTip(),
                })

            elif isinstance(item, QGraphicsPathItem):
                path_data = {
                    'type': 'QGraphicsPathItem',
                    'pen': self.serialize_pen(item.pen()),
                    'brush': self.serialize_brush(item.brush()),
                    'rotation': item.rotation(),
                    'transform': self.serialize_transform(item.transform()),
                    'x': item.pos().x(),
                    'y': item.pos().y(),
                    'name': item.toolTip(),
                    'elements': self.serialize_path(item.path()),
                }
                items_data.append(path_data)

        return items_data

    def serialize_color(self, color: QColor):
        return {
            'red': color.red(),
            'green': color.green(),
            'blue': color.blue(),
            'alpha': color.alpha(),
        }

    def serialize_pen(self, pen: QPen):
        return {
            'width': pen.width(),
            'color': self.serialize_color(pen.color()),
            'style': pen.style(),
            'capstyle': pen.capStyle(),
            'joinstyle': pen.joinStyle()
        }

    def serialize_brush(self, brush: QBrush):
        return {
            'color': self.serialize_color(brush.color()),
            'style': brush.style()
        }

    def serialize_font(self, font: QFont):
        return {
            'family': font.family(),
            'pointsize': font.pixelSize(),
            'letterspacing': font.letterSpacing(),
            'bold': font.bold(),
            'italic': font.italic(),
            'underline': font.underline(),
        }

    def serialize_transform(self, transform: QTransform):
        return {
            'm11': transform.m11(),
            'm12': transform.m12(),
            'm13': transform.m13(),
            'm21': transform.m21(),
            'm22': transform.m22(),
            'm23': transform.m23(),
            'm31': transform.m31(),
            'm32': transform.m32(),
            'm33': transform.m33()
        }

    def serialize_path(self, path: QPainterPath):
        elements = []
        for i in range(path.elementCount()):
            element = path.elementAt(i)
            if element.isMoveTo():
                elements.append({'type': 'moveTo', 'x': element.x, 'y': element.y})
            elif element.isLineTo():
                elements.append({'type': 'lineTo', 'x': element.x, 'y': element.y})
            elif element.isCurveTo():
                elements.append({'type': 'curveTo', 'x': element.x, 'y': element.y})
        return elements

    def deserialize_items(self, items_data):
        for item_data in items_data:
            if item_data['type'] == 'TextBox':
                item = self.deserialize_text_item(item_data)
            elif item_data['type'] == 'QGraphicsPathItem':
                item = self.deserialize_path_item(item_data)

            # Add item
            self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().addItem(item)

    def deserialize_color(self, color):
        return QColor(color['red'], color['green'], color['blue'], color['alpha'])

    def deserialize_pen(self, data):
        pen = QPen()
        pen.setWidth(data['width'])
        pen.setColor(self.deserialize_color(data['color']))
        pen.setStyle(data['style'])
        pen.setCapStyle(data['capstyle'])
        pen.setJoinStyle(data['joinstyle'])
        return pen

    def deserialize_brush(self, data):
        brush = QBrush()
        brush.setColor(self.deserialize_color(data['color']))
        brush.setStyle(data['style'])
        return brush

    def deserialize_font(self, data):
        font = QFont()
        font.setFamily(data['family'])
        font.setPixelSize(data['pointsize'])
        font.setLetterSpacing(QFont.AbsoluteSpacing, data['letterspacing'])
        font.setBold(data['bold'])
        font.setItalic(data['italic'])
        font.setUnderline(data['underline'])
        return font

    def deserialize_transform(self, data):
        transform = QTransform(
            data['m11'], data['m12'], data['m13'],
            data['m21'], data['m22'], data['m23'],
            data['m31'], data['m32'], data['m33']
        )
        return transform

    def deserialize_text_item(self, data):
        from text_box import TextBox
        text_item = TextBox()
        text_item.setFont(self.deserialize_font(data['font']))
        text_item.setDefaultTextColor(self.deserialize_color(data['color']))
        text_item.setRotation(data['rotation'])
        text_item.setTransform(self.deserialize_transform(data['transform']))
        text_item.setPos(data['x'], data['y'])
        text_item.setToolTip(data['name'])
        text_item.setPlainText(data['text'])
        return text_item

    def deserialize_path_item(self, data):
        sub_path = QPainterPath()
        for element in data['elements']:
            if element['type'] == 'moveTo':
                sub_path.moveTo(element['x'], element['y'])
            elif element['type'] == 'lineTo':
                sub_path.lineTo(element['x'], element['y'])
            elif element['type'] == 'curveTo':
                sub_path.cubicTo(element['x'],
                                 element['y'],
                                 element['x'],
                                 element['y'],
                                 element['x'],
                                 element['y'])

        path_item = QGraphicsPathItem(sub_path)
        path_item.setPen(self.deserialize_pen(data['pen']))
        path_item.setBrush(self.deserialize_brush(data['brush']))
        path_item.setRotation(data['rotation'])
        path_item.setTransform(self.deserialize_transform(data['transform']))
        path_item.setPos(data['x'], data['y'])
        path_item.setToolTip(data['name'])

        return path_item

    def new_tab(self):
        #adds a new tab that contains the widget canvas
        self.tabWidget.addTab(NewNotebook.add_new_notebook(NewNotebook), "Notebook %d" % (self.tabWidget.count()+1))

        # attaches a new instance of scene to the new tab's canvas
        self.scene = BoardScene()
        NewNotebook.get_canvas(NewNotebook).setScene(self.scene)
        NewNotebook.get_canvas(NewNotebook).setRenderHint(QPainter.RenderHint.Antialiasing, True)



if __name__ == '__main__':
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())