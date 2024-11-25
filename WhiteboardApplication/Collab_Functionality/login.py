import sys
import sqlite3
import bcrypt
import threading
import socket
import time
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QPushButton, QMessageBox
from PySide6.QtGui import QFont, QPainter, QColor, QLinearGradient
from WhiteboardApplication.main2 import MainWindow
from WhiteboardApplication.Collab_Functionality.discover_server import start_discovery_server
from WhiteboardApplication.Collab_Functionality.utils import ensure_discovery_server
import logging
import requests

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Check if discovery server is running
def is_discovery_server_running(host="127.0.0.1", port=9000):
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except (socket.timeout, ConnectionRefusedError):
        return False

def ensure_user_registered_with_discovery_server(self, username):
    try:
        # Check if the server is running before connecting
        with socket.create_connection(('localhost', 9000)) as sock:
            print("Connected to discovery server")
            # Continue with registration logic...
    except ConnectionRefusedError as e:
        print("Error: Could not connect to the discovery server. Is it running?")
        # Handle the case where the server is not available (maybe retry or alert the user)
    except Exception as e:
        print(f"Unexpected error: {e}")

def ensure_discovery_server():
    if not is_discovery_server_running():
        logger.info("Discovery server is not running. Starting it now...")
        threading.Thread(target=start_discovery_server, daemon=True).start()
        time.sleep(1)  # Give the server a moment to start
    else:
        logger.info("Discovery server is already running.")

# Sets up the sqlite database to hold user information
def init_database():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Creates table if it doesn't already exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        ip_address TEXT,
        port INTEGER)""")

    conn.commit()
    return conn

# Encrypts password with bcrypt
def encrypt_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# Verifies entered password against the stored hash
def check_password(stored_hash, password):
    try:
        # Check if the entered password matches the stored hash
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except Exception as e:
        # General exception handler for unexpected errors
        print(f"Error during password check: {e}")
        return False

# Login Window
class LoginWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Creates window
        self.setWindowTitle("Login")
        self.setMinimumSize(1060, 702)

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
        self.db_conn = init_database()

    # Draws and resizes the background color
    def paintEvent(self, event):
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(0, 0, 0))  # Black
        gradient.setColorAt(1.0, QColor(65, 105, 225))  # Royal Blue at the bottom

        painter = QPainter(self)
        painter.setBrush(gradient)
        painter.drawRect(self.rect())  # Fill the entire widget with the gradient

        super().paintEvent(event)

    def login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        cursor = self.db_conn.cursor()

        # Check if user exists in local database
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()

        if result:
            stored_password = result[0]
            if check_password(stored_password, password):
                # After successful login, ensure the user is registered with the discovery server
                self.ensure_user_registered_with_discovery_server(username)
                QMessageBox.information(self, "Login Success", "Welcome!")
                self.parent().show_whiteboard(username)
            else:
                QMessageBox.warning(self, "Login Failed", "Invalid password. (login)")
        else:
            QMessageBox.warning(self, "Login Failed", "User not found. (login)")

    def get_public_ip(self):
        try:
            # Use an external service to fetch the public IP
            response = requests.get('https://api.ipify.org?format=json')
            response.raise_for_status()  # Raise an error for HTTP issues
            public_ip = response.json().get('ip')  # Extract the IP from the JSON response

            # Debugging: log the response
            print(f"Received public IP: {public_ip}")

            return public_ip
        except requests.RequestException as e:
            QMessageBox.critical(None, "Error", f"Failed to retrieve public IP address: {e}")
            return None

    def register(self):
        username = self.username_input.text()
        password = self.password_input.text()
        port = self.get_user_port()
        ip_address = self.get_public_ip()

        # Debugging: print or log the retrieved public IP address
        print(f"Public IP address: {ip_address}")

        if ip_address is None or port is None:
            QMessageBox.warning(self, "Error", "Unable to retrieve public IP or user port. Please try again.")
            return

        cursor = self.db_conn.cursor()

        # Insert user into local database (users.db)
        try:
            cursor.execute(
                "INSERT INTO users (username, password, ip_address, port) VALUES (?, ?, ?, ?)",
                (username, encrypt_password(password), ip_address, port)
            )
            self.db_conn.commit()
            QMessageBox.information(self, "Registration Success", "User registered successfully!")

            # After registration, register user with the discovery server
            self.register_with_discovery_server(username, ip_address, port)

        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Error", "Username already exists.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred (login): {e}")

    '''
    def register(self):
        username = self.username_input.text()
        password = self.password_input.text()
        port = self.get_user_port()
        ip_address = socket.gethostbyname(socket.gethostname())

        if port is None:
            QMessageBox.warning(self, "Error", "Unable to retrieve user port. Please try again. (login)")
            return

        cursor = self.db_conn.cursor()

        # Insert user into local database (users.db)
        try:
            cursor.execute(
            "INSERT INTO users (username, password, ip_address, port) VALUES (?, ?, ?, ?)",
            (username, encrypt_password(password), ip_address, port)
            )
            self.db_conn.commit()
            QMessageBox.information(self, "Registration Success", "User registered successfully!")

            # After registration, register user with the discovery server
            self.register_with_discovery_server(username, ip_address, port)

        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Error", "Username already exists.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred (login): {e}")
    '''
    def register_with_discovery_server(self, username, ip_address, port):
        try:
            # Send REGISTER command to discovery server
            with socket.create_connection(('localhost', 9000)) as sock:
                sock.sendall(f"REGISTER {username} {port}\n".encode())
                response = sock.recv(1024).decode().strip()
                if response == "OK":
                    print(f"User {username} registered successfully with discovery server. (login)")
                else:
                    print(f"Error registering user {username} with discovery server (login): {response}")
        except Exception as e:
            print(f"Error connecting to discovery server (login): {e}")

    def ensure_user_registered_with_discovery_server(self, username):
        # Send LOOKUP command to discovery server
        with socket.create_connection(('localhost', 9000)) as sock:
            sock.sendall(f"LOOKUP {username}\n".encode())
            response = sock.recv(1024).decode().strip()
            if response == "NOT_FOUND":
                print(f"User {username} not registered with discovery server. Registering now...")
                # Register the user if not found
                ip_address = socket.gethostbyname(socket.gethostname())
                port = self.get_user_port()
                self.register_with_discovery_server(username, ip_address, port)
            else:
                print(f"User {username} found on discovery server (login): {response}")

    def get_user_port(self):
        """
        Retrieves the port number from which the user is connecting.
        Returns:
            int: The port number of the current connection.
        """
        # Example logic for retrieving the port
        try:
            # Create a temporary socket to determine the port dynamically
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as temp_socket:
                # Bind the socket to an available port on localhost
                temp_socket.bind(('localhost', 0))  # Port 0 tells OS to find an available port
                port = temp_socket.getsockname()[1]  # Retrieve the assigned port

            return port
        except socket.error as e:
            print(f"Error retrieving user port (login): {e}")
            return None  # Or handle error as needed

# Application window, where the application is run from
class ApplicationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Collaborative Whiteboard")

        # Creates the login window, board scene, and main window
        self.login_window = LoginWindow(self)
        self.main_window = MainWindow()  # Import your MainWindow properly

        # Start with login window
        self.setCentralWidget(self.login_window)

    def show_whiteboard(self, username):
        # Switches to whiteboard once login is done correctly
        self.username = username
        print("Username entered by user is: "+ self.username)
        self.main_window.set_username(username)
        self.setCentralWidget(self.main_window)

def main():
    ensure_discovery_server()

    app = QApplication(sys.argv)
    main_window = ApplicationWindow()
    main_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()