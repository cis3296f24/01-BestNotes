import sqlite3
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton, QLabel, QHBoxLayout, QDialog

'''
class HostWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Host: Add Guests")
        self.setGeometry(300, 300, 400, 200)

        # UI Elements
        self.layout = QVBoxLayout()

        self.guest_input = QLineEdit(self)
        self.guest_input.setPlaceholderText("Enter guest's name")

        self.add_button = QPushButton("Add Guest", self)
        self.error_label = QLabel("", self)

        self.layout.addWidget(self.guest_input)
        self.layout.addWidget(self.add_button)
        self.layout.addWidget(self.error_label)

        # Connect button to function
        self.add_button.clicked.connect(self.add_guest)

        self.setLayout(self.layout)

        # List of valid guests
        self.valid_guests = []

    def check_user_in_db(self, name):
        """Check if the user exists in the database."""
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (name,))
        exists = cursor.fetchone()[0] > 0
        conn.close()
        return exists

    def add_guest(self):
        """Add a guest if they exist in the database."""
        guest_name = self.guest_input.text().strip()

        if not guest_name:
            self.error_label.setText("Please enter a name!")
            return

        # Check if the name is in the database
        if self.check_user_in_db(guest_name):
            self.valid_guests.append(guest_name)
            self.error_label.setText(f"Guest '{guest_name}' added successfully!")
            self.guest_input.clear()  # Clear input field
        else:
            self.error_label.setText(f"Error: '{guest_name}' not found in database. Try again.")

# Create the application and window
app = QApplication([])
window = HostWindow()
window.show()

app.exec()
'''
class HostWindow(QDialog):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Host: Add Guests")
        self.setGeometry(300, 300, 400, 200)

        # UI Elements
        self.layout = QVBoxLayout()
        self.guest_input = QLineEdit(self)
        self.guest_input.setPlaceholderText("Enter guest's name")
        self.add_button = QPushButton("Add Guest", self)
        self.error_label = QLabel("", self)

        self.layout.addWidget(self.guest_input)
        self.layout.addWidget(self.add_button)
        self.layout.addWidget(self.error_label)

        self.setLayout(self.layout)

        # Connect button to function
        self.add_button.clicked.connect(self.add_guest)

        # Track valid guests
        self.valid_guests = []
        self.max_guests = 7  # Limit to 7 valid guests

    def add_guest(self):
        """Add a guest if they exist in the database."""
        guest_name = self.guest_input.text().strip()

        if not guest_name:
            self.error_label.setText("Please enter a name!")
            return

        # Check if the name is in the database (simulated here)
        if len(self.valid_guests) < self.max_guests:
            if self.check_user_in_db(guest_name):
                self.valid_guests.append(guest_name)
                self.error_label.setText(f"Guest '{guest_name}' added successfully!")
                self.guest_input.clear()  # Clear input field
            else:
                self.error_label.setText(f"Error: '{guest_name}' not found in database. Try again.")
        else:
            self.error_label.setText(f"Error: You can only add up to {self.max_guests} guests.")

    def check_user_in_db(self, name):
        """Check if the user exists in the database (mock check)."""
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (name,))
        exists = cursor.fetchone()[0] > 0
        conn.close()
        return exists  # Example valid names

    def get_valid_guests(self):
        """Return the list of valid guests."""
        return self.valid_guests