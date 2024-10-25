from flask import Flask, render_template, request, session, redirect, url_for, send_from_directory
from flask_socketio import join_room, leave_room, emit, SocketIO
import random
import os
from string import ascii_uppercase
from werkzeug.utils import secure_filename
from PIL import Image
from moviepy.editor import VideoFileClip
import sys

app = Flask(__name__)
app.config["SECRET_KEY"] = "hjhjsdahhds"
app.config["UPLOAD_FOLDER"] = "uploads"  # Directory to store uploaded files
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # Max file size: 16MB
socketio = SocketIO(app)

rooms = {}

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
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            return render_template("home.html", error="Room does not exist.", code=code, name=name)

        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))

    return render_template("home.html")

# Creating main room
room = 'MAIN'
rooms[room] = {"members": 0, "messages": []}

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
    message = request.form.get("message", "")
    
    if file.filename == '':
        return {"error": "No selected file"}, 400

    if allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Construct the URL for the uploaded file
        file_url = url_for('uploaded_file', filename=filename, _external=True)

        # Determine file type
        file_type = 'image' if file.content_type.startswith('image/') else 'video'

        # Emit the message with the file URL
        room = session.get("room")
        if room in rooms:
            content = {
                "name": session.get("name"),
                "message": file_url,
                "type": file_type
            }
            message(content, room)
            #socketio.emit("message", content, room=room)
            rooms[room]["messages"].append(content)

        return {"fileUrl": file_url, "fileType": file_type}, 200

    return {"error": "Invalid file format"}, 400



@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

def compress_image(filepath):
    """ Compress image to save space. """
    try:
        img = Image.open(filepath)
        img.save(filepath, optimize=True, quality=60)  # Compress with quality 60%
    except Exception as e:
        print(f"Error compressing image: {e}")

def compress_video(filepath):
    """ Compress video to save space. """
    try:
        clip = VideoFileClip(filepath)
        compressed_path = filepath.rsplit('.', 1)[0] + "_compressed.mp4"
        clip.write_videofile(compressed_path, bitrate="500k")  # Reduce video bitrate
        os.replace(compressed_path, filepath)  # Replace original with compressed version
    except Exception as e:
        print(f"Error compressing video: {e}")

#@socketio.on("message")
def message(data, room):
    #room = session.get("room")
    if room not in rooms:
        return
    
    content = {
        "name": session.get("name"),
        "message": data["message"],
        "type": 'text'
    }
    socketio.emit("messager", content, room=room)
    rooms[room]["messages"].append(content)
    print(f"{session.get('name')} said: {data['message']}")

@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return
    
    join_room(room)
    socketio.emit("message", {"name": name, "message": f"{name} has joined the room."}, room=room)

if __name__ == "__main__":
    socketio.run(app, debug=True, host='0.0.0.0', port=int(sys.argv[1]))
