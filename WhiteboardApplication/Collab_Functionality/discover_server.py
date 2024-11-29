import socketserver
import threading

import socketserver
import threading
import socket
import sqlite3
from typing import Type
import logging
from WhiteboardApplication.Collab_Functionality.turn_server import TURN_SERVER, TURN_PASSWORD, TURN_USERNAME

import socketserver
import sqlite3
import json

#TURN_SERVER =
#TURN_USERNAME = "your_turn_username"
#TURN_PASSWORD = "your_turn_password"

class DiscoveryHandler(socketserver.BaseRequestHandler):
    def setup(self):
        # Initialize the database connection
        self.db_conn = sqlite3.connect("discovery_users.db")
        self.cursor = self.db_conn.cursor()

    def finish(self):
        # Close the database connection
        self.cursor.close()
        self.db_conn.close()

    def handle(self):
        try:
            # Receive the command and arguments
            data = self.request.recv(1024).decode().strip()

            if not data:
                print(f"Error: No data received (discover_server)")
                self.request.sendall(b"ERROR: No data received\n")
                return

            command, *args = data.split()

            print(f"(discover_server)Received command: {command} with args: {args}")

            if command == "REGISTER":
                if len(args) >= 4:  # We expect at least username, IP, port, and TURN info
                    username = args[0]
                    ip = args[1]
                    port = int(args[2])
                    turn_info = ' '.join(args[3:])  # Combine remaining parts as TURN info
                    print(f" (discover_server) Registering user {username} at {ip}:{port} with TURN info: {turn_info}")
                    if self.lookup_user(username):
                        print(f"User {username} is already registered. (discover_server)")
                        self.request.sendall(b"ALREADY_REGISTERED\n")
                    else:
                        self.register_user(username, ip, port, turn_info)
                else:
                    self.request.sendall(b"ERROR: Invalid REGISTER command format\n")

            # Handle other commands (LOOKUP, DEREGISTER)
            elif command == "LOOKUP":
                if len(args) == 1:
                    username = args[0]
                    print(f"(discover_server) Looking up user {username}")
                    result = self.lookup_user(username)
                    if result:
                        ip, port, _ = result  # Ignore TURN info for simplicity
                        response = f"{ip}:{port}\n"  # Send only the required data
                        self.request.sendall(response.encode())
                    else:
                        self.request.sendall(b"NOT_FOUND\n")
                else:
                    self.request.sendall(b"ERROR: Invalid LOOKUP command format\n")

            elif command == "DEREGISTER":
                if len(args) == 1:
                    username = args[0]
                    if self.deregister_user(username):
                        self.request.sendall(b"OK\n")
                    else:
                        self.request.sendall(b"ERROR: Username not found\n")
                else:
                    self.request.sendall(b"ERROR: Invalid DEREGISTER command format\n")

            else:
                self.request.sendall(b"ERROR: Unknown command\n")
        except Exception as e:
            print(f"Error handling request (discover_server): {e}")
            self.request.sendall(b"ERROR: Internal server error\n")

    def register_user(self, username, ip, port, turn_info):
        try:
            if not username or not ip or not port:
                self.request.sendall(b"ERROR: Invalid registration format\n")
                return

            # Use the provided TURN info
            print(f"(discover_server) Registering user {username} at {ip}:{port} with TURN info: {turn_info}")

            # Register the user in the database (discovery_users.db)
            self.cursor.execute(
                "INSERT OR REPLACE INTO discovery_users (username, ip_address, port, turn_info) VALUES (?, ?, ?, ?)",
                (username, ip, port, turn_info)
            )
            self.db_conn.commit()

            # Send success message
            self.request.sendall(f"OK | TURN INFO: {turn_info}\n".encode())
        except sqlite3.Error as e:
            self.request.sendall(b"ERROR: Database error during registration\n")
            print(f"(discover_server) Database error during registration: {e}")

    def lookup_user(self, username):
        self.cursor.execute("SELECT ip_address, port FROM discovery_users WHERE username = ?", (username,))
        user_info = self.cursor.fetchone()

        if user_info:
            ip, port = user_info
            # Append TURN server information to the result
            turn_info = f"{TURN_SERVER} {TURN_USERNAME} {TURN_PASSWORD}"
            return ip, port, turn_info
        return None

    def deregister_user(self, username):
        # Change 'user_registry' to 'users'
        self.cursor.execute("DELETE FROM discovery_users WHERE username = ?", (username,))
        self.db_conn.commit()
        return self.cursor.rowcount > 0

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

def start_discovery_server(port=9000):
    init_discovery_database()
    try:
        # Bind to all interfaces
        server = socketserver.ThreadingTCPServer(('0.0.0.0', port), DiscoveryHandler)
        print(f"(discover_server) Discovery server running on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"(discover_server) Error starting discovery server: {e}")
    finally:
        print("(discover_server) Shutting down discovery server.")
        server.server_close()
        server.socket.close()

if __name__ == "__main__":
    start_discovery_server()
