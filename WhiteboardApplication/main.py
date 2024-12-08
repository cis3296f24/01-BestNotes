import os
import pickle
import sys
import socket
import threading
import time

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
    QScrollArea, QMessageBox, QDialog
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
    Qt, QRectF, QSizeF, QPointF, QSize, QRect, QFile, QIODevice
)

import ssl
import json

from WhiteboardApplication.UI.board import Ui_MainWindow
from WhiteboardApplication.text_box import TextBox
from WhiteboardApplication.new_notebook import NewNotebook
from WhiteboardApplication.board_scene import BoardScene
from WhiteboardApplication.database import UserDatabase
from WhiteboardApplication.collab_dialogs import HostDialog, JoinDialog, UserRegistry
from WhiteboardApplication.Collab_Functionality.collab_manager import CollabServer, CollabClient
from WhiteboardApplication.Collab_Functionality.discover_server import start_discovery_server

class MainWindow(QMainWindow, Ui_MainWindow):

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.client = False  # Default state (not logged in)

        self.config = self.load_config()
        print("Loaded config:", self.config)  # Add this for debugging
        self.ssl_key_path = self.config.get('ssl_key_path')  # Use .get() to avoid KeyError
        self.ssl_cert_path = self.config.get('ssl_cert_path')  # Same here

        if not self.ssl_key_path or not self.ssl_cert_path:
            print("Warning: SSL key or certificate path is missing.")

        if hasattr(self, 'actionImages'):
            print("actionImages is initialized.")
        else:
            print("actionImages is NOT initialized.")

        # Menus Bar: Files
        self.actionSave.triggered.connect(self.save)
        self.actionLoad.triggered.connect(self.load)
        self.actionNew.triggered.connect(self.new_tab)

        #Menu Bar: Hosting and Joining
        # Add collab-related members
        self.user_db = UserDatabase()
        self.user_reg = UserRegistry()
        self.collab_server = None
        self.collab_client = None
        self.username = None

        # Add collab menu actions
        self.actionHost.triggered.connect(self.host_session)
        self.actionJoin.triggered.connect(self.join_session)

        ############################################################################################################
        # Ensure all buttons behave properly when clicked
        self.list_of_buttons = [self.tb_actionPen, self.tb_actionHighlighter, self.tb_actionEraser]

        self.tb_actionPen.setChecked(True)
        self.tb_actionPen.triggered.connect(self.button_clicked)
        self.tb_actionHighlighter.triggered.connect(self.button_clicked)
        self.tb_actionEraser.triggered.connect(self.button_clicked)

        #sharon helped me out by showing this below
        self.tb_actionText.triggered.connect(self.create_text_box)
        self.tb_actionEraser.triggered.connect(self.button_clicked)
        self.tb_actionPen.triggered.connect(self.button_clicked)

        self.current_color = QColor("#000000")

        ############################################################################################################

        self.actionClear.triggered.connect(self.clear_canvas)

        # Define what the tool buttons do
        ###########################################################################################################
        self.current_color = QColor("#000000")
        self.tb_actionUndo.triggered.connect(self.undo)
        self.tb_actionRedo.triggered.connect(self.redo)

        # Image
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
                pixmap_item.setPos(0, 0)  # Adjust position as needed
                pixmap_item.setFlag(QGraphicsPixmapItem.ItemIsMovable)
                self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().add_image(pixmap_item)

    # this finds the current tab and locates the canvas
    # inside that tab to access its scene
    def undo(self):
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().undo()

    def redo(self):
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().redo()

    def clear_canvas(self):
        self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().clear()

    #Depending on which button is clicked, sets the appropriate flag so that operations
    #don't overlap
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
                self.tabWidget.currentWidget().findChild(QGraphicsView, 'gv_Canvas').scene().set_active_tool("pen")
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
                self.scene.set_active_tool("highlighter")
                self.tb_actionPen.setChecked(False)  # Ensure pen is not active
                self.tb_actionCursor.setChecked(False)
                self.tb_actionEraser.setChecked(False)
            else:
                # Deactivate erasing mode when button is clicked again
                print("Highlighter deactivated")  # Debugging print
                self.scene.set_active_tool(None)

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

    # Function to load the config file
    def load_config(self):
        """Load configuration from a JSON file based on the project directory"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))

            # Traverse up to find the project root directory
            project_root = current_dir
            while not os.path.exists(os.path.join(project_root, 'config.json')):
                project_root = os.path.dirname(project_root)
                if project_root == os.path.dirname(project_root):
                    raise FileNotFoundError("config.json not found in the project directory.")

            print(f"Main.py Project root path: {project_root}")
            config_path = os.path.join(project_root, 'config.json')
            print(f"Main.py config path: {config_path}\n")

            # Load the config file
            with open(config_path, 'r') as config_file:
                config = json.load(config_file)

            ssl_key_path = config.get('ssl_key_path', 'ssl/server.key')
            ssl_cert_path = config.get('ssl_cert_path', 'ssl/server.crt')

            ssl_key_path = os.path.join(project_root, ssl_key_path)
            ssl_cert_path = os.path.join(project_root, ssl_cert_path)

            if not os.path.exists(ssl_key_path):
                raise FileNotFoundError(f"SSL key file not found: {ssl_key_path}")
            if not os.path.exists(ssl_cert_path):
                raise FileNotFoundError(f"SSL certificate file not found: {ssl_cert_path}")

            config['ssl_key_path'] = ssl_key_path
            config['ssl_cert_path'] = ssl_cert_path

            return config
        except FileNotFoundError as e:
            print(f"Error: {str(e)}")
            return {}
        except json.JSONDecodeError:
            print("Error: Failed to decode JSON from the config file.")
            return {}

    # Function to load SSL key and certificate
    def load_ssl_files(self, ssl_key_path, ssl_cert_path):
        """Load SSL key and certificate from files"""
        try:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(certfile=ssl_cert_path, keyfile=ssl_key_path)
            return ssl_context, None
        except Exception as e:
            print(f"Error loading SSL files: {str(e)}")
            return None, None

    # Function to host a collaborative session
    def host_session(self):
        dialog = HostDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            username = dialog.get_username()
            if not self.user_db.user_exists(username):
                self.user_db.add_user(username)

            self.username = username
            port = self.user_reg.register_host(username)

            self.collab_server = CollabServer()
            self.collab_server.port = port

            try:
                # Load SSL configuration
                config = self.load_config()
                ssl_key_path = config.get('ssl_key_path', '')
                ssl_cert_path = config.get('ssl_cert_path', '')

                if not ssl_key_path or not ssl_cert_path:
                    raise RuntimeError("SSL certificate or key path missing in configuration")

                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(certfile=ssl_cert_path, keyfile=ssl_key_path)
                self.collab_server.ssl_context = ssl_context

                # Set the IP address to the real IP address of the host machine
                host_ip = socket.gethostbyname(socket.gethostname())  # Get local IP address
                self.collab_server.host_ip = host_ip
                self.collab_server.start()

                self.collab_server.clientConnected.connect(self._handle_client_connected)
                self.collab_server.clientDisconnected.connect(self._handle_client_disconnected)

                QMessageBox.information(self, "Success", "Successfully started hosting session")
                print(f"Hosting on IP: {host_ip}, Port: {port}")
                self.scene.change_color(QColor("#FF0000"))
            except RuntimeError as e:
                QMessageBox.warning(self, "Error", f"Could not start hosting: {str(e)}")
                print(f"Could not host: {str(e)}")

    # Function to join a collaborative session
    def join_session(self):
        dialog = JoinDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            username = dialog.get_username()
            host_username = dialog.get_host_username()

            if not self.user_db.user_exists(username):
                self.user_db.add_user(username)

            try:
                # Get the IP and port of the host from user registration
                host_address, port = self.user_reg.get_host_address(host_username)
                self.username = username
                self.collab_client = CollabClient(self)

                if self.collab_client.connect_to_host(host_address, port, username):
                    # Load SSL context for client-side secure connection
                    config = self.load_config()
                    ssl_key_path = config.get('ssl_key_path', '')
                    ssl_cert_path = config.get('ssl_cert_path', '')

                    if not ssl_key_path or not ssl_cert_path:
                        raise RuntimeError("SSL certificate or key path missing in configuration")

                    ssl_context, _ = self.load_ssl_files(ssl_key_path, ssl_cert_path)
                    if not ssl_context:
                        raise RuntimeError("Failed to load SSL context. Check the SSL configuration.")

                    if self.collab_client.secure_connect(ssl_context):
                        self.collab_client.drawingReceived.connect(self._handle_remote_drawing)
                        QMessageBox.information(self, "Connected", "Successfully joined session")
                        print(f"Joined session successfully. Host IP: {host_address}, Port: {port}")
                        self.scene.change_color(QColor("#3600FF"))
                    else:
                        QMessageBox.warning(self, "Connection Failed", "Could not connect to host")
                else:
                    QMessageBox.warning(self, "Connection Failed", "Could not connect to host")
            except ValueError:
                QMessageBox.warning(self, "Host Not Found", f"No active session found for user {host_username}")

    # Handle incoming data from the server
    def handle_incoming_data(self, data):
        parsed_data = json.loads(data)
        if parsed_data['type'] == 'drawing':
            self.scene.apply_remote_drawing(parsed_data['data'])

    # Handle remote drawing received from another client
    def _handle_remote_drawing(self, drawing_data: dict):
        self.scene.apply_remote_drawing(drawing_data)

    # Handle client connections
    def _handle_client_connected(self, username: str):
        QMessageBox.information(self, "User Joined", f"{username} joined the session")

    # Handle client disconnections
    def _handle_client_disconnected(self, username: str):
        QMessageBox.information(self, "User Left", f"{username} left the session")

    #Clean up when the window is closed
    def closeEvent(self, event):
        if hasattr(self, 'username'):
            self.user_reg.remove_user(self.username)
        super().closeEvent(event)

    def start_server_after_login(self, username):
        print(f"Starting collaborative server for user: {username}")
        try:
            # Configure and start the server here
            self.collab_server = CollabServer()
            self.collab_server.username = username

            # Load SSL configuration if necessary
            config = self.load_config()
            ssl_key_path = config.get('ssl_key_path', '')
            ssl_cert_path = config.get('ssl_cert_path', '')

            if not ssl_key_path or not ssl_cert_path:
                raise RuntimeError("SSL certificate or key path missing in configuration")

            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.load_cert_chain(certfile=ssl_cert_path, keyfile=ssl_key_path)
            self.collab_server.ssl_context = ssl_context

            # Set the IP address to the real IP address of the host machine
            host_ip = socket.gethostbyname(socket.gethostname())  # Get local IP address
            self.collab_server.host_ip = host_ip
            self.collab_server.start()

            self.collab_server.clientConnected.connect(self._handle_client_connected)
            self.collab_server.clientDisconnected.connect(self._handle_client_disconnected)

            QMessageBox.information(self, "Success", "Successfully started hosting session")
            print(f"Hosting on IP: {host_ip}")
        except RuntimeError as e:
            QMessageBox.warning(self, "Error", f"Could not start hosting: {str(e)}")
            print(f"Could not host: {str(e)}")

    '''
    def host_session(self):
        dialog = HostDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            username = dialog.get_username()
            if not self.user_db.user_exists(username):
                self.user_db.add_user(username)

            self.username = username
            port = self.user_reg.register_host(username)

            self.collab_server = CollabServer(self)
            try:
                self.collab_server.start(port)
                self.collab_server.clientConnected.connect(self._handle_client_connected)
                self.collab_server.clientDisconnected.connect(self._handle_client_disconnected)
                QMessageBox.information(self, "Success",
                                        "Successfully started hosting session")
                print("Hosted successfully")
                self.scene.change_color(QColor("#FF0000"))
            except RuntimeError as e:
                QMessageBox.warning(self, "Error",
                                    f"Could not start hosting: {str(e)}")
                print("Could not host")

    def join_session(self):
        dialog = JoinDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            username = dialog.get_username()
            host_username = dialog.get_host_username()

            if not self.user_db.user_exists(username):
                self.user_db.add_user(username)

            try:
                host_address, port = self.user_reg.get_host_address(host_username)
                self.username = username
                self.collab_client = CollabClient(self)

                if self.collab_client.connect_to_host(host_address, port, username):
                    self.collab_client.drawingReceived.connect(self._handle_remote_drawing)
                    QMessageBox.information(self, "Connected",
                                            "Successfully joined session")
                    print("Joined session successfully")
                    self.scene.change_color(QColor("#3600FF"))
                else:
                    QMessageBox.warning(self, "Connection Failed",
                                        "Could not connect to host")
            except ValueError:
                QMessageBox.warning(self, "Host Not Found",
                                    f"No active session found for user {host_username}")

    def _handle_client_connected(self, username: str):
        QMessageBox.information(self, "User Joined",
                                f"{username} joined the session")

    def _handle_client_disconnected(self, username: str):
        QMessageBox.information(self, "User Left",
                                f"{username} left the session")

    def closeEvent(self, event):
        # Clean up when the window is closed
        if hasattr(self, 'username'):
            self.user_reg.remove_user(self.username)
        super().closeEvent(event)

    def handle_incoming_data(self, data):
        parsed_data = json.loads(data)
        if parsed_data['type'] == 'drawing':
            self.scene.apply_remote_drawing(parsed_data['data'])

    def _handle_remote_drawing(self, drawing_data: dict):
        # Update the canvas with remote drawing data
        self.scene.apply_remote_drawing(drawing_data)
    '''

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec())