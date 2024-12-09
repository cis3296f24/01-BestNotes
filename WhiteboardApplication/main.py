import os
import pickle
import sys
import random
from firebase_admin import db
from threading import Thread
from WhiteboardApplication.board_sync import WhiteboardSync

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
    QScrollArea, QMessageBox, QDialog, QMenu, QInputDialog
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
    Qt, QRectF, QSizeF, QPointF, QSize, QRect, QFile, QIODevice, QUrl, QTimer
)

from WhiteboardApplication.UI.board import Ui_MainWindow
from WhiteboardApplication.text_box import TextBox
from WhiteboardApplication.new_notebook import NewNotebook
from WhiteboardApplication.board_scene import BoardScene

from WhiteboardApplication.resize_handle_image import ResizablePixmapItem

class MainWindow(QMainWindow, Ui_MainWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.user_email = None

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
        self.list_of_buttons = [self.tb_actionCursor, self.tb_actionPen, self.tb_actionHighlighter, self.tb_actionEraser]

        self.tb_actionCursor.triggered.connect(self.button_clicked)
        self.tb_actionPen.triggered.connect(self.button_clicked)
        self.tb_actionHighlighter.triggered.connect(self.button_clicked)
        self.tb_actionEraser.triggered.connect(self.button_clicked)

        #sharon helped me out by showing this below
        self.tb_actionText.triggered.connect(self.create_text_box)
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
        self.tb_actionUndo.triggered.connect(self.undo)
        self.tb_actionRedo.triggered.connect(self.redo)

        self.actionHost.triggered.connect(self.host_meeting)
        self.actionJoin.triggered.connect(self.join_meeting)

        # Image
        self.tb_actionImages.triggered.connect(self.upload_image)
        ###########################################################################################################
        self.redo_list = []

        self.new_tab()

        self.tb_actionPen.setChecked(True)
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool("pen")

        ## closes the tab/notebook when clicking the close button
        self.tabWidget.tabCloseRequested.connect(self.tabWidget.removeTab)

    def set_user_email(self, email):
        self.user_email = email
        print(f"Username set in MainWindow: {self.user_email}")

    def generate_meeting_id(self):
        """Generate a random numeric meeting ID."""
        return str(random.randint(100000, 999999))  # Example: 6-digit numeric ID

    def host_meeting(self):
        # Generate a random meeting ID
        meeting_id = self.generate_meeting_id()

        # Inform the user about the meeting ID
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Meeting Created")
        msg.setText(f"Your meeting ID is: {meeting_id}")
        msg.exec()

        # Create the meeting in the database
        meeting_ref = db.reference(f"meetings/{meeting_id}")
        meeting_ref.set({
            "participants": {
                "Host": {
                    "name": self.user_email
                }
            }
        })

        # Start listening for participant updates
        self.notify_participants(meeting_id)

        print(f"Meeting {meeting_id} created successfully.")
        current_scene = self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene()
        current_scene.sync = WhiteboardSync(current_scene, meeting_id, self.user_email)

    def join_meeting(self, user_id):
        # Prompt the user for the meeting ID
        meeting_id, ok = QInputDialog.getText(None, "Join Meeting", "Enter Meeting ID:")
        if not ok or not meeting_id.strip():
            return  # User canceled or entered invalid input

        meeting_id = meeting_id.strip()

        # Join the meeting in the database
        meeting_ref = db.reference(f"meetings/{meeting_id}/participants")
        meeting_ref.update({
            "Guest": {
                "name": self.user_email
            }
        })

        # Confirm to the user
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Meeting Joined")
        msg.setText(f"You have joined meeting {meeting_id}.")
        msg.exec()

        # Start listening for participant updates
        self.notify_participants(meeting_id)

        print(f"User {self.user_email} joined meeting {meeting_id}.")
        current_scene = self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene()
        current_scene.sync = WhiteboardSync(current_scene, meeting_id, self.user_email)

    def notify_participants(self, meeting_id):
        """Set up a listener to notify participants when someone joins."""
        meeting_ref = db.reference(f"meetings/{meeting_id}/participants")

        def participant_added(event):
            # Check for 'put' or 'patch' events which indicate an update to the participants
            if event.event_type in ["put", "patch"] and event.data:
                # Loop through the participants and check if any new participant has joined
                for user_id, participant_data in event.data.items():
                    user_name = participant_data.get("name", "Unknown")  # Get the participant's name
                    print(f"User added is named: {user_name}")
            else:
                print(f"Event type is {event.event_type}\n Event data is: {event.data}")

        def start_listener():
            try:
                print("Trying to start listener")
                meeting_ref.listen(participant_added)
            except Exception as e:
                print(f"Error in listener: {e}")

        listener_thread = Thread(target=start_listener)
        listener_thread.daemon = True  # This ensures the thread will exit when the main program exits
        listener_thread.start()

    def show_notification(self, user_name, meeting_id):
        """Display a QMessageBox notification for a new participant."""
        # Create the message box
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("New Participant")
        msg.setText(f"{user_name} has joined Meeting ID: {meeting_id}.")

        # Ensure the message box is shown on the main thread
        QTimer.singleShot(0, msg.exec)  # This schedules the execution on the main thread

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

    def clear_canvas(self):
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().clear()

    def color_changed(self, color):
         self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().change_color(color)

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

    # Depending on which button is clicked, sets the appropriate flag so that operations
    # don't overlap
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