import json
import time
from PIL import Image
import io
import sys
import os
import logging

# Add the project root directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../../"))
sys.path.insert(0, project_root)

from shared_libraries.mqtt_client_base import MQTTClientBase

class CommunicationInterface(MQTTClientBase):
    def __init__(self, broker_address, port, event_dispatcher):
        super().__init__(broker_address, port)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = event_dispatcher

        self.start_command = ""
        self.is_streaming = False

        self.service_status = "Awake" # As soon as the robot controller starts, it is awake

        # Subscription topics
        self.service_status_requested_topic = "request/service_status"
        self.service_control_cmd = "robot_control_control_cmd"
        self.robot_volume = "robot_volume"
        self.robot_colour = "robot_colour"
        self.recive_robot_tts_topic = "robot_tts"
        self.animation_topic = "robot/animation"
        # self.activate_camera_topic = "robot/activate_camera"
        self.robot_behaviour_topic = "robot_behaviour_command"
        self.update_state_topic = "service/robot_control/update_state"
        self.save_check_in_topic = "save_check_in"

        # Publish topics
        self.conversation_history_topic = "conversation/history"
        self.camera_active_topic = "robot/cameraActive"
        self.video_topic = "robot/video_feed"
        self.robot_service_status_topic = "robot_status"
        self.robot_control_status_topic = "robot_control_status"

        # Subscribe to necessary topics
        self.subscribe(self.service_status_requested_topic, self._respond_with_service_status)
        self.subscribe(self.service_control_cmd, self._handle_control_command)
        self.subscribe(self.robot_volume, self._handle_volume_command)
        self.subscribe(self.robot_colour, self._handle_colour_command)
        self.subscribe(self.recive_robot_tts_topic, self._handle_tts_command)
        self.subscribe(self.animation_topic, self._handle_animation_command)
        self.subscribe(self.robot_behaviour_topic, self._handle_behaviour_request)
        # self.subscribe(self.activate_camera_topic, self._process_camera_active)
        self.subscribe(self.update_state_topic, self._update_service_state)
        self.subscribe(self.save_check_in_topic, self._save_check_in)

        self._register_event_handlers()

    def _register_event_handlers(self):
        """Register event handlers for robot actions."""
        if self.dispatcher:
            self.dispatcher.register_event("behaviour_completion_status", self._update_behaviour_status)
    
    def _respond_with_service_status(self, client, userdata, message):
        self.publish_robot_status(self.service_status)
    
    def _handle_control_command(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            command = payload.get("cmd", "")
            self.dispatcher.dispatch_event("control_command", command)

            status_response = {
                "set_up": "ready",
                "start": "running",
                "end": "completed"
            }

            self.publish_robot_status(status_response.get(command, "running"))
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON payload. Using default retry parameters.")
    
    def _handle_volume_command(self, client, userdata, message):
        try:
            volume = message.payload.decode("utf-8")
            self.logger.info(f"Volume command received: {volume}")
            self.dispatcher.dispatch_event("volume_command", volume)
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON payload for volume command.")
    
    def _handle_colour_command(self, client, userdata, message):
        selected_colour = message.payload.decode()
        try:
            self.logger.info(f"Colour received: {selected_colour}")
            if selected_colour:
                self.dispatcher.dispatch_event("eye_colour_command", selected_colour)
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON payload for colour command.")
    
    def _handle_tts_command(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            sender = payload.get("sender", "")
            if sender == "orchestrator":
                self.dispatcher.dispatch_event("tts_command", payload)
                payload["sender"] = "robot"
                self.publish(self.conversation_history_topic, json.dumps(payload))
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON payload for TTS command.")
            
    def _handle_animation_command(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            animation_name = payload.get("animation", "")
            self.logger.info(f"Animation command received: {animation_name}")
            if animation_name:
                self.dispatcher.dispatch_event("animation_command", animation_name)
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON payload for animation command.")

    def _handle_behaviour_request(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            behaviour_name = payload.get("cmd", "")
            self.logger.info(f"behaviour command received: {behaviour_name}")
            if behaviour_name:
                self.dispatcher.dispatch_event("control_command", behaviour_name)
            self.logger.info("Behaviour control command processed")
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON payload for animation command.")
        
    def _update_behaviour_status(self, message):
        self.publish(self.robot_control_status_topic, json.dumps(message))
    
    def _update_service_state(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            state_name = payload.get("state_name", "")
            state = payload.get("state_value", [])
            self.logger.info(f"Received state update for {state_name}: {state}")
            self.dispatcher.dispatch_event("update_service_state", payload)
            self.service_status = "set_up"
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON payload for updating service state. Using default retry parameters.")

    def _save_check_in(self, client, userdata, message):
        self.dispatcher.dispatch_event("control_command", "return_home")

    # def _process_camera_active(self, client, userdata, message):
    #     camera_active = message.payload.decode() == '1'
    #     self.logger.info(f"Camera active: {camera_active}")
    #     if self.socketio:
    #         self.logger.info("start displaying camera feed")
    #         self.robot_control.start_video_stream()
    #     else:
    #         self.robot_control.stop_video_stream()
    
    # def video_stream(self):
    #     self.logger.info(f"Video stream status = {self.robot_control.is_streaming}")
    #     while True:
    #         if self.robot_control.is_streaming:
    #             try:
    #                 img = self.robot_control.capture_camera_frame()
    #                 img_io = io.BytesIO()
    #                 img.save(img_io, format="JPEG")
    #                 img_data = img_io.getvalue()
    #                 self.publish(self.video_topic, img_data)
    #                 time.sleep(0.2)  # Frame rate of 5 frames per second
    #             except Exception as e:
    #                 self.logger.error(f"Error in video streaming: {e}")
    #                 break
    
    def publish_robot_status(self, status, message="", details=None):
        logging.info(f"Publishing robot status: {status}")
        if status == "ready":
            self.publish(self.camera_active_topic, "1")
        if status == "completed":
            self.publish(self.camera_active_topic, "0")
        
        payload = {
            "service_name": "robot_control",
            "status": status,
            "message": message,
            "details": details,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.publish(self.robot_service_status_topic, json.dumps(payload))

        self.service_status = status