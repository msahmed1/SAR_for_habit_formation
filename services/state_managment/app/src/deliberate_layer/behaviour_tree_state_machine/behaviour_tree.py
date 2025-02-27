from .leaf_nodes import UserInterface, Reminder, VoiceAssistant, RobotController, Databse
from .behaviour_branch import BehaviourBranch
from .bt_communication_interface import CommunicationInterface
import os
import logging
import time
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../"))
sys.path.insert(0, project_root)

from orchestrations.check_in_scenario import CheckInScenario
from orchestrations.reminder_scenario import ReminderScenario

class BehaviourTree:
    def __init__(self, finite_state_machine_event_queue, behaviour_tree_event_queue):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.communication_interface = CommunicationInterface(
            broker_address = str(os.getenv('MQTT_BROKER_ADDRESS')),
            port = int(os.getenv('MQTT_BROKER_PORT'))
        )

        self.finite_state_machine_event_queue = finite_state_machine_event_queue
        self.behaviour_tree_event_queue = behaviour_tree_event_queue

        self.current_branch = None
        self.current_state = None
        self.branches = {}

        # Service names to control
        self.behaviours =["reminder","check_in", "configuring"]

        # Dictionary to track acknowledgment status
        self.behaviour_branch_status = {behaviour: False for behaviour in self.behaviours}

        # Reminder
        reminder_scenario = ReminderScenario(self.communication_interface)
        self.reminder_branch = BehaviourBranch(self.behaviours[0], self.communication_interface, orchestrator = reminder_scenario)
        self.reminder_branch.add_service(UserInterface)
        self.reminder_branch.add_service(Reminder)
        self.reminder_branch.add_service(Databse)
        self.reminder_branch.add_service(RobotController, priority="optional")
        self.add_branch(self.behaviours[0], self.reminder_branch)

        # Check-in
        check_in_scenario = CheckInScenario(self.communication_interface)
        self.check_in_dialog_branch = BehaviourBranch(self.behaviours[1], self.communication_interface, orchestrator = check_in_scenario)
        self.check_in_dialog_branch.add_service(UserInterface)
        self.check_in_dialog_branch.add_service(VoiceAssistant)
        self.check_in_dialog_branch.add_service(Databse)
        self.check_in_dialog_branch.add_service(RobotController, priority="optional")
        self.add_branch(self.behaviours[1], self.check_in_dialog_branch)

        # Configuration
        self.configurations_branch = BehaviourBranch(self.behaviours[2], self.communication_interface)
        self.configurations_branch.add_service(UserInterface)
        self.configurations_branch.add_service(RobotController, priority="optional")
        self.configurations_branch.add_service(Databse)
        self.add_branch(self.behaviours[2], self.configurations_branch)

        # Step 1: Check if all services are running
        self.check_if_all_services_are_running()

    def _set_current_state(self, state):
        # self.logger.info(f"treansitioning current state from {self.current_state} to {state}")
        self.current_state = state

    def get_current_state(self):
        '''
            This funtion is used for testing purposes
        '''
        return self.current_state
    
    def get_current_branch(self):
        '''
            This funtion is used for testing purposes
        '''
        return self.current_branch.branch_name if self.current_branch else None

    def add_branch(self, branch_name, branch):
        self.branches[branch_name] = branch

    def transition_to_branch(self, branch_name):
        """Transition to a specific branch of behaviours based on FSM state"""
        self.logger.info(f"processing request to transition to {branch_name} branch")
        if branch_name in self.branches:
            if self.current_branch: # If current branch exists
                self.current_branch.deactivate_behaviour()  # Stop all behaviours
            self.current_branch = self.branches[branch_name]
            if branch_name == self.behaviours[0]: # If transitioning to reminder branch
                self.communication_interface.set_behaviour_running_status(self.behaviours[0], "standby") # Default current behaviour to standby
            self.current_branch.activate_behaviour() # Start behaviour in the new branch
            self.logger.info(f"Transitioned to {self.current_branch.branch_name} branch")
            self.behaviour_tree_event_queue.put({"state": branch_name})
            time.sleep(0.4) # Give the system time to process the request

    def update(self):
        """Update the behaviour tree"""
        # Step 2: Check the high-level state in the finite state machine
        self.check_finite_state_machine_event_queue()

        # Step 3: Check if the user has requested a behaviour
        self.check_for_user_requested_events()

        # Step 4: If no behaviour is running, transition to the reminder branch
        if self.current_branch == None: # Default to reminder branch
            self.transition_to_branch(self.behaviours[0])

        # Step 4: Start and stop behaviours based on the current branch
        self.manage_behaviour()

        # Step 5: Update all active behaviours in the current branch
        self.current_branch.update(self.current_state) # The current_state is used to handel the error state
    
    def check_finite_state_machine_event_queue(self):
        if self.finite_state_machine_event_queue.empty() is False:
            self.logger.info("Checking FSM event queue...")
            state = self.finite_state_machine_event_queue.get()["state"]
            
            # Set current state if it's different from the existing one
            if self.current_state in ['Sleep', 'Active'] or state in ['Sleep', 'Active']:
                # If the fsm transitions from sleep to active or vice versa, the branch won't change so don't transition
                self._set_current_state(state)
            elif self.current_state == "Error" and state != "Error":
                # Update FSM back to current bramch state
                # self.behaviour_tree_event_queue.put({"state": self.current_branch.branch_name})
                self._set_current_state(state) # Remove this line if the above line is uncommented
                pass
            elif self.current_state != state:
                self._set_current_state(state)
                
                # Transition based on the FSM state
                if state == 'Sleep':
                    self.transition_to_branch(self.behaviours[0])  # Reminder branch
                elif state == 'Active':
                    self.transition_to_branch(self.behaviours[0])  # Reminder branch
    
    def check_if_all_services_are_running(self):
        self.logger.info("Checking if all services are Awake...")
        while True:
            all_services_awake = True

            # Request service status
            self.communication_interface.request_service_status()
            
            time.sleep(1)

            services = self.communication_interface.get_system_status()
            for service, status in services.items():
                if status != "Awake":
                    all_services_awake = False
                    self.logger.warning(f"Service {service} is not Awake. Current status: {status}")
            
            # Notify the user interface about the system status
            self.communication_interface.publish_system_status()

            if all_services_awake:
                self.logger.info("All services are Awake.")
                break  # Exit the loop if all services are Awake

        self.logger.info("Ensuring all services are set_up...")
        timer = 0 # seconds
        while True:
            all_services_set_up = True

            # Publish "update_system_state" to the database
            self.communication_interface.behaviour_controller("database", "update_system_state")
            self.communication_interface.behaviour_controller("peripherals", "set_up")

            time.sleep(1)

            # Check if all services are "set_up"
            while True:
                # Request service status
                self.communication_interface.request_service_status()

                time.sleep(1)

                services = self.communication_interface.get_system_status()
                for service, status in services.items():
                    if status != "set_up":
                        all_services_set_up = False
                        self.logger.warning(f"Service {service} is not set_up. Current status: {status}")
                
                # Notify the user interface about the system status
                self.communication_interface.publish_system_status()
                
                if all_services_set_up:
                    self.logger.info("All services are set_up.")
                    break  # Exit the loop if all services are set_up
                
                timer += 1
                if timer > 3: break
            timer = 0

            if all_services_set_up:
                    self.logger.info("All services are set_up.")
                    break  # Exit the loop if all services are set_up

        self.logger.info("All services are running and ready.")

    def check_for_user_requested_events(self):
        ''' Check if the user has requested a behaviour '''
        behaviourRunning = self.communication_interface.get_behaviour_running_status()

        # Transition to appropriate branch if it is not already in that branch
        if behaviourRunning['check_in'] != "disabled" and self.current_branch.branch_name != self.behaviours[1]:
            self.logger.info(f"Check-in event received event['check_in'] = {behaviourRunning['check_in']} and self.current_branch.branch_name = {self.current_branch.branch_name}")
            self.transition_to_branch(self.behaviours[1])
            self._set_current_state('interacting')
            self.logger.info("Fulfilled user request and transitioning to check-in branch")
        elif behaviourRunning['configuring'] != "disabled" and self.current_branch.branch_name != self.behaviours[2]:
            self.logger.info("Configurations event received")
            self.transition_to_branch(self.behaviours[2])
            self._set_current_state('configuring')
            self.logger.info("Fulfilled user request and transitioning to configurations branch")

    def manage_behaviour(self):
        """Activate or deactivate a specific behaviour in the current branch"""
        behaviourIsRunning = self.communication_interface.get_behaviour_running_status()[self.current_branch.branch_name] # Check if behaviour branch is running

        if behaviourIsRunning != "disabled" and self.current_branch.behaviour_running == "disabled": # Activate the current branch if it's not running
            self.logger.info(f"Current branch is: {self.current_branch.branch_name} and the behaviour is not running")
            self.current_branch.activate_behaviour() # Activate the current branch if it's not running and not complete
        elif behaviourIsRunning == "disabled" and self.current_branch.behaviour_running != "disabled": # Deactivate the current branch if it's running and complete
            self.logger.info(f"Current branch is: {self.current_branch.branch_name} and the behaviour is complete")
            self.transition_to_branch(self.behaviours[0])
            self._set_current_state('active')
