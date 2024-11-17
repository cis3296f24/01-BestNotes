from flask import Flask, request
from flask_socketio import SocketIO, join_room, leave_room, emit

app = Flask(__name__)
socketio = SocketIO(app)

sessions = {}

@socketio.on('join')
def on_join(data):
    session_id = data['session_id']
    username = data['username']
    join_room(session_id)
    emit('user_joined', {'username': username}, room=session_id)

@socketio.on('update')
def on_update(data):
    session_id = data['session_id']
    update = data['update']
    emit('board_update', update, room=session_id)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001)