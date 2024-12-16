from .leaf_nodes import UserInterface, Reminder, VoiceAssistant, RobotController, Configurations
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

class BehaviourTree:
    def __init__(self, finite_state_machine_event_queue, behaviour_tree_event_queue):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.first_run = True
        self.all_services_running = False

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
        self.reminder_branch = BehaviourBranch(self.behaviours[0], self.communication_interface)
        self.reminder_branch.add_service(UserInterface)
        self.reminder_branch.add_service(Reminder)
        self.add_branch(self.behaviours[0], self.reminder_branch)

        # Check-in
        check_in_scenario = CheckInScenario(self.communication_interface)
        self.check_in_dialog_branch = BehaviourBranch(self.behaviours[1], self.communication_interface, orchestrator = check_in_scenario)
        self.check_in_dialog_branch.add_service(UserInterface)
        self.check_in_dialog_branch.add_service(VoiceAssistant)
        self.check_in_dialog_branch.add_service(RobotController, priority="optional")
        self.add_branch(self.behaviours[1], self.check_in_dialog_branch)

        # Configuration
        self.configurations_branch = BehaviourBranch(self.behaviours[2], self.communication_interface)
        self.configurations_branch.add_service(UserInterface)
        self.configurations_branch.add_service(Configurations)
        self.add_branch(self.behaviours[2], self.configurations_branch)

    def _set_current_state(self, state):
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
            if self.current_branch:
                self.current_branch.deactivate_behaviour()  # Stop all behaviours in the current branch
            self.current_branch = self.branches[branch_name]
            if branch_name == self.behaviours[0]:
                self.communication_interface.set_behaviour_running_status(self.behaviours[0], True)
            self.current_branch.activate_behaviour()  # Start all behaviours in the new branch
            self.logger.info(f"Transitioned to {self.current_branch.branch_name} branch")
            self.behaviour_tree_event_queue.put({"state": branch_name})
            time.sleep(0.4) # Give the system time to process the request

    def update(self):
        """Update the behaviour tree"""
        # Step 1: Check if all services are running
        self.check_if_all_services_are_running()

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
        self.current_branch.update()

    def check_finite_state_machine_event_queue(self):
        if self.finite_state_machine_event_queue.empty() is False:
            self.logger.info("Checking FSM event queue...")
            state = self.finite_state_machine_event_queue.get()["state"]
            
            # Set current state if it's different from the existing one
            if self.current_state in ['Sleep', 'Active'] or state in ['Sleep', 'Active']:
                    # If the fsm transitions from sleep to active or vice versa, the branch won't change so don't transition
                    self._set_current_state(state)
            elif self.current_state != state:
                self._set_current_state(state)
                
                # Transition based on the FSM state
                if state == 'Sleep':
                    self.transition_to_branch(self.behaviours[0])  # Reminder branch
                elif state == 'Active':
                    self.transition_to_branch(self.behaviours[0])  # Reminder branch
                elif state == 'Error':
                    pass
                    # Handle error state if required
    
    def check_if_all_services_are_running(self):
        while self.first_run:
            self.all_services_running = True
            services = self.communication_interface.get_system_status()
            self.communication_interface.request_service_status() # Request all services to provide their status
            self.communication_interface.publish_system_status() # Publish the system status so services know the system health and can respond accordingly

            time.sleep(0.4)

            for service in services:
                if services[service] != "Awake":
                    self.all_services_running = False
            
            if self.all_services_running:
                self.logger.info("All services are running")
                self.communication_interface.publish_system_status() # Publish the system status so services know the system health and can respond accordingly
                self.first_run = False

    def check_for_user_requested_events(self):
        ''' Check if the user has requested a behaviour '''
        behaviourRunning = self.communication_interface.get_behaviour_running_status()

        # Transition to appropriate branch if it is not already in that branch
        if behaviourRunning['check_in'] and self.current_branch.branch_name != self.behaviours[1]:
            self.logger.info(f"Check-in event received event['check_in'] = {behaviourRunning['check_in']} and self.current_branch.branch_name = {self.current_branch.branch_name}")
            self.transition_to_branch(self.behaviours[1])
            self._set_current_state('interacting')
            self.logger.info("Fulfilled user request and transitioning to check-in branch")
        elif behaviourRunning['configurations'] and self.current_branch.branch_name != self.behaviours[2]:
            self.logger.info("Configurations event received")
            self.transition_to_branch(self.behaviours[2])
            self._set_current_state('configuring')
            self.logger.info("Fulfilled user request and transitioning to configurations branch")

    def manage_behaviour(self):
        """Activate or deactivate a specific behaviour in the current branch"""
        behaviourIsRunning = self.communication_interface.get_behaviour_running_status()[self.current_branch.branch_name] # Check if behaviour branch is running

        if behaviourIsRunning and self.current_branch.behaviour_running == False: # Activate the current branch if it's not running
            self.logger.info(f"Current branch is: {self.current_branch.branch_name} and the behaviour is not running")
            self.current_branch.activate_behaviour() # Activate the current branch if it's not running and not complete
        elif behaviourIsRunning == False and self.current_branch.behaviour_running: # Deactivate the current branch if it's running and complete
            self.logger.info(f"Current branch is: {self.current_branch.branch_name} and the behaviour is complete")
            self.transition_to_branch(self.behaviours[0])
            self._set_current_state('active')