import socketserver
import threading

import socketserver
import threading
import socket
import sqlite3
from typing import Type
import logging

class DiscoveryHandler(socketserver.BaseRequestHandler):
    def setup(self):
        # Initialize the database connection when handling a request
        self.db_conn = sqlite3.connect("users.db")
        self.cursor = self.db_conn.cursor()

    def finish(self):
        # Close the database connection after finishing a request
        self.cursor.close()
        self.db_conn.close()

    def handle(self):
        try:
            # Receive the command and arguments from the request
            data = self.request.recv(1024).decode().strip()

            if not data:  # Check if no data was received
                print(f"Error: No data received (discover_server)")
                self.request.sendall(b"ERROR: No data received\n")
                return

            command, *args = data.split()

            print(f"Received command (discover_server): {command} with args: {args}")

            # Process the command
            if command == "REGISTER":
                if len(args) == 2:
                    username, port = args
                    client_ip = self.client_address[0]
                    print(f"(discover_server) Registering user {username} at {client_ip}:{port}")
                    self.register_user(username, client_ip, int(port))
                    self.request.sendall(b"OK\n")
                else:
                    self.request.sendall(b"ERROR: Invalid REGISTER command format\n")

            elif command == "LOOKUP":
                if len(args) == 1:
                    username = args[0]
                    print(f"Looking up user {username}")
                    result = self.lookup_user(username)
                    if result:
                        ip, port = result
                        response = f"{ip}:{port}\n"
                        print(f"Found user: {response}")
                        self.request.sendall(response.encode())
                    else:
                        print(f"User {username} not found (discover_server)")
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

    def register_user(self, username, ip, port):
        try:
            # Change 'user_registry' to 'users'
            self.cursor.execute(
                "INSERT OR REPLACE INTO users (username, ip_address, port) VALUES (?, ?, ?)",
                (username, ip, port),
            )
            self.db_conn.commit()
        except sqlite3.Error as e:
            print(f"Database error during registration (discover_server): {e}")

    def lookup_user(self, username):
        # Change 'user_registry' to 'users'
        self.cursor.execute("SELECT ip_address, port FROM users WHERE username = ?", (username,))
        return self.cursor.fetchone()

    def deregister_user(self, username):
        # Change 'user_registry' to 'users'
        self.cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        self.db_conn.commit()
        return self.cursor.rowcount > 0

def init_user_registry_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        ip_address TEXT,
        port INTEGER)""")

    conn.commit()
    conn.close()

'''
def start_discovery_server(port=9000):
    # Initialize the user registry database
    init_user_registry_db()
    try:
        # Start the threaded TCP server with the handler class
        server = socketserver.ThreadingTCPServer(('0.0.0.0', port), DiscoveryHandler)
        print(f"Discovery server running on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"Error starting discovery server (discover_server): {e}")
    finally:
        # Ensure server shutdown properly
        print("Shutting down discovery server.")
        server.server_close()
        server.socket.close()
'''
def start_discovery_server(port=9000):
    init_user_registry_db()
    try:
        # Bind to all interfaces
        server = socketserver.ThreadingTCPServer(('0.0.0.0', port), DiscoveryHandler)
        print(f"Discovery server running on port {port}")
        server.serve_forever()
    except Exception as e:
        print(f"Error starting discovery server: {e}")
    finally:
        print("Shutting down discovery server.")
        server.server_close()
        server.socket.close()
if __name__ == "__main__":
    start_discovery_server()
