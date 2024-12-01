from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
from communication_interface import CommunicationInterface
import logging
from custom_logging.logging_config import setup_logger
import os
from dotenv import load_dotenv
from pathlib import Path

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app)

# Load environment variables
dotenv_path = Path('../configurations/.env')
load_dotenv(dotenv_path=dotenv_path)

# Setup logger
setup_logger()

logger = logging.getLogger(__name__)

# Persistent message storage
chat_history = []

communication_interface = CommunicationInterface(
    broker_address=os.getenv("MQTT_BROKER_ADDRESS"),
    port=int(os.getenv("MQTT_BROKER_PORT"))
)

communication_interface.socketio = socketio

def publish_heartbeat():
    while True:
        communication_interface.publish_UI_status("running")
        time.sleep(30)  # Publish heartbeat every 30 seconds

# Start heartbeat thread
threading.Thread(target=publish_heartbeat, daemon=True).start()

# MQTT message handler
def on_mqtt_message(message):
    # Format the message
    formatted_message = {
        "sender": message.get("sender", "robot"),  # Default sender is robot
        "content": message.get("content", ""),
        "time": message.get("time", time.strftime("%H:%M %p | %B %d"))
    }
    # Add to chat history
    chat_history.append(formatted_message)
    logger.info(f"New message: {formatted_message}")
    # Emit the message to connected clients
    socketio.emit('new_message', formatted_message)

# Register the MQTT message handler
communication_interface.message_callback = on_mqtt_message

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/check_in')
def check_in():
    return render_template('check_in.html')

@app.route('/history')
def history():
    return render_template('history.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/start_check_in', methods=['POST'])
def start_check_in():
    # Start the check-in process
    communication_interface.start_check_in()
    return jsonify({'status': 'success', 'message': 'Check-In command sent'})
# Asynchronous response returning true but the message channel closed before response received

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    # Send chat history to the newly connected client
    emit('chat_history', chat_history)

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

if __name__ == '__main__':
    try:
        socketio.run(port=8000, debug=True)
    except KeyboardInterrupt:
        logger.info("Exiting user interface service...")
    finally:
        communication_interface.disconnect()