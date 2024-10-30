from flask import Flask, render_template, request, session, redirect, url_for, send_from_directory
from flask_socketio import join_room, leave_room, emit, SocketIO
import random
import os
from string import ascii_uppercase
from werkzeug.utils import secure_filename
from PIL import Image
from moviepy.editor import VideoFileClip
import sys
import time

#sys.argv[1] = 5000

app = Flask(__name__)
app.config["SECRET_KEY"] = "slvrealsecretkeylausdcongratuations221"
app.config["UPLOAD_FOLDER"] = "uploads"  # Directory to store uploaded files
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # Max file size: 64MB
socketio = SocketIO(app)

rooms = {}
room_last_activity = {}
colored_text_codes = {'<1111>': '#4465fc', '<201124>': 'rainbow', '<228>': '#de1d1d'}

# Ensure the upload folder exists
if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_unique_code(length):
    while True:
        code = ''.join(random.choice(ascii_uppercase) for _ in range(length))
        if code not in rooms:
            break
    return code

def generate_unique_filename(filename):
    filename, extension = os.path.splitext(filename)
    return secure_filename(filename + '-' + str(random.randint(1, 10000)) + extension)

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

    return render_template("room.html", code=room, messages=rooms[room]["messages"])

@app.route("/upload-file", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return {"error": "No file part"}, 400

    file = request.files['file']
    
    if file.filename == '':
        return {"error": "No selected file"}, 400

    if allowed_file(file.filename):
        filename = generate_unique_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Construct the URL for the uploaded file
        file_url = url_for('uploaded_file', filename=filename, _external=True)

        # Determine file type
        file_type = 'image' if file.content_type.startswith('image/') else 'video'

        compress_image(filepath) if file_type == 'image' else compress_video(filepath)

        return {"fileUrl": file_url, "fileType": file_type}, 200

    return {"error": "Invalid file format"}, 400

@app.route("/uploads/<string:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

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
    if room not in rooms:
        return

    color, username = get_username_color(session.get("name"))
    
    content = {
        "name": username,
        "message": data["message"],  # Send base64 string directly
        "type": data["type"],         # 'text', 'image', or 'video'
        "color": color  # Include the color in the message data
    }
    
    # Emit the message to all clients in the room
    socketio.emit("message", content, room=room)
    
    # Save the message in the room's history
    rooms[room]["messages"].append(content)
    room_last_activity[room] = time.time()  # Update last activity time
    print(f"{session.get('name')} sent: {data['message']}")

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
    
    join_room(room)
    rooms[room]["names"].append(name)
    room_last_activity[room] = time.time()  # Track last activity
    socketio.emit("message", {"name": name, "message": f"{name} has joined the room."}, room=room)

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] == 0:
            room_last_activity[room] = time.time()  # Track time when last user left

@socketio.on("remove_inactive_rooms")
def remove_inactive_rooms():
    current_time = time.time()
    for room, last_activity in list(room_last_activity.items()):
        if room != 'MAIN' and rooms[room]["members"] == 0 and (current_time - last_activity) > 300:
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
