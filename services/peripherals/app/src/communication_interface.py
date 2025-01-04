import json
import sys
import os
import logging
import time

# Add the project root directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../../"))
sys.path.insert(0, project_root)

from shared_libraries.mqtt_client_base import MQTTClientBase

class CommunicationInterface(MQTTClientBase):
    def __init__(self, broker_address, port, event_dispatcher=None):
        super().__init__(broker_address, port)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.dispatcher = event_dispatcher

        self.service_status = None
        self.start_command = False

        # Subscription topics
        self.service_status_requested_topic = "request/service_status"
        self.control_cmd = "peripherals_control_cmd"

        # Publish topics
        self.peripherals_status_topic = "peripherals_status"
        self.peripherals_hearbeat_topic = "peripherals_heartbeat"
        self.network_status_topic = "network_status"
        self.network_speed_topic = "network_speed"
        self.service_error_topic = "service_error"
        
        # subscribe to topics
        self.subscribe(self.service_status_requested_topic, self._respond_with_service_status)
        self.subscribe(self.control_cmd, self._handle_command)

        self._register_event_handlers()

    def _register_event_handlers(self):
        if self.dispatcher:
            self.dispatcher.register_event("send_network_status", self.publish_network_status)
            self.dispatcher.register_event("send_network_speed", self.publish_network_speed)
            self.dispatcher.register_event("send_service_error", self.publish_service_error)

    def _respond_with_service_status(self, client, userdata, message):
        self.publish_peripherals_status(self.service_status)

    def _handle_command(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            cmd = payload.get("cmd", "")
            logging.info(f"peripherals received the command: {cmd}")
            self.logger.info(f"cmd = {cmd}")
            if cmd == "set_up":
                self.start_command = True

            status = {
                "end": "ended",
                "set_up": "set_up",
                "start": "running",
                "check_network_speed": "running",
                "check_network_status": "running"
            }
            self.publish_peripherals_status(status[cmd])
        except Exception as e:
            logging.error(f"Error handling command: {e}")

    def publish_peripherals_status(self, status, message = "", details = None):
        self.service_status = status
        self.logger.info(f"Peripherals status: {status}")
        payload = {
            "service_name": "peripherals",
            "status": status,
            "message": message,
            "details": details,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.publish(self.peripherals_status_topic, json.dumps(payload))

    def publish_peripherals_heartbeat(self):
        self.publish(self.peripherals_hearbeat_topic, "alive")
    
    def publish_network_status(self, status):
        self.logger.info(f"Network status: {status}")
        message = {
            "status": status,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.publish(self.network_status_topic, json.dumps(message))
        self.publish_peripherals_status("completed")

    def publish_network_speed(self, speed):
        self.logger.info(f"Download = {speed['download']/1000000}Mbps and upload = {speed['upload']/1000000}Mbps")
        self.publish(self.network_speed_topic, json.dumps(speed))
        self.publish_peripherals_status("completed")
    
    def publish_service_error(self, error_message):
        payload = {
            "error_message": f"Error processing control command: {error_message}",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "service_name": "robot_control"
            }
        self.publish("error_message", json.dumps(payload))