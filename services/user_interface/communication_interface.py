import json
import sys
import os
import time
import logging

# Add the project root directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
sys.path.insert(0, project_root)
print(f"project_root: {project_root}")

from shared_libraries.mqtt_client_base import MQTTClientBase

class CommunicationInterface(MQTTClientBase):
    def __init__(self, broker_address, port, event_dispatcher):
        # Initialize QObject explicitly (no arguments are required for QObject)
        super().__init__(broker_address, port)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = event_dispatcher

        self.service_status = "setting_up" # The UI is not active until the root page has loaded

        self.inputs = {
            'switch_state': False,
            'error': False,
            'audioActive': False,
            'cameraActive': False,
            'wifiActive': False,
        }
        self.system_status = {}
        self.check_in_status = False

        # Set up the message callbacks
        self.message_callback = None
        self.socketio = None

        # Subscription topics
        self.service_status_requested_topic = "request/service_status"
        self.update_system_status_topic = "publish/system_status"
        self.user_interface_control_cmd_topic = "user_interface_control_cmd"
        self.silence_detected_topic = "speech_recognition/silence_detected"
        self.conversation_history_topic = "conversation/history"
        self.camera_active_topic = "robot/cameraActive"
        self.audio_active_topic = "audio_active"
        self.robot_error_topic = "robot/error"
        self.update_state_topic = "service/user_interface/update_state"

        # Publish topics
        self.user_interface_status_topic = "user_interface_status"
        self.robot_volume_topic = "robot_volume"
        self.robot_colour_topic = "robot_colour"
        self.update_persistent_data = "update_persistent_data"
        self.save_check_in_topic = "save_check_in"

        # Subscriber and publisher topics
        self.check_in_controls_topic = "check_in_controller"

        # Subscribe to topics
        self.subscribe(self.service_status_requested_topic, self._respond_with_service_status)
        self.subscribe(self.update_system_status_topic, self._update_system_status)
        self.subscribe(self.check_in_controls_topic, self._process_check_in_commands)
        self.subscribe(self.user_interface_control_cmd_topic, self._process_control_command)
        self.subscribe(self.silence_detected_topic, self._process_silence_detected)
        self.subscribe(self.conversation_history_topic, self._on_message)
        self.subscribe(self.camera_active_topic, self._process_camera_active)
        self.subscribe(self.audio_active_topic, self._process_audio_active)
        self.subscribe(self.robot_error_topic, self._process_error_message)
        self.subscribe(self.update_state_topic, self._update_service_state)

    def _respond_with_service_status(self, client, userdata, message):
        self.publish_UI_status(self.service_status)

    def _update_system_status(self, client, userdata, message):
        serviceStatus = json.loads(message.payload.decode("utf-8"))
        # self.logger.info(f"Service status dictionary: {serviceStatus}")
        self.socketio.emit('service_status', serviceStatus)
        self.system_status = serviceStatus
        still_loading = False
        self.logger.info(f"Service status: {serviceStatus}")
        for key, value in serviceStatus.items():
            if value != "set_up":
                still_loading = True
        if still_loading == False:
            self.logger.info("Sending loading_complete event")
            self.socketio.emit('loading_complete')

    def _process_check_in_commands(self, client, userdata, message):
        if message.payload.decode() == '1':
            self.logger.info("Starting check-in")
            self.check_in_status = True
        elif message.payload.decode() == '0':
            self.logger.info("Ending check-in")
            self.socketio.emit('check_in_complete')
            self.check_in_status = False

    def _process_control_command(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            message = payload.get("cmd", "")
            self.logger.info(f"User Interface received the command = {message}")
            self.start_command = message
            if message == "set_up":
                # Check to see if the screen is turned on
                logging.info("UI publishing ready")
                self.publish_UI_status("ready")
            elif message == "start":
                logging.info("UI publishing that it is running")
                self.publish_UI_status("running")
            elif message == "end":
                # put the screen in stand-by or go to home page
                # self.robot_control.disengage_user()
                self.publish_UI_status("completed")
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON payload. Using default retry parameters.")

    def _process_silence_detected(self, client, userdata, message):
        duration = message.payload.decode()
        self.logger.info(f"Silence detected: {duration}")
        self.socketio.emit('silence_detected', {'duration': duration})

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            self.logger.info(f"Message received on '{self.conversation_history_topic}, payload: {payload}")
            if self.message_callback:
                self.message_callback(payload)
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON payload: {e}")

    def _process_camera_active(self, client, userdata, message):
        camera_active = message.payload.decode() == '1'
        self.logger.info(f"Camera active: {camera_active}")
        if self.socketio:
            self.logger.info("Emitting cam_status event to clients")
            self.socketio.emit('cam_status', {'active': camera_active})

    def _process_audio_active(self, client, userdata, message):
        audio_active = message.payload.decode() == '1'
        self.logger.info(f"Microphone active: {audio_active}")
        self.inputs['audioActive'] = audio_active
        if self.socketio:
            self.logger.info("Emitting mic_status event to clients")
            self.socketio.emit('mic_status', {'active': audio_active})

    def _process_error_message(self, client, userdata, message):
        error_message = message.payload.decode()

    def _update_service_state(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            state_name = payload.get("state_name", "")
            state = payload.get("state_value", "")
            self.logger.info(f"Received state update for {state_name}: {state}")
            self.dispatcher.dispatch_event("update_service_state", payload)
            self.service_status = "set_up"
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON payload for updating service state. Using default retry parameters.")

    def start_check_in(self):
        if self.check_in_status != True:
            self.logger.info("Sending check-in start command")
            self.publish(self.check_in_controls_topic, "1")
    
    def change_colour(self, selected_colour):
        self.logger.info(f"Sending colour change command: {selected_colour}")
        self.publish(self.robot_colour_topic, selected_colour)
    
    def change_volume(self, volume):
        self.logger.info(f"Sending volume change command: {volume}")
        self.publish(self.robot_volume_topic, volume)

    def publish_UI_status(self, status, message="", details=None):
        payload = {
            "service_name": "user_interface",
            "status": status,
            "message": message,
            "details": details,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.publish(self.user_interface_status_topic, json.dumps(payload))

        self.service_status = status

    def save_check_in(self, check_in_data):
        self.publish(self.save_check_in_topic, json.dumps(check_in_data))
        self.logger.info(f"Check-in data sent to the database service, Payload: {check_in_data}")

    def set_reminder_time(self, hours = 0, minutes = 0, ampm = "AM"):
        self.logger.info(f"Setting reminder time to {hours}:{minutes} {ampm}")
        states = [
            ["reminder_time_hr", hours],
            ["reminder_time_min", minutes],
            ["reminder_time_ampm", ampm]
        ]

        for state in states:
            payload = {
                "service_name": "reminder",
                "state_name": state[0],
                "state_value": state[1]
            }
            self.logger.info(f"Sending reminder time update: {payload}")
            self.publish(self.update_persistent_data, json.dumps(payload))

    def get_system_status(self):
        return self.system_status
