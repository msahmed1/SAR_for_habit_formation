import paho.mqtt.client as mqtt
from PyQt6.QtCore import pyqtSignal, QObject, QMetaObject, Qt


class MQTTClient(QObject):
    switch_state_signal = pyqtSignal(str)
    wake_word_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    audio_signal = pyqtSignal(bool)
    camera_signal = pyqtSignal(bool)

    def __init__(self, broker_address, port):
        super().__init__()
        self.mqtt_client = mqtt.Client()
        try:
            self.mqtt_client.connect(broker_address, port, keepalive=60)
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.loop_start()
            self.mqtt_client.on_disconnect = self.on_disconnect
        except Exception as e:
            print(f"Error connecting to MQTT broker: {e}")

        self.inputs = {
            'switch_state': None,
            'wake_word': None,
            'error': None,
            'audioActive': None,
            'cameraActive': None,
            'wifiActive': None,
        }
        self.subscribe_to_topics()

    def on_connect(self, client, userdata, flags, rc):
        try:
            if rc == 0:
                print("Connected to broker")
            else:
                print(f"Failed to connect to broker, return code {rc}")
        except Exception as e:
            print(f"Exception in on_connect: {e}")

    def subscribe_to_topics(self):
        self.mqtt_client.subscribe("robot/switch_state")
        self.mqtt_client.message_callback_add(
            "robot/switch_state", self.process_switch_state)

        self.mqtt_client.subscribe("robot/error")
        self.mqtt_client.message_callback_add(
            "robot/error", self.process_error_message)

        self.mqtt_client.subscribe("robot/audioActive")
        self.mqtt_client.message_callback_add(
            "robot/audioActive", self.process_audio_active)

        self.mqtt_client.subscribe("robot/cameraActive")
        self.mqtt_client.message_callback_add(
            "robot/cameraActive", self.process_camera_active)

    # Use QMetaObject.invokeMethod to ensure signal emission in the main thread
    def process_switch_state(self, client, userdata, message):
        switch_state = message.payload.decode()
        QMetaObject.invokeMethod(
            self, "emit_switch_state_signal", Qt.ConnectionType.QueuedConnection, switch_state)

    def process_error_message(self, client, userdata, message):
        error_message = message.payload.decode()
        QMetaObject.invokeMethod(
            self, "emit_error_signal", Qt.ConnectionType.QueuedConnection, error_message)

    def process_audio_active(self, client, userdata, message):
        audio_active = message.payload.decode() == '1'
        self.audio_signal.emit(audio_active)

    def process_camera_active(self, client, userdata, message):
        camera_active = message.payload.decode() == '1'
        self.camera_signal.emit(camera_active)

    # These methods will be called safely from the main thread
    def emit_switch_state_signal(self, switch_state):
        self.switch_state_signal.emit(switch_state)

    def emit_error_signal(self, error_message):
        self.error_signal.emit(error_message)

    def emit_audio_signal(self, audio_active):
        self.audio_signal.emit(audio_active)

    def emit_camera_signal(self, camera_active):
        self.camera_signal.emit(camera_active)

    def get_inputs(self):
        return self.inputs

    def start_check_in(self):
        print("Client connected:", self.mqtt_client.is_connected())
        print("Attempting to send start check-in message")
        result = self.mqtt_client.publish("robot/check_in", "1")
        print(f"Publish result: {result.rc}")  # result.rc == 0 means success

    def disconnect(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()

    def on_disconnect(self, client, userdata, rc):
        print(f"Disconnected with return code {rc}")
        if rc != 0:
            print("Unexpected disconnection. Attempting to reconnect...")
            try:
                client.reconnect()
            except Exception as e:
                print(f"Reconnection failed: {e}")