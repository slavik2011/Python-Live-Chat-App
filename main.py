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
    # Check if 'file' is part of the request
    if 'file' not in request.files:
        return {"error": "No file part"}, 400

    file = request.files['file']
    message = request.form.get("message", "")

    # Ensure the filename is not empty
    if file.filename == '':
        return {"error": "No selected file"}, 400

    # Validate the file extension
    if allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)  # Save the file to the specified path

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
            socketio.emit("message", content, room=room)
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

def get_type(msg):
    if msg.startswith('@'):
        return 'text', msg[1:]  # '@' indicates a text message
    elif msg.startswith('#'):
        return 'image', msg[1:]  # '#' indicates an image
    elif msg.startswith('$'):
        return 'video', msg[1:]  # '$' indicates a video
    else:
        return 'unknown', msg  # Handle unexpected message types

@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return

    type, normalized_msg = get_type(data["message"])
    content = {
        "name": session.get("name"),
        "message": normalized_msg,
        "type": type
    }
    
    # Handle file saving if the message is a base64-encoded image or video
    if type in ['image', 'video']:
        # Decode the base64 message
        import base64

        # Extract the data from the message
        header, encoded = normalized_msg.split(',', 1)
        file_data = base64.b64decode(encoded)
        
        # Get the file extension from the header
        extension = header.split(';')[0].split('/')[-1]
        filename = f"{session.get('name')}.{extension}"  # Name the file with the sender's name and extension

        # Save the file
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(filepath, 'wb') as f:
            f.write(file_data)

        # Construct the URL for the uploaded file
        file_url = url_for('uploaded_file', filename=filename, _external=True)

        content['message'] = file_url  # Use the URL in the message

    socketio.emit("message", content, room=room)
    rooms[room]["messages"].append(content)
    print(f"{session.get('name')} sent: {data['message']}")

    
@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return

    # Handle text and binary messages separately
    if data['type'] == 'text':
        content = {
            "name": session.get("name"),
            "message": data["message"],
            "type": 'text'
        }
    elif data['type'] in ['image', 'video']:
        # Save the binary file if it's an image or video
        file_data = data["message"]  # This will be a binary data string
        filename = data['filename']  # Get the filename
        
        # Save the file to the uploads folder
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Convert the binary data to a file
        with open(filepath, "wb") as f:
            f.write(file_data)  # Write binary data to file

        # Construct the URL for the uploaded file
        file_url = url_for('uploaded_file', filename=filename, _external=True)

        content = {
            "name": session.get("name"),
            "message": file_url,
            "type": data['type']
        }

    socketio.emit("message", content, room=room)
    rooms[room]["messages"].append(content)
    print(f"{session.get('name')} sent: {data['message']}")


if __name__ == "__main__":
    socketio.run(app, debug=True, host='0.0.0.0', port=int(sys.argv[1]))
