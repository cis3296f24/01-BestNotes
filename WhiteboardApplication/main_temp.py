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
    QScrollArea
)

from PySide6.QtGui import (
    QPen,
    Qt,
    QPainter,
    QPainterPath,
    QColor,
    QBrush,
    QAction,
    QTransform, QBrush, QFont, QPixmap, QImageReader, QCursor
)

from PySide6.QtCore import (
    Qt, QRectF, QSizeF, QPointF, QSize, QRect
)

from WhiteboardApplication.UI.board import Ui_MainWindow
from WhiteboardApplication.text_box import TextBox
from WhiteboardApplication.new_notebook import NewNotebook
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

        self.is_text_box_selected = False
        self.dragging_text_box = False
        self.drawing_enabled = False
        self.highlighting_enabled = False
        self.erasing_enabled = False
        self.active_tool = None

        self.undo_list = []
        self.redo_list = []
        self.highlight_items = []

    def add_item_to_undo(self, item):
        self.redo_list.clear()
        self.undo_list.append([item])
        print("Added to undo:", item)

    def undo(self):
        if not self.undo_list:
            print("Undo list is empty")
            return

        item_group = self.undo_list.pop()
        for item in item_group:
            self.removeItem(item)
            print("Removed from scene (undo):", item)

        self.redo_list.append(item_group)
        print("Added to redo stack:", item_group)

    def redo(self):
        if not self.redo_list:
            print("Redo list is empty")
            return

        item_group = self.redo_list.pop()
        for item in item_group:
            self.addItem(item)
            print("Added back to scene (redo):", item)

        self.undo_list.append(item_group)
        print("Restored to undo stack:", item_group)

    def add_text_box(self, text_box_item):
        self.addItem(text_box_item)
        self.add_item_to_undo(text_box_item)
        print("TextBox added to scene:", text_box_item)

    def add_image(self, pixmap_item):
        self.addItem(pixmap_item)
        self.add_item_to_undo(pixmap_item)
        print("Image added to scene:", pixmap_item)

    def change_color(self, color):
        self.color = color

    def change_size(self, size):
        self.size = size

    def enable_drawing(self, enable):
        self.drawing_enabled = enable
        if enable:
            self.erasing_enabled = False
            self.highlighting_enabled = False

    def enable_eraser(self, enable):
        self.erasing_enabled = enable
        if enable:
            self.drawing_enabled = False
            self.highlighting_enabled = False

    def enable_highlighter(self, enable):
        self.highlighting_enabled = enable
        if enable:
            self.drawing_enabled = False
            self.erasing_enabled = False

    def erase(self, position):
        eraser_radius = 10
        erase_item = self.items(QRectF(position - QPointF(eraser_radius, eraser_radius), QSizeF(eraser_radius * 2, eraser_radius * 2)))
        for item in erase_item:
            if item in self.highlight_items:
                self.removeItem(item)
                self.highlight_items.remove(item)
            elif isinstance(item, QGraphicsPathItem):
                self.removeItem(item)

    def highlight(self, position):
        highlight_color = QColor(255, 255, 0, 30)
        highlight_brush = QBrush(highlight_color)
        highlight_radius = 15
        highlight_circle = QGraphicsEllipseItem(position.x() - highlight_radius,position.y() - highlight_radius,highlight_radius * 2,highlight_radius * 2)

        highlight_circle.setBrush(highlight_brush)
        highlight_circle.setPen(Qt.NoPen)

        self.addItem(highlight_circle)
        self.highlight_items.append(highlight_circle)

    def mousePressEvent(self, event):
        item = self.itemAt(event.scenePos(), QTransform())
        print(f"Active Tool: {self.active_tool}")  # Debugging print

        if event.button() == Qt.LeftButton:
            if isinstance(item, TextBox):
                print("Box selected")
                self.drawing = False
                self.is_text_box_selected = True
                self.selected_text_box = item
                self.start_pos = event.scenePos()
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
        elif getattr(self, 'highlighting', False):
            print("highlighting")
            self.highlight(event.scenePos())

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.dragging_text_box:
                print("Finished dragging box")
                self.dragging_text_box = False
            elif self.drawing:
                self.add_item_to_undo(self.pathItem)
                print("Path item added to undo stack:", self.pathItem)
            self.drawing = False
            self.is_text_box_selected = False

        super().mouseReleaseEvent(event)

    def set_active_tool(self, tool):
        self.active_tool = tool

class MainWindow(QMainWindow, Ui_MainWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.client = None

        if hasattr(self, 'actionImages'):
            print("actionImages is initialized.")
        else:
            print("actionImages is NOT initialized.")

        self.actionSave.triggered.connect(self.save)
        self.actionLoad.triggered.connect(self.load)
        self.actionNew.triggered.connect(self.new_tab)
        self.list_of_buttons = [self.tb_actionPen, self.tb_actionHighlighter, self.tb_actionEraser]

        self.tb_actionPen.setChecked(True)
        self.tb_actionPen.triggered.connect(self.button_clicked)
        self.tb_actionHighlighter.triggered.connect(self.button_clicked)
        self.tb_actionEraser.triggered.connect(self.button_clicked)

        self.tb_actionText.triggered.connect(self.create_text_box)
        self.tb_actionEraser.triggered.connect(self.button_clicked)
        self.tb_actionPen.triggered.connect(self.button_clicked)

        self.current_color = QColor("#000000")


        self.actionClear.triggered.connect(self.clear_canvas)

        self.current_color = QColor("#000000")
        self.tb_actionUndo.triggered.connect(self.undo)
        self.tb_actionRedo.triggered.connect(self.redo)
        self.tb_actionImages.triggered.connect(self.upload_image)
        self.redo_list = []
        self.new_tab()

    #Upload Image
    def upload_image(self):
        print("Image Button clicked")
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.bmp)")
        if file_name:
            pixmap = QPixmap(file_name)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio)
                pixmap_item = QGraphicsPixmapItem(pixmap)
                pixmap_item.setPos(0, 0)
                pixmap_item.setFlag(QGraphicsPixmapItem.ItemIsMovable)
                self.scene.add_image(pixmap_item)

    def undo(self):
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().undo()

    def redo(self):
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().redo()

    def clear_canvas(self):
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().clear()

    def color_dialog(self):
        color_dialog = QColorDialog()
        color_dialog.show()
        color_dialog.currentColorChanged.connect(lambda e: self.color_dialog_color_changed(color_dialog.currentColor()))
        self.current_color = color_dialog.currentColor()

    def color_dialog_color_changed(self, current_color):
        self.color_changed(current_color)
        if self.tb_actionEraser.isChecked():
            self.tb_actionEraser.setChecked(False)
            self.tb_actionPen.setChecked(True)

    def color_changed(self, color):
        self.scene.change_color(color)

    def button_clicked(self):
        sender_button = self.sender()
        if sender_button == self.tb_actionCursor:
            if self.tb_actionCursor.isChecked():
                print("Cursor activated")
                self.scene.set_active_tool("cursor")
                self.tb_actionEraser.setChecked(False)
                self.tb_actionPen.setChecked(False)
                self.tb_actionHighlighter.setChecked(False)

        # Toggle Pen
        if sender_button == self.tb_actionPen:
            if self.tb_actionPen.isChecked():
                print("Pen activated")
                self.color_changed(self.current_color)
                self.scene.set_active_tool("pen")
                self.tb_actionEraser.setChecked(False)
                self.tb_actionCursor.setChecked(False)
                self.tb_actionHighlighter.setChecked(False)
            else:
                print("Pen deactivated")
                self.scene.set_active_tool(None)

        # Toggle Eraser
        elif sender_button == self.tb_actionEraser:
            if self.tb_actionEraser.isChecked():
                print("Eraser activated")
                self.scene.set_active_tool("eraser")
                self.tb_actionPen.setChecked(False)
                self.tb_actionCursor.setChecked(False)
                self.tb_actionHighlighter.setChecked(False)
            else:
                print("Eraser deactivated")
                self.scene.set_active_tool(None)

        elif sender_button == self.tb_actionHighlighter:
            if self.tb_actionHighlighter.isChecked():
                print("Highlighter activated")
                self.scene.set_active_tool("highlighter")
                self.tb_actionPen.setChecked(False)
                self.tb_actionCursor.setChecked(False)
                self.tb_actionEraser.setChecked(False)
            else:
                print("Highlighter deactivated")
                self.scene.set_active_tool(None)

    def create_text_box(self):
        text_box_item = TextBox()
        self.scene.add_text_box(text_box_item)

    def enable_eraser(self, enable):
        self.erasing_enabled = enable
        if enable:
            self.drawing_enabled = False
            self.highlighting_enabled = False

    def enable_highlighter(self, enable):
        self.highlighting_enabled = enable
        if enable:
            self.erasing_enabled = False
            self.drawing_enabled = False

    def save(self):
        directory, _filter = QFileDialog.getSaveFileName(self, "Save as Pickle", '', "Pickle (*.pkl)")

        if directory == "":
            return

        with open(directory, 'wb') as file:
            pickle.dump(self.serialize_items(), file, protocol=pickle.HIGHEST_PROTOCOL)

    def load(self):
        self.scene.clear()
        directory, _filter = QFileDialog.getOpenFileName()
        with open(directory, 'rb') as file:
            items_data = pickle.load(file)
            self.deserialize_items(items_data)

    def serialize_items(self):
        items_data = []
        for item in self.scene.items():
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
            self.scene.addItem(item)

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
        self.tabWidget.addTab(NewNotebook.add_new_notebook(NewNotebook), "Notebook %d" % (self.tabWidget.count()+1))
        self.scene = BoardScene()
        NewNotebook.get_canvas(NewNotebook).setScene(self.scene)
        NewNotebook.get_canvas(NewNotebook).setRenderHint(QPainter.RenderHint.Antialiasing, True)


if __name__ == '__main__':
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())