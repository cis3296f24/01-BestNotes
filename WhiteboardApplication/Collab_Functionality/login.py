import sys
import sqlite3
from PySide6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QVBoxLayout, QLineEdit, QPushButton, QMessageBox
)
from PySide6.QtGui import QFont, QColor, QPalette, QLinearGradient, QBrush, QPainter
import bcrypt

from WhiteboardApplication.main import MainWindow, BoardScene

#Sets up the sqlite database to hold user information
def init_database():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    #Creates table if it doesn't already exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

# Encrypts password with bcrypt
def encrypt_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# Verifies entered password against the stored hash
def check_password(stored_hash, password):
    return bcrypt.checkpw(password.encode(), stored_hash.encode())

# Login Window
class LoginWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        #Creates window
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

    #Draws and resizes the background color
    def paintEvent(self, event):
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(0, 0, 0))  # Black
        gradient.setColorAt(1.0, QColor(65, 105, 225))  # Royal Blue at the bottom

        painter = QPainter(self)
        painter.setBrush(gradient)
        painter.drawRect(self.rect())  # Fill the entire widget with the gradient

        super().paintEvent(event)

    #Method to log a user in
    def login(self):

        #gets username and password, and sets cursor to search for the credentials
        username = self.username_input.text()
        password = self.password_input.text()
        cursor = self.db_conn.cursor()

        #Checks if the credentials are there
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()

        #Checks if the decrypted password matches what the user entered
        if result:
            stored_password = result[0]
            try:
                if check_password(stored_password) == password:
                    QMessageBox.information(self, "Login Success", "Welcome!")
                    self.parent().show_whiteboard()  # Parent is the ApplicationWindow
                else:
                    QMessageBox.warning(self, "Login Failed", "Invalid password.")
            except Exception:
                QMessageBox.warning(self, "Error", "Failed to decrypt password.")
        else:
            QMessageBox.warning(self, "Login Failed", "User not found.")

    #Allows a new user to register their credentials
    def register(self):

        #Accepts username and password, and sets the cursor in the database to add these credentials
        username = self.username_input.text()
        password = self.password_input.text()
        cursor = self.db_conn.cursor()

        #Inserts the new credentials and notifies user of status of registration
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, encrypt_password(password)))
            self.db_conn.commit()
            QMessageBox.information(self, "Registration Success", "User registered successfully!")

        #Stops if a user tries to register when they already have an account
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Error", "Username already exists.")

#Application window, where the application is run from
class ApplicationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Collaborative Whiteboard")

        #Creates the login window, board scene, and main window
        self.login_window = LoginWindow(self)
        self.board_scene = BoardScene()
        self.main_window = MainWindow()  # Import your MainWindow properly

        # Start with login window
        self.setCentralWidget(self.login_window)

    def show_whiteboard(self):
        # Switches to whiteboard once login is done correctly
        self.setCentralWidget(self.main_window)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = ApplicationWindow()
    main_window.show()
    sys.exit(app.exec())
