import asyncio
from queue import Queue
import websockets
import json

class Client:
    def __init__(self, host='localhost', port=12345):
        self.host = host
        self.port = port
        self.uri = f"ws://{self.host}:{self.port}"
        self.running = True
        self.receive_queue = Queue()

    async def connect(self):
        """Connect to the WebSocket server."""
        try:
            async with websockets.connect(self.uri) as websocket:
                await self.listen_for_data(websocket)
        except Exception as e:
            print(f"Error connecting: {e}")

    async def send_data(self, websocket, data):
        """Send data to the WebSocket server."""
        try:
            json_data = json.dumps(data)
            await websocket.send(json_data)
        except Exception as e:
            print(f"Error sending data: {e}")

    async def listen_for_data(self, websocket):
        """Listen for incoming data."""
        while self.running:
            try:
                data = await websocket.recv()
                data = json.loads(data)
                self.receive_queue.put(data)
            except Exception as e:
                print(f"Error receiving data: {e}")
                self.running = False

    def get_received_data(self):
        """Retrieve received data from the queue."""
        while not self.receive_queue.empty():
            yield self.receive_queue.get()

    async def disconnect(self, websocket):
        """Disconnect from the WebSocket server."""
        self.running = False
        await websocket.close()