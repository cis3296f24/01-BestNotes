import socket
import logging
import threading
import time
from WhiteboardApplication.Collab_Functionality.discover_server import start_discovery_server

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def is_discovery_server_running(host="127.0.0.1", port=9000):
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except (socket.timeout, ConnectionRefusedError):
        return False

def ensure_discovery_server():
    if not is_discovery_server_running():
        logger.info("Discovery server is not running. Starting it now...")
        threading.Thread(target=start_discovery_server, daemon=True).start()
        time.sleep(1)  # Give the server a moment to start
    else:
        logger.info("Discovery server is already running.")