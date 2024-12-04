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

logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to capture all logs
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]  # Logs will be displayed in the console
)

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
                client_address = self.client_address[0]
                logging.error(
                    "No data received. Possible issues: network error, client misbehavior, or timeout. "
                    f"Client address: {client_address}, Socket status: {self.request}")
                self.request.sendall(b"ERROR: No data received\n")
                return

            command, *args = data.split()

            logging.info(f"Received command: {command} with args: {args} from {self.client_address}")

            if command == "REGISTER":
                # Expecting at least 5 arguments (username, IP, port, TURN info, ngrok URL)
                if len(args) >= 5:
                    
                    username = args[0]
                    ip = args[1]
                    port = int(args[2])
                    # If there are more than 4 args, the last one is the ngrok URL
                    ngrok_url = args[-1]
                    turn_info = ' '.join(args[3:-1])  # Combine all middle parts as TURN info
                    logging.debug(f"Registering user {username} at {ip}:{port} with TURN info: {turn_info} and ngrok URL: {ngrok_url}")
                    self.register_user(username, ip, port, turn_info, ngrok_url)
                else:
                    self.request.sendall(b"ERROR: Invalid REGISTER command format\n")


            # Handle other commands (LOOKUP, DEREGISTER)
            elif command == "LOOKUP":
                if len(args) == 1:
                    username = args[0]
                    logging.info(f"Looking up user {username}")
                    result = self.lookup_user(username)
                    if result:
                        # result is already a formatted string from lookup_user
                        response = result  # Simply use the result directly as the response
                        logging.info(f"Response to be sent by discovery server is {response}")
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
            logging.exception(f"Error handling request: {e}")
            self.request.sendall(b"ERROR: Internal server error\n")

    def register_user(self, username, ip, port, turn_info, ngrok_url):
        try:
            if not username or not ip or not port or not ngrok_url:
                self.request.sendall(b"ERROR: Invalid registration format\n")
                return

            logging.debug(
                f"Registering/updating user {username} at {ip}:{port} with TURN info: {turn_info} and ngrok URL: {ngrok_url}")

            # Always update or insert the user's information in the database
            self.cursor.execute(
                "INSERT OR REPLACE INTO discovery_users (username, ip_address, port, turn_info, ngrok_url) VALUES (?, ?, ?, ?, ?)",
                (username, ip, port, turn_info, ngrok_url)
            )

            self.db_conn.commit()
            logging.debug(f"User {username} registration successful, committed to the database.")

            self.request.sendall(b"OK\n")
        except sqlite3.Error as e:
            logging.error(f"Database error during registration: {e}")
            self.request.sendall(b"ERROR: Database error\n")
        except Exception as e:
            logging.error(f"Unexpected error during registration: {e}")
            self.request.sendall(b"ERROR: Unexpected error\n")

    def lookup_user(self, username):
        try:
            self.cursor.execute("SELECT ip_address, port, turn_info, ngrok_url FROM discovery_users WHERE username = ?",
                                (username,))
            user_info = self.cursor.fetchone()

            if user_info:
                ip, port, turn_info, ngrok_url = user_info  # Unpack all four fields
                logging.debug(
                    f"Lookup successful for {username}: {ip}:{port}, TURN info: {turn_info}, Ngrok URL: {ngrok_url}")

                # Now we need to extract TURN server, username, password from turn_info
                turn_parts = turn_info.split(" ")
                if len(turn_parts) < 3:
                    logging.error(f"Invalid TURN server credentials: {turn_info}")
                    return None

                turn_server = turn_parts[0].split(":")[1]  # e.g., '18.116.1.76'
                turn_port = turn_parts[0].split(":")[2]  # e.g., '3478'
                turn_username = turn_parts[1]  # e.g., 'public-user'
                turn_password = turn_parts[2]  # e.g., 'public-password'

                logging.debug(
                    f"TURN Server: {turn_server}:{turn_port}, TURN Username: {turn_username}, TURN Password: {turn_password}")

                # Format the response with commas separating the different components
                response = f"{ip}:{port},{turn_server}:{turn_port} {turn_username} {turn_password},{ngrok_url}\n"
                logging.info(f"Response to be sent by discovery server is {response}")
                return response
            else:
                logging.debug(f"Lookup failed for {username}: User not found")
                return None
        except sqlite3.Error as e:
            logging.error(f"Database error during lookup for {username}: {e}")
            return None

    def deregister_user(self, username):
        # Change 'user_registry' to 'users'
        self.cursor.execute("DELETE FROM discovery_users WHERE username = ?", (username,))
        self.db_conn.commit()
        return self.cursor.rowcount > 0

# Set up the database for the discovery server
def init_discovery_database():
    conn = sqlite3.connect("discovery_users.db")
    cursor = conn.cursor()

    # Create table for discovery registration if it doesn't already exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS discovery_users (
        username TEXT PRIMARY KEY,
        ip_address TEXT,
        port INTEGER,
        turn_info TEXT,
        ngrok_url TEXT)""")

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
