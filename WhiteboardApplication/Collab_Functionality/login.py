import sys
import sqlite3
import bcrypt
import json
import threading
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QPushButton, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPainter, QColor, QLinearGradient
from WhiteboardApplication.Collab_Functionality.collab_manager import CollabServer, CollabClient
from WhiteboardApplication.main import MainWindow
from WhiteboardApplication.board_scene import BoardScene


# Database initialization
def init_database():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


# Password encryption
def encrypt_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(stored_hash, password):
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except Exception as e:
        print(f"Password check error: {e}")
        return False


class LoginWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Creates window
        self.setWindowTitle("Login")
        self.setMinimumSize(1060, 702)

        self.client = None

        # Layout setup
        layout = QVBoxLayout()

        # Username Section
        self.username_input = QLineEdit()
        self.username_input.setFixedHeight(50)
        self.username_input.setPlaceholderText("Username")
        self.username_input.setFont(QFont("Arial", 12))
        self.username_input.setStyleSheet("QLineEdit { padding: 10px 20px; margin-left: 30px; margin-right: 30px;}")
        layout.addWidget(self.username_input)

        # Password Section
        self.password_input = QLineEdit()
        self.password_input.setFixedHeight(50)
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFont(QFont("Arial", 12))
        self.password_input.setStyleSheet("QLineEdit { padding: 10px 20px; margin-left: 30px; margin-right: 30px;}")
        layout.addWidget(self.password_input)

        # Login Button
        self.login_button = QPushButton("LOGIN")
        self.login_button.setFixedHeight(50)
        self.login_button.clicked.connect(self.login)
        self.login_button.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; padding: 10px 20px; font-size: 20px; margin-left: 30px; margin-right: 30px; font-weight: bold;}")
        layout.addWidget(self.login_button)

        # Register Button
        self.register_button = QPushButton("REGISTER")
        self.register_button.setFixedHeight(50)
        self.register_button.clicked.connect(self.register)
        self.register_button.setStyleSheet(
            "QPushButton { background-color: #4682B4; color: white; padding: 10px 20px; font-size: 20px; margin-left: 30px; margin-right: 30px; font-weight: bold;}")
        layout.addWidget(self.register_button)

        self.setLayout(layout)

        self.setLayout(layout)
        self.db_conn = init_database()
        self.client = CollabClient()

    def paintEvent(self, event):
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(30, 30, 30))
        gradient.setColorAt(1.0, QColor(70, 70, 250))

        painter = QPainter(self)
        painter.setBrush(gradient)
        painter.drawRect(self.rect())
        super().paintEvent(event)

    '''
    def login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()

        if result and check_password(result[0], password):
            self.client = CollabClient()  # Initialize the client on successful login

            try:
                self.client.connect()  # Attempt to connect to the server
                self.client.send(f"LOGIN {username}")  # Send login message
                QMessageBox.information(self, "Login Successful", "Welcome!")
                self.parent().show_whiteboard(self.client)  # Pass client to parent
            except Exception as e:
                QMessageBox.critical(self, "Connection Failed", f"Error: {e}")
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")
    '''

    def login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()

        if result and check_password(result[0], password):
            self.client = CollabClient()  # Initialize the client on successful login

            try:
                self.client.connect()  # Attempt to connect to the server
                self.client.send(f"LOGIN {username}")  # Send login message
                QMessageBox.information(self, "Login Successful", "Welcome!")
                self.parent().show_whiteboard(self.client)  # Pass client to parent
            except Exception as e:
                QMessageBox.critical(self, "Connection Failed", f"Error: {e}")
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password.")

    def register(self):
        username = self.username_input.text()
        password = self.password_input.text()
        cursor = self.db_conn.cursor()

        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                           (username, encrypt_password(password)))
            self.db_conn.commit()
            QMessageBox.information(self, "Registration Successful", "User registered!")
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Registration Failed", "Username already exists.")


class ApplicationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Collaborative Whiteboard")
        self.setGeometry(100, 100, 800, 600)
        self.login_window = LoginWindow(self)
        self.setCentralWidget(self.login_window)

        self.client = None

    def show_whiteboard(self, client):
        #if self.client:
        print("Transitioning to whiteboard...")
        self.main_window = MainWindow()
        self.setCentralWidget(self.main_window)
            #self.board_scene = BoardScene()
            #self.main_window.set_client(self.client)  # Pass the client to the whiteboard
            #self.close()  # Close the login window


def start_server():
    print("Server started in login")
    server = CollabServer()
    server.start()


def main():
    # Start the server in a separate thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Start the application
    app = QApplication(sys.argv)
    window = ApplicationWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()