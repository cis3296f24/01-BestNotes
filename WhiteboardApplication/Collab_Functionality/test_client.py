import pytest
import asyncio
import websockets

@pytest.mark.asyncio
async def test_client():
    uri = "ws://localhost:52572"
    try:
        async with websockets.connect(uri) as websocket:
            await websocket.send("Hello, server!")
            response = await websocket.recv()
            print(f"Received from server: {response}")
            assert response == "Hello, server!"
    except websockets.ConnectionClosedError as e:
        print(f"Connection closed unexpectedly: {e}")
        assert False, "Unexpected ConnectionClosedError"
    except Exception as e:
        print(f"Unexpected error: {e}")
        assert False, f"Unexpected error: {e}"