import asyncio
import websockets

async def echo(websocket, path):
    try:
        print("Client connected")
        async for message in websocket:
            print(f"Received: {message}")
            await websocket.send(message)
    except websockets.ConnectionClosed as e:
        print(f"Connection closed: {e}")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    print("WebSocket server starting...")
    async with websockets.serve(echo, '0.0.0.0', 52572):
        print("WebSocket server running...")
        await asyncio.Future()  # Keep the server running

asyncio.run(main())