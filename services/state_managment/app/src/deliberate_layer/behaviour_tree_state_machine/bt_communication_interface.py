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
    def __init__(self, broker_address, port):
        super().__init__(broker_address, port)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.subscriptions = {}

        # Behaviour running status used activate/deactivate certain behaviours
        self.behaviourRunningStatus = {
            'reminder': False,
            'check_in': False,
            'configurations': False
        }

        self.systemStatus = {
            "speech_recognition": "",
            "robot_control": "",
            "user_interface": "",
            "reminder": ""
        }

        # Subscription topics
        self.reminder_status_topic = "reminder_status"
        self.reminder_heartbeat_topic = "reminder_heartbeat"
        self.speech_recognition_status_topic = "speech_recognition_status"
        self.speech_recognition_heartbeat_topic = "speech_recognition_heartbeat"
        self.robot_status_topic = "robot_status"
        self.robot_heartbeat_topic = "robot_heartbeat"
        self.user_interface_status_topic = "user_interface_status"
        self.user_interface_heartbeat_topic = "user_interface_heartbeat"
        self.configure_topic = "configure"
        self.service_error_topic = "service_error"

        # Publish topics
        self.request_service_status_topic = "request/service_status"
        self.publish_system_status_topic = "publish/system_status"
        self.robot_speech_topic = "speech_recognition/robot_speech"
        self.service_control_command_topic = lambda service_name : service_name + "_control_cmd"

        # Subscriber and publisher topics
        self.check_in_controls_topic = "check_in_controller"

        # Subscribe to topics with custom handlers
        self.subscribe(self.check_in_controls_topic, self._process_check_in_request)
        self.subscribe(self.speech_recognition_status_topic, self._process_service_status)
        # self.subscribe(self.speech_recognition_heartbeat_topic, self._process_heartbeat)
        self.subscribe(self.robot_status_topic, self._process_service_status)
        # self.subscribe(self.robot_controller_status_topic, self._process_heartbeat)
        self.subscribe(self.user_interface_status_topic, self._process_service_status)
        # self.subscribe(self.user_interface_status_topic, self._process_heartbeat)
        self.subscribe(self.reminder_status_topic, self._process_service_status)
        # self.subscribe(self.reminder_heartbeat_topic, self._process_heartbeat)
        self.subscribe(self.configure_topic, self._process_configurations)
        self.subscribe(self.service_error_topic, self._process_error_message)

    def _process_check_in_request(self, client, userdata, message):
        '''
        Process the check in request from the user interface
        
        Args:
            message (str): A string flag indicating the check in status
                '1' - Start check in
                '0' - End check in
        '''
        self.logger.info("Processing check in")
        if message.payload.decode() == '1':
            self.behaviourRunningStatus['check_in'] = True
            # Transition to check in branch
            self.logger.info("Starting check in")
        else:
            for behaviour in self.behaviourRunningStatus:
                self.behaviourRunningStatus[behaviour] = False
            self.logger.info("Ending check in")

    def _process_service_status(self, client, uesrdata, message):
        '''
        Process the status of the services to update the current of the entier system status
        
        Args:
            message (dict): A dictionary containing the message payload
                message = {
                    "service_name": str,
                    "status": str,
                    "message": str,
                    "details": str,
                    "timestamp": "%Y-%m-%d %H:%M:%S"
                }
        '''
        payload = json.loads(message.payload.decode("utf-8"))
        service = payload.get("service_name", "")
        status = payload.get("status", "")

        self.systemStatus[service] = status

    def _process_configurations(self, client, userdata, message):
        self.logger.info("Processing configurations")
        if message.payload.decode() == '1':
            self.behaviourRunningStatus['configurations'] = True
        else:
            self.behaviourRunningStatus['configurations'] = False

    def _process_error_message(self, client, userdata, message):
        self.logger.imfo("Processing error message")
        self.criticalEvents['error'] = message.payload.decode()

    def request_service_status(self):
        '''
        Request a response from all services to get their status
        '''
        # self.logger.info("Requesting service status")
        self.publish(self.request_service_status_topic, "")

    def publish_system_status(self):
        '''
        Publish the system status to all services
        '''
        # self.logger.info("Publishing system status")
        self.publish(self.publish_system_status_topic, json.dumps(self.systemStatus))
    
    def _handle_robot_speech(self, client, userdata, message):
        # Forwards the robot speech to the conversation history
        self.publish(self.conversation_history_topic, message.payload.decode("utf-8"))

    def publish_robot_speech(self, content, message_type="response"):
        message = {
            "sender": "robot",
            "message_type": message_type,
            "content": content
        }
        json_message = json.dumps(message)
        # This is what the robot should say
        self.publish(self.robot_speech_topic, json_message)

    def behaviour_controller(self, service_name, cmd):
        payload = {
            "service_name": service_name,
            "cmd": cmd,
            "time": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.logger.info(f"Publishing service control command to {self.service_control_command_topic(service_name)} with command: {cmd}")
        self.publish(self.service_control_command_topic(service_name), json.dumps(payload))

    def end_check_in(self):
        logging.info("Ending check-in")
        self.publish(self.check_in_controls_topic, "0")

    def get_system_status(self,):
        '''
        A method to expose the service status or all services
        '''
        return self.systemStatus

    def get_behaviour_running_status(self):
        return self.behaviourRunningStatus
    
    def set_behaviour_running_status(self, behaviour, status):
        self.behaviourRunningStatus[behaviour] = status