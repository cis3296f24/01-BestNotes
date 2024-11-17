import asyncio
import websockets
import json

class Server:
    def __init__(self, host='localhost', port=12345):
        self.host = host
        self.port = port
        self.clients = set()
        self.running = True

    async def handle_client(self, websocket, path):
        """Handle an individual client connection."""
        self.clients.add(websocket)
        try:
            async for message in websocket:
                # Broadcast the message to all other clients
                await self.broadcast(message, websocket)
        except Exception as e:
            print(f"Error with client: {e}")
        finally:
            self.clients.remove(websocket)

    async def broadcast(self, message, sender_websocket):
        """Broadcast a message to all connected clients except the sender."""
        for client in self.clients:
            if client != sender_websocket:
                try:
                    await client.send(message)
                except Exception as e:
                    print(f"Error sending to client: {e}")

    async def start(self):
        """Start the WebSocket server."""
        async with websockets.serve(self.handle_client, self.host, self.port):
            await asyncio.Future()  # Run the server until interrupted

    def stop(self):
        """Stop the server."""
        self.running = False