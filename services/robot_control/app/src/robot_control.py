import anki_vector
from anki_vector import audio
from anki_vector.util import degrees
import logging
import os

import threading
import time
import logging
from functools import wraps

TIMEOUT_WARNING = 5  # Seconds to issue a warning
TIMEOUT_RECONNECT = 8  # Seconds to force reconnect
RETRY_DELAY = 3

class VectorRobotController:
    def __init__(self, dispatcher=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.dispatcher = dispatcher
        self._register_event_handlers()

        self.robot_serial = str(os.getenv("SDK_CONFIGURATION"))
        self.robot_enabled = str(os.getenv("ROBOT_ENABLED")) == 'True'
        self.logger.info(f"Robot enabled: {self.robot_enabled}")
        self.connected = False
        self.error = None
        self.max_retries = 10
        self.connect()
        # self.check_connection()

    def reconnect_on_fail(func):
        '''
            Run robot control function. If the function hangs, force a reconnect.
        '''
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            retries = 0

            while retries < self.max_retries:
                thread = None
                result = None
                func_executed = threading.Event()  # Flag to track if `func()` completed
                exception_raised = None

                def issue_warning():
                    self.logger.warning(f"{func.__name__} is taking too long. Please wait or check the robot.")
                
                warning_timer = threading.Timer(TIMEOUT_WARNING, issue_warning)
                warning_timer.start()

                def run_function():
                    nonlocal result, exception_raised
                    try:
                        result = func(self, *args, **kwargs)
                        func_executed.set()  # Mark function as completed
                    except Exception as e:
                        self.logger.error(f"Exception in {func.__name__}: {e}")
                        exception_raised = e

                thread = threading.Thread(target=run_function, daemon=True)
                thread.start()

                # Wait for the function to complete or timeout
                self.logger.info(f"Waiting for {func.__name__} to complete or timeout...")
                thread.join(TIMEOUT_RECONNECT)
                
                if func_executed.is_set():
                    # Function completed successfully
                    self.logger.info("function executed sucessfully")
                    warning_timer.cancel()
                    return result
                else:
                    self.logger.warning(f"{func.__name__} did not complete in time (timeout).")
                    if self.connected:
                        self.connected = False
                        try:
                            self.disconnect_robot()
                        except Exception as e:
                            self.logger.debug(f"Attempted to disconnect but recived an error: {e}")
                            retries += 1
                            continue # If there is an error during disconnect assume the robot is not connected
                    
                    self.logger.warning(f"{func.__name__} took too long. Forcing a reconnect...")
                
                    try:
                        self.logger.warning(f"{func.__name__} is being directly invoked to avoid recursion.")
                        self._direct_connect()  # Direct method for `connect` logic
                        if func.__name__ == "connect":
                            return True  # Return after successful direct invocation
                    except Exception as e:
                        self.logger.error(f"Direct connect() invocation failed: {e}")
                        retries += 1
                        time.sleep(RETRY_DELAY)
                        continue  # Retry the decorator logic
            
            self.dispatcher.dispatch_event("send_service_error", f"Failed after {self.max_retries} retries.")
            # Exhausted retries
            self.logger.error(f"Failed to execute {func.__name__} after {self.max_retries} retries.")
            return False

        return wrapper
    
    def run_if_robot_is_enabled(func):
        def wrapper(self, *args, **kwargs):
            if self.robot_enabled:
                return func(self, *args, **kwargs)
            return None  # Or raise another custom exception if necessary
        return wrapper
    
    @run_if_robot_is_enabled
    @reconnect_on_fail
    def connect(self):
        """Wrapper for connection logic."""
        self._direct_connect()
        self.max_retries = 1

    def _direct_connect(self):
        """Direct connection logic without decorator."""
        self.robot = anki_vector.Robot(self.robot_serial)
        self.robot.connect()
        self.connected = True
        self.logger.info("Connected successfully!")

    @run_if_robot_is_enabled
    @reconnect_on_fail
    def check_connection(self):
        self.robot.get_battery_state()
        if not self.connected:
            self.logger.info(f"Failed to connect to the robot after multiple attempts. Ended with error {self.error}")
        self.logger.info("Battery checked and robot is, Connected successfully!")
            
    def disconnect_robot(self):
        """Disconnects from the Vector robot."""
        if self.robot:
            self.robot.disconnect()
    
    def _register_event_handlers(self):
        """Register event handlers for robot actions."""
        if self.dispatcher:
            self.dispatcher.register_event("control_command", self.handle_control_command)
            self.dispatcher.register_event("volume_command", self.set_volume)
            self.dispatcher.register_event("tts_command", self.handle_tts_command)
            self.dispatcher.register_event("eye_colour_command", self.handle_eye_colour_command)
            self.dispatcher.register_event("update_service_state", self.update_service_state)

    def handle_control_command(self, command):
        '''
        handels the control commands received from the state machine.

        Args:
            command (str): The control command to handle.
        '''
        self.logger.info(f"Handling control command: {command}")
        status = "complete"
        try:
            if command == "set_up":
                # self.drive_off_charger()
                pass
            elif command == "start":
                # self.handle_tts_command("Starting check-in")
                pass
            elif command == "end":
                # self.disengage_user()
                pass
            elif command == "drive off charger":
                self.logger.debug("Processing drive off charger request")
                self.drive_off_charger()
                self.logger.info("Drive off charger request has been fulfilled..")
            elif command == "return_home":
                self.logger.debug("Processing return home request")
                self.drive_on_charger()
        except Exception as e:
            self.logger.error(f"Error processing control command: {e}")
            payload = {
                "error": f"Error processing control command: {e}",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "service_name": "robot_control"
            }
            self.dispatcher.dispatch_event("send_service_error", payload)
            status = "failed"
            return RuntimeError(f"Failed to execute control command")
        
        # Send acknowledgement to the state machine that the command has been processed
        response = {
                    "behaviour_name": command,
                    "status": status, # "complete" or "failed"
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
        self.dispatcher.dispatch_event("behaviour_completion_status", response)
    
    @run_if_robot_is_enabled
    @reconnect_on_fail
    def drive_off_charger(self):
        self.robot.behavior.drive_off_charger()
        return True

    @run_if_robot_is_enabled
    @reconnect_on_fail
    def drive_on_charger(self):
        self.robot.behavior.drive_on_charger()
        return True

    @run_if_robot_is_enabled
    @reconnect_on_fail
    def find_face(self):
        # Ask user where are they
        self.robot.behavior.say_text("where are you")
        self.robot.behavior.find_faces()
        # Let the user know you see them
        # self.robot.behavior.turn_towards_face()
        return True

    @run_if_robot_is_enabled
    @reconnect_on_fail
    def enable_free_play(self, enable=True):
        if enable:
            self.robot.conn.release_control()
        else:
            self.robot.conn.request_control()
        return True

    @run_if_robot_is_enabled
    @reconnect_on_fail
    def disengage_user(self):
        self.robot.behavior.drive_on_charger()
        return True

    
    def handle_tts_command(self, payload):
        status = "complete"
        try: 
            self.logger.info(f"In handel tts command func, text from {payload['sender']} is: {payload['content']}")
            self.tts(payload["content"])
            # Add delay to allow the robot to finish speaking before sending completion status
            delay = len(payload["content"].split()) / 3 # Assuming robot can speak 3 words per second
            self.logger.info(f"Delaying for {delay} seconds")
            time.sleep(delay)
        except Exception as e:
            self.logger.error(f"Error processing TTS command {e}")
            payload = {
                "error": f"Error processing TTS command: {e}",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "service_name": "robot_control"
            }
            self.dispatcher.dispatch_event("send_service_error", payload)
            status = "failed"
            return RuntimeError(f"Failed to execute TTS command after {self.max_retries} retries")
            
        
        response = {
                    "behaviour_name": payload["message_type"],
                    "status": status, # "complete" or "failed"
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
        self.dispatcher.dispatch_event("behaviour_completion_status", response)

        return True

    @run_if_robot_is_enabled
    @reconnect_on_fail
    def tts(self, text):
        self.robot.behavior.say_text(text)
        return True


    @run_if_robot_is_enabled
    @reconnect_on_fail
    def list_animations(self):
        """Returns a list of all available animations on the robot."""
        return self.robot.anim.anim_list

    @run_if_robot_is_enabled
    @reconnect_on_fail
    def play_animation(self, animation_name):
        """Plays a specified animation by name."""
        # self.robot.conn.request_control()
        # print(self.robot.conn.requires_behavior_control) # Will print True
        # self.robot.anim.play_animation_trigger('GreetAfterLongTime')
        # self.robot.conn.release_control()
        if animation_name in self.robot.anim.anim_list:
            self.robot.anim.play_animation(animation_name)
        else:
            raise ValueError(f"Animation '{animation_name}' not found.")
        return True

    @run_if_robot_is_enabled
    @reconnect_on_fail
    def toggle_autonomous_behavior(self, enable=True):
        self.robot.behavior.enable_all_reactions(enable)
        return True

    @run_if_robot_is_enabled
    @reconnect_on_fail
    def handle_eye_colour_command(self, colour):
        colours = {
            "orange": (0.05, 0.95),
            "yellow": (0.11, 1.00),
            "lime": (0.21, 1.00),
            "sapphire": (0.57, 1.00),
            "purple": (0.83, 0.76),
            "green": (0.25, 1.00),
            "red": (0.00, 1.00),    
        }

        selected_colour = colours.get(colour, colours["orange"])
        self.logger.info(f"Setting eye colour to {colour}")

        self.robot.behavior.set_head_angle(degrees(45.0))
        self.logger.info("Lifted the robot's lift.")
        self.robot.behavior.set_lift_height(0.0)
        self.logger.info("Eye colour set successfully.")
        self.robot.behavior.set_eye_color(hue=selected_colour[0], saturation=selected_colour[1])
        return True
        

    def update_service_state(self, payload):
        state_name = payload.get("state_name", "")
        state = payload.get("state_value", "")
        self.logger.info(f"Received state update for {state_name}: {state}")
        if state_name == "robot_colour":
            self.handle_eye_colour_command(state)
        elif state_name == "robot_volume":
            self.set_volume(state, silent=True)
        elif state_name == "robot_voice":
            self.logger.info(f"Voice command received: {state}")
        elif state_name == "free_play":
            self.logger.info(f"Free play mode {'enabled' if state == 'enable' else 'disabled'}")
            self.enable_free_play(state=="enable")

    @run_if_robot_is_enabled
    @reconnect_on_fail
    def set_volume(self, volume, silent=False):
        '''
        Set the robot's volume level.

        Args:
            volume (str): The volume level to set. One of "quiet", "medium_low", "default", "medium_high", "loud".
        '''
        RobotVolumeLevel = {
            "quiet": audio.RobotVolumeLevel.LOW,
            "medium_low": audio.RobotVolumeLevel.MEDIUM_LOW,
            "default": audio.RobotVolumeLevel.MEDIUM,
            "medium_high": audio.RobotVolumeLevel.MEDIUM_HIGH,
            "loud": audio.RobotVolumeLevel.HIGH,
        }
        self.robot.audio.set_master_volume(RobotVolumeLevel[volume])

        if not silent:
            self.handle_tts_command(f"Volume has been set to {volume}")

        return True

    @run_if_robot_is_enabled
    @reconnect_on_fail
    def capture_camera_frame(self):
        """Captures a single image frame from the robot's camera."""
        if self.robot.camera.latest_image:
            return self.robot.camera.latest_image.raw_image
        else:
            raise RuntimeError("Camera feed not available.")        

    @run_if_robot_is_enabled
    @reconnect_on_fail
    def drive(self, forward_speed=50, turn_speed=0):
        """
        Drives the robot with specified forward and turning speeds.
        Positive forward_speed moves forward; negative moves backward.
        turn_speed specifies turning velocity (left or right).
        """
        self.robot.motors.set_wheel_motors(forward_speed, forward_speed + turn_speed)

    @run_if_robot_is_enabled
    @reconnect_on_fail
    def start_video_stream(self):
        self.is_streaming = True
        self.robot.camera.init_camera_feed()

    @run_if_robot_is_enabled
    @reconnect_on_fail
    def stop_video_stream(self):
        self.is_streaming = False
        self.robot.camera.close_camera_feed()