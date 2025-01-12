import time
import threading
from src.device_monitors import NetworkMonitor, ScreenMonitor
from src.communication_interface import CommunicationInterface

import logging

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../../"))
sys.path.insert(0, project_root)

from shared_libraries.logging_config import setup_logger
from shared_libraries.event_dispatcher import EventDispatcher

def publish_heartbeat():
    network_connection_timer = time.time()
    network_speed_timer = time.time()
    
    while True:
        current_time = time.time()

        if current_time - network_connection_timer > 5:
            logger.info("Checking network connection")
            if network_monitor:
                network_monitor.check_internet_connection()
            network_connection_timer = current_time
        if current_time - network_speed_timer > 60:
            logger.info("Checking network speed")
            if network_monitor:
                network_monitor.check_internet_speed()
            network_speed_timer = current_time
        
        screen_monitor.check_for_screen_timeout()

        time.sleep(0.1)

if __name__ == "__main__":
    try:
        while True:
            try:
                setup_logger()

                logger = logging.getLogger("Main")

                dispatcher = EventDispatcher()
                
                network_monitor = NetworkMonitor(
                    event_dispatcher=dispatcher
                )

                screen_monitor = ScreenMonitor(
                    event_dispatcher=dispatcher
                )

                communication_interface = CommunicationInterface(
                        broker_address=str(os.getenv("MQTT_BROKER_ADDRESS")),
                        port=int(os.getenv("MQTT_BROKER_PORT")),
                        event_dispatcher=dispatcher
                    )
                
                communication_interface.publish_peripherals_status("Awake")

                # wait to recive set up command... before running this...
                logger.info("Waiting for set up command")
                while not communication_interface.start_command:
                    logger.info("Set up command not recived")
                    time.sleep(1)

                # Check network connection and speed before starting the heartbeat thread
                network_monitor.check_internet_connection()
                network_monitor.check_internet_speed()

                # Start heartbeat thread
                heart_beat_thread = threading.Thread(target=publish_heartbeat, daemon=True)
                heart_beat_thread.start()

                while True:
                    time.sleep(0.4)

            except Exception as e:
                logger.error(f"Peripherals service threw the following Error: {e}")
                time.sleep(5)

    except KeyboardInterrupt as e:
        heart_beat_thread.join()