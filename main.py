from flask import Flask, render_template, request, session, redirect, url_for, send_from_directory, send_file, jsonify
from flask_socketio import join_room, leave_room, emit, SocketIO
import random
import os
from string import ascii_uppercase
from werkzeug.utils import secure_filename
import mimetypes  # Crucial for detecting file types (3)
import time
import base64
import uuid
import json
import sys
import datetime

app = Flask(__name__)
app.config["SECRET_KEY"] = f"secretencryptionkey-"  # Replace with a strong secret key
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # Max file size: 64MB
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

socketio = SocketIO(app)

rooms = {}
room_last_activity = {}
colored_text_codes = {
    "<1111>": "#4465fc",
    "<201124>": "rainbow",
    "<228>": "#de1d1d",
    "<security333>": "#e455e2",
}

# Ensure the upload folder exists
if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "mp4", "mov", "wav", "mp3"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_unique_code(length):
    while True:
        code = "".join(random.choice(ascii_uppercase) for _ in range(length))
        if code not in rooms:
            break
    return code


def generate_unique_filename(filename):
    filename, extension = os.path.splitext(filename)
    return secure_filename(filename + "-" + str(random.randint(1, 10000)) + extension)


def get_username_color(username):
    for element, color in colored_text_codes.items():
        if username.startswith(element):
            return color, username[len(element):]
    return "#000000", username

@app.route("/", methods=["POST", "GET"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:
            return render_template("home.html", error="Please enter a name.", code=code, name=name)

        if join != False and not code:
            return render_template("home.html", error="Please enter a room code.", code=code, name=name)

        room = code
        if create != False:
            room = generate_unique_code(6)
            rooms[room] = {"members": 0, "names": [], "messages": []}
            room_last_activity[room] = time.time()  # Track creation time for activity
        elif code not in rooms:
            return render_template("home.html", error="Room does not exist.", code=code, name=name)

        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))

    return render_template("home.html")

# Creating main room
room = 'MAIN'
rooms[room] = {"members": 0, "messages": [], "names": []}


@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))

    return render_template("room.html", code=room, messages=rooms.get(room, []))

@app.route('/upload-file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        print(f"Saving file to {file_path}")  # Debugging statement
        file.save(file_path)

        file_type = 'audio' if filename.endswith('.wav') or filename.endswith('.mp3') else 'image'
        file_url = f"/uploads/{filename}"

        return jsonify({'fileUrl': file_url, 'fileType': file_type})

    return jsonify({"error": "Invalid file type"}), 400

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def compress_image(filepath):
    """ Compress image to save space. """
    try:
        img = Image.open(filepath)
        img.save(filepath, optimize=True, quality=20)  # Compress with quality 40%
    except Exception as e:
        print(f"Error compressing image: {e}")

def compress_video(filepath):
    """ Compress video to save space. """
    try:
        clip = VideoFileClip(filepath)
        compressed_path = filepath.rsplit('.', 1)[0] + "_compressed.mp4"
        clip.write_videofile(compressed_path, bitrate="40k")  # Reduce video bitrate
        os.replace(compressed_path, filepath)  # Replace original with compressed version
    except Exception as e:
        print(f"Error compressing video: {e}")

def get_username_color(username):
    print(username)
    for element in colored_text_codes.keys():
        if username.startswith(element):
            return colored_text_codes[element], username[len(element):]
    return '#000000', username

@socketio.on("message")
def message(data):
    room = session.get("room")
    if room is None:
        return

    if room not in rooms:
        return

    color, username = get_username_color(session.get("name"))
    content = {
        "name": username,
        "message": data.get("message", ""),
        "type": data.get("type", "text"),
        "color": color,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Check if the message is of type 'audio'
    if content["type"] == "audio":
        # The message should contain the audio file URL
        content["message"] = data.get("message")  # This should be the URL sent from the client

    # Other security checks...
    if "<" in content["message"] and ">" in content["message"]:
        content["message"] = "Warning: Attempted code execution!"
        content["name"] = "Security"
        content['color'] = '#e455e2'

    rooms[room]["messages"].append(content)

    # Emit the message to all users in the room
    socketio.emit("message", content, room=room)


@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    rooms[room]["members"] += 1
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return
    if not rooms[room]["members"] == 1 and name in rooms[room]["names"] :
        rooms[room]["members"] -= 1
        leave_room(room)
        return

    h_room = str(random.randint(1, 10000000))

    join_room(h_room)

    for msg in rooms[room]['messages']:
        socketio.emit("message", msg, room=h_room)

    time.sleep(1)
    
    join_room(room)
    rooms[room]["names"].append(name)
    room_last_activity[room] = time.time()  # Track last activity
    color, username = get_username_color(name)
    if room != 'MAIN':
        system_messages = ['⚠️ WARNING ⚠️', 'You created a private room. This room will be deleted in 1 hour of unactivity.', '⚠️ WARNING ⚠️']
        for ms in system_messages:
            content = {
                "name": 'System',
                "message": ms,
                "type": 'text',
                "color": '#e455e2',
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
    
            rooms[room]["messages"].append(content)
        
            socketio.emit("message", content, room=room)

    content = {
        "name": 'System',
        "message": f"{username} has joined the room.",
        "type": 'text',
        "color": '#e455e2',
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    rooms[room]["messages"].append(content)
    
    socketio.emit("message", content, room=room)

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    color, username = get_username_color(session.get("name"))
    content = {
        "name": 'System',
        "message": f"{username} has left the room.",
        "type": 'text',
        "color": '#e455e2',
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    rooms[room]["messages"].append(content)
    
    socketio.emit("message", content, room=room)
    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] == 0:
            room_last_activity[room] = time.time()  # Track time when last user left

@socketio.on("remove_inactive_rooms")
def remove_inactive_rooms():
    current_time = time.time()
    for room, last_activity in list(room_last_activity.items()):
        if room != 'MAIN' and rooms[room]["members"] == 0 and (current_time - last_activity) > 3600:
            # Delete all media files in the room's upload folder
            room_folder = os.path.join(app.config["UPLOAD_FOLDER"], room)
            if os.path.exists(room_folder):
                for filename in os.listdir(room_folder):
                    os.remove(os.path.join(room_folder, filename))
            del rooms[room]
            del room_last_activity[room]
            print(f"Room {room} has been removed due to inactivity.")

@socketio.on("start_room_cleanup_task")
def start_room_cleanup_task():
    while True:
        remove_inactive_rooms()
        socketio.sleep(300)

if __name__ == "__main__":
    socketio.start_background_task(start_room_cleanup_task)
    socketio.run(app, debug=True, host='0.0.0.0', port=int(sys.argv[1]))
