from flask import Flask, request, jsonify

app = Flask(__name__)
sessions = {}

@app.route('/create_session', methods=['POST'])
def create_session():
    data = request.json
    session_id = data.get('session_id')
    host = data.get('host')

    if not session_id or not host:
        return jsonify({"error": "Invalid data"}), 400

    if session_id in sessions:
        return jsonify({"error": "Session ID already exists"}), 400

    sessions[session_id] = {"host": host, "participants": []}
    return jsonify({"message": "Session created"}), 200

@app.route('/join_session', methods=['POST'])
def join_session():
    data = request.json
    session_id = data.get('session_id')
    username = data.get('username')

    if not session_id or not username:
        return jsonify({"error": "Invalid data"}), 400

    session = sessions.get(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    if len(session['participants']) >= 7:
        return jsonify({"error": "Session is full"}), 403

    session['participants'].append(username)
    return jsonify({"message": "Joined session"}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)