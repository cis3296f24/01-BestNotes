import socketio
from WhiteboardApplication.board_scene import BoardScene  # Ensure your BoardScene is imported

class Client(BoardScene):
    def __init__(self, room, username, server_url="https://young-retreat-21350-055b4ca73a90.herokuapp.com"):
        from WhiteboardApplication.main import BoardScene
        super().__init__()
        self.sio = socketio.Client()
        self.room = room
        self.username = username
        self.server_url = server_url

        try:
            # Connect to the server
            self.sio.connect(self.server_url)
            self.sio.emit('join_room', {'room': self.room, 'username': self.username})

            # Listen for drawing updates
            @self.sio.on('draw_update')
            def on_draw_update(data):
                self.apply_remote_update(data)

        except Exception as e:
            print(f"Failed to connect to the server: {e}")

    def apply_remote_update(self, data):
        """
        Update the board based on received data.
        This method should be implemented based on your board structure.
        """
        pass

    def mouseReleaseEvent(self, event):
        """
        Override mouseReleaseEvent to send updates.
        """
        super().mouseReleaseEvent(event)
        try:
            self.sio.emit('draw_update', {
                'room': self.room,
                'drawing_data': self.get_current_drawing()
            })
        except Exception as e:
            print(f"Failed to send draw update: {e}")

    def closeEvent(self, event):
        """
        Override closeEvent to ensure proper disconnection.
        """
        try:
            self.sio.emit('leave_room', {'room': self.room, 'username': self.username})
            self.sio.disconnect()
        except Exception as e:
            print(f"Error during disconnect: {e}")
        finally:
            super().closeEvent(event)