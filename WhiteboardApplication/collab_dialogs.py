from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit,
                               QPushButton, QMessageBox)

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton
from PySide6.QtNetwork import QHostAddress

import json
import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton
from PySide6.QtNetwork import QHostAddress

class HostDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Host Collaboration")
        layout = QVBoxLayout(self)

        self.username_label = QLabel("Enter your username:")
        self.username_input = QLineEdit()
        self.host_button = QPushButton("Host Session")

        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.host_button)

        self.host_button.clicked.connect(self.accept)

    def get_username(self) -> str:
        return self.username_input.text()

class JoinDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Join Collaboration")
        layout = QVBoxLayout(self)

        self.username_label = QLabel("Enter your username:")
        self.username_input = QLineEdit()
        self.host_username_label = QLabel("Host's username:")
        self.host_username_input = QLineEdit()
        self.join_button = QPushButton("Join Session")

        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.host_username_label)
        layout.addWidget(self.host_username_input)
        layout.addWidget(self.join_button)

        self.join_button.clicked.connect(self.accept)

    def get_username(self) -> str:
        return self.username_input.text()

    def get_host_username(self) -> str:
        return self.host_username_input.text()

class UserRegistry:
    REGISTRY_FILE = "session_registry.json"

    def __init__(self):
        self._default_port = 5050
        self._current_port = self._default_port
        self._load_registry()

    def _load_registry(self):
        """Load the registry from file"""
        try:
            if os.path.exists(self.REGISTRY_FILE):
                with open(self.REGISTRY_FILE, 'r') as f:
                    self._users = json.load(f)
            else:
                self._users = {}
        except Exception:
            self._users = {}

    def _save_registry(self):
        """Save the registry to file"""
        try:
            with open(self.REGISTRY_FILE, 'w') as f:
                json.dump(self._users, f)
        except Exception as e:
            print(f"Error saving registry: {e}")

    def register_host(self, username: str) -> int:
        """Register a host user and assign them a port"""
        port = self._current_port
        self._users[username] = ["127.0.0.1", port]  # Use list instead of tuple for JSON serialization
        self._current_port += 1
        self._save_registry()
        return port

    def get_host_address(self, username: str) -> tuple[str, int]:
        """Get the host address and port for a given username"""
        self._load_registry()  # Reload to get latest data
        if username not in self._users:
            raise ValueError(f"No host found with username: {username}")
        host, port = self._users[username]
        return host, port

    def remove_user(self, username: str):
        """Remove a user from the registry"""
        if username in self._users:
            del self._users[username]
            self._save_registry()