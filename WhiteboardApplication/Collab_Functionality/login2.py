import os
import sys
import sqlite3
import bcrypt
import threading
import socket
import time
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QPushButton, QMessageBox
from PySide6.QtGui import QFont, QPainter, QColor, QLinearGradient
from WhiteboardApplication.main import MainWindow
from WhiteboardApplication.Collab_Functionality.discover_server import start_discovery_server
from WhiteboardApplication.Collab_Functionality.utils import ensure_discovery_server
import logging
import requests
import pystun3
import stun
import random
from WhiteboardApplication.Collab_Functionality.turn_server import TURN_SERVER, TURN_PASSWORD, TURN_USERNAME

#install pip install pystun3

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Discovery Server Constants
DISCOVERY_HOST = "127.0.0.1"
DISCOVERY_PORT = 9000

def is_discovery_server_running(host=DISCOVERY_HOST, port=DISCOVERY_PORT):
    """
    Checks if the discovery server is running on the given host and port.
    """
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

def ensure_discover_server(self):
    """
   Ensures the discovery server is running on a valid port.
   """
    host, port = "127.0.0.1", 9000
    if not is_discovery_server_running(host, port):
        try:
            # Dynamically choose a port if the default is unavailable
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as temp_socket:
                temp_socket.bind((host, port))  # Attempt to bind the default port
                temp_socket.listen(5)  # Ensure it's valid
                print(f"Discovery server started on {host}:{port}")
        except OSError:
            # Fall back to a dynamic port
            port = 0  # Let OS pick an available port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as temp_socket:
                temp_socket.bind((host, port))
                temp_socket.listen(5)
                port = temp_socket.getsockname()[1]
                print(f"Discovery server fallback port: {port}")

        threading.Thread(target=start_discovery_server, args=(host, port), daemon=True).start()
        time.sleep(1)  # Allow server time to start
    else:
        logger.info("Discovery server is already running.")

#Sets up the database for the discovery server
def init_discovery_database():
    conn = sqlite3.connect("discovery_users.db")
    cursor = conn.cursor()

    # Creates table for discovery registration if it doesn't already exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS discovery_users (
        username TEXT PRIMARY KEY,
        ip_address TEXT,
        port INTEGER,
        turn_info TEXT)""")

    conn.commit()
    return conn

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
        #Creates Login Window GUI

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
                self.ensure_user_registered_with_discover_server(username)
                QMessageBox.information(self, "Login Success", "Welcome!")
                self.parent().show_whiteboard(username)
            else:
                QMessageBox.warning(self, "Login Failed", "Invalid password. (login)")
        else:
            QMessageBox.warning(self, "Login Failed", "User not found. (login)")

    def get_public_ip_stun(self):
        """
        Retrieves the public IP address and port using a STUN server.
        """
        try:
            nat_type, external_ip, external_port = stun.get_ip_info(stun_host="stun.l.google.com", stun_port=19302)
            logger.info(f"Public IP from STUN: {external_ip}, Port: {external_port}")
            return external_ip, external_port
        except Exception as e:
            logger.error(f"STUN failed: {e}")
            return None, None

    def get_public_ip(self):
        """
        Attempts to retrieve the public IP address using STUN or a fallback service.
        """
        public_ip, public_port = self.get_public_ip_stun()
        if not public_ip:
            try:
                response = requests.get('https://api.ipify.org?format=json', timeout=5)
                response.raise_for_status()
                public_ip = response.json().get('ip')
                logger.info(f"Public IP from fallback: {public_ip}")
            except Exception as e:
                logger.error(f"Failed to get public IP via fallback: {e}")
        return public_ip

    def register(self):
        username = self.username_input.text()
        password = self.password_input.text()
        port = self.get_turn_port()
        ip_address = self.get_public_ip()

        # Debugging: print or log the retrieved public IP address
        print(f"(login) Public IP address: {ip_address}")
        print(f"(login) Port user is registering with is: {port}")

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
            ngrok_url = ""
            self.register_with_discovery_server(username, ip_address, port, ngrok_url)

        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Error", "Username already exists. (login)")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred (login): {e}")

    def register_with_discovery_server(self, username, ip_address, port, ngrok_url):
        """
        Registers the user with the discovery server, including TURN details.
        """
        if not ip_address or not port:
            logger.warning("Invalid IP or port for registration.")
            return

        # Store information in discovery_users.db
        conn = init_discovery_database()
        cursor = conn.cursor()

        turn_info = f"{TURN_SERVER} {TURN_USERNAME} {TURN_PASSWORD}"

        try:
            # Store in discovery-specific database
            cursor.execute(
                "INSERT OR REPLACE INTO discovery_users (username, ip_address, port, turn_info, ngrok_url) VALUES (?, ?, ?, ?, ?)",
                (username, ip_address, port, turn_info, ngrok_url))
            conn.commit()

            # Optionally, send the registration details to the discovery server
            with socket.create_connection((DISCOVERY_HOST, DISCOVERY_PORT)) as sock:
                register_message = f"REGISTER {username} {ip_address} {port} {turn_info} {ngrok_url}\n"
                sock.sendall(register_message.encode())
                response = sock.recv(1024).decode().strip()
                if response == "OK":
                    logger.info(f"Successfully registered {username} with discovery server.")
                else:
                    logger.error(f"Registration failed: {response}")
        except Exception as e:
            logger.error(f"Error during discovery registration: {e}")
        finally:
            cursor.close()
            conn.close()

    def ensure_user_registered_with_discover_server(self, username):
        """
        Ensure the user is registered with the discovery server if not already.
        """
        try:
            with socket.create_connection((DISCOVERY_HOST, DISCOVERY_PORT)) as sock:
                sock.sendall(f"LOOKUP {username}\n".encode())
                response = sock.recv(1024).decode().strip()

                if response == "NOT_FOUND":
                    ip_address = self.get_public_ip()
                    port = self.get_turn_port()
                    self.register_with_discovery_server(username, ip_address, port)
                else:
                    logger.info(f"{username} is already registered with the discovery server.")
        except Exception as e:
            logger.error(f"Discovery server lookup failed: {e}")

    def get_turn_port(self):
        """
         Gets a local port for outbound TURN server communication.
         Returns: int - An available local port
        """
        try:
            # Create a socket to find an available port
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.bind(('', 0))  # Binds to any available port
                _, port = s.getsockname()
                return port
        except Exception as e:
            logger.error(f"Error getting local port: {e}")
            # Fallback to a random port in the dynamic range
            return random.randint(5000, 65535)

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
        print("Username entered by user is (login): "+ self.username)
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