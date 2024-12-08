import sys
import os
import bcrypt
import requests
import json
import firebase_admin
from firebase_admin import credentials, auth, db, initialize_app
#import pyrebase
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton, QMessageBox, QMainWindow
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QFont, QLinearGradient

from WhiteboardApplication.main2 import MainWindow
from WhiteboardApplication.board_scene import BoardScene

# Get Firebase credentials from environment variable
firebase_credentials_json = os.getenv('FIREBASE_CREDENTIALS_JSON')

# Write the credentials to a temporary file
with open('firebase-credentials.json', 'w') as f:
    f.write(firebase_credentials_json)

# Initialize Firebase app using the credentials
cred = credentials.Certificate('firebase-credentials.json')
firebase_app = initialize_app(cred, {
    'databaseURL': 'https://bestnotes-3e99f-default-rtdb.firebaseio.com/'
})

ref = db.reference('/users')
print(ref.get())

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

        # Email Section
        self.email_input = QLineEdit()
        self.email_input.setFixedHeight(50)
        self.email_input.setPlaceholderText("Email")
        self.email_input.setFont(QFont("Arial", 12))
        self.email_input.setStyleSheet("QLineEdit { padding: 10px 20px; margin-left: 30px; margin-right: 30px;}")
        layout.addWidget(self.email_input)

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
        email = self.email_input.text()
        password = self.password_input.text()

        FIREBASE_API_KEY = os.getenv('FIREBASE_API_KEY')
        # Firebase API URL with the web API key
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"

        # Prepare the login request body
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True  # This ensures the response includes the ID token
        }

        try:
            # Send POST request to Firebase Authentication API
            response = requests.post(url, json=payload)

            # Check if login is successful
            if response.status_code == 200:
                # Get the ID token from the response
                data = response.json()
                id_token = data.get('idToken')

                # Now verify the ID token using your existing function
                if self.verify_id_token(id_token):
                    QMessageBox.information(self, "Login Success", f"Welcome, {email}!")
                    self.parent().show_whiteboard(email)  # Proceed to next window
                else:
                    QMessageBox.warning(self, "Login Failed", "Invalid token verification.")
            else:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', 'Unknown error')
                QMessageBox.warning(self, "Login Failed", f"Authentication failed: {error_message}")
        except requests.exceptions.RequestException as e:
            QMessageBox.warning(self, "Login Failed", f"Error: {str(e)}")

    def verify_id_token(self, id_token):
        try:
            # Call Firebase Admin SDK to verify the ID token
            user_info = auth.verify_id_token(id_token)
            print(f"User ID: {user_info['uid']}")
            return True
        except firebase_admin.auth.InvalidIdTokenError:
            print("Invalid token")
            return False

    def register(self):
        email = self.email_input.text()
        password = self.password_input.text()

        try:
            # Create the user in Firebase Authentication
            user = auth.create_user(
                email=email,
                password=password)

            # Store additional user data in Firebase Realtime Database
            db_ref = db.reference('users').child(user.uid)
            db_ref.set({
                'email': email
            })

            QMessageBox.information(self, "Registration Success", "User registered successfully!")

        except Exception as e:
            QMessageBox.warning(self, "Registration Failed", f"Error: {str(e)}")

# Application window, where the application is run from
class ApplicationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Collaborative Whiteboard")

        self.user_email = None  # Store the email here

        # Creates the login window, board scene, and main window
        self.login_window = LoginWindow(self)
        self.board_scene = BoardScene()
        self.main_window = MainWindow()  # Import your MainWindow properly
        # Start with login window
        self.setCentralWidget(self.login_window)

    def show_whiteboard(self, email):
        # Switches to whiteboard once login is done correctly
        self.user_email= email
        print("Email entered by user is (login): " + self.user_email)
        self.main_window.set_user_email(self.user_email)
        self.setCentralWidget(self.main_window)


def main():
    app = QApplication(sys.argv)
    main_window = ApplicationWindow()
    main_window.show()
    sys.exit(app.exec())

# Optional: make this the default entry point if running as a script
if __name__ == "__main__":
    main()
