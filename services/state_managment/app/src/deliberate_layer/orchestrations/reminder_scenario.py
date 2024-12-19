import time
import logging

class ReminderScenario:
    def __init__(self, communication_interface):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.communication_interface = communication_interface
        self.step = 0
        self.complete = False

    def start(self):
        self.step = 1
        self.complete = False
        self.waiting_for_response = False
        self.logger.info("Reminder scenario started")
        pass
    
    def update(self):
        # self.logger.info(f"Updating orchestrator, currently on step = {self.step}")
        # If we've completed the scenario, do nothing.
        if self.complete:
            return
        
        # Step 1: Set up
        if self.step == 1: 
            if self._drive_off_charger():
                 self.step = 2
        
        # Step 1: Send greeting
        if self.step == 2: 
            if self._remind_user():
                 self.step = 3
        
        # Step 5: Wish participants farewell
        if self.step == 3:
            self._farewell_user()
            self.step = 4
            return
        
        # Step 5: Mark as complete
        elif self.step == 4:
            self.complete = True
            self.logger.info("Check-In Scenario Complete")
            self.step = 0
            # Possibly also send completion signals if needed
            return
        
    # Helper methods for each step
    def _drive_off_charger(self):
        # Get robot to drive off the charger and wait for it to complete...
        if self.waiting_for_response == False:
            self.communication_interface.publish_robot_behaviour_command("drive off charger")
            self.waiting_for_response = True
        
        if self.communication_interface.get_robot_behaviour_completion_status("drive off charger") == "complete":
            self.waiting_for_response = False
            self.logger.info("No longer wating, moving to step 2 to greet user")
            return True
        
        return False
    
    def _remind_user(self):
        if self.waiting_for_response == False:
            self.logger.info("Requesting robot to speak")
            self.communication_interface.publish_robot_speech(
                message_type="greeting",
                content="Hello! Welcome to your daily reminder."
            )
            self.waiting_for_response = True
        
        if self.communication_interface.get_robot_behaviour_completion_status("greeting") == "complete":
            self.logger.info("Greetings complete")
            self.waiting_for_response = False
            return True
        
        return False

    def _farewell_user(self):
        self.logger.info("Sending farewell.")
        self.communication_interface.publish_robot_speech(
            message_type="farewell",
            content="Thank you for checking in. Have a great day!"
        )
        self.communication_interface.set_behaviour_running_status("reminder", "standby")
        self.logger.info("Voice assistant service completed successfully.")
        time.sleep(0.5)

    # def save_response(question, response, summary=""):
        # Save the response to a database or file

    def is_complete(self):
            return self.complete