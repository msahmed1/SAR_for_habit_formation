# Behaviour tree leaf nodes
class Task:
    def start(self):
        pass

    def update(self):
        pass

    def end(self):
        pass

# For each behaviour mark the services that are critical to the behaviour to previent transition to another state while behaviour is running

class CheckIn(Task):
    def start(self):
        # Start voice assistant
        # print("Greet participant")
        pass

    def update(self):
        # print("Ask questions and record responses...")
        pass

    def end(self):
        # print("Summarise responses and wish farewell")
        pass

class AutonomousBhaviour(Task):
    def start(self):
        # Face tracking
        # Autonomous roaming
        # print("Starting to autonomously behave")
        pass

    def update(self):
        # print("Behaving autonimously...")
        pass

    def end(self):
        # print("Stopped autonomous behaviour")
        pass

class EmotionGeneration(Task):
    def start(self):
        # Enable the robots emotion generation system in robot behavior
        # print("Starting to generate emotion")
        pass

    def update(self):
        # print("Generating emotion...")
        pass

    def end(self):
        # print("Stopped generating emotion")
        pass

class AdministerSurvey(Task):
    def start(self):
        # Start survey in user interface
        # print("Starting survey")
        pass

    def update(self):
        # print("Surveying...")
        pass

    def end(self):
        # print("Stopped survey")
        pass


class TaskScheduler(Task):
    def start(self):
        # Send message to the task scheduler to start scheduling tasks
        # Send message to user interface to show scheduled tasks
        # print("Starting task scheduler")
        pass

    def update(self):
        # print("Scheduling tasks...")
        pass

    def end(self):
        # print("Stopped task scheduler")
        pass


class Configurations(Task):
    def start(self):
        # Show configuration options in user interface and start robot behaviour configuration
        # print("Show configuration options")
        pass

    def update(self):
        # print("Configuring...")
        pass

    def end(self):
        # print("Exit configuration page")
        pass


class BehaviorBranch:
    """Represents a branch of behaviors accessible during a specific FSM state."""

    def __init__(self, name):
        self.name = name
        self.behaviors = []
        self.all_services_available = False
        self.behaviour_running = False

    def add_behavior(self, behavior):
        self.behaviors.append(behavior)

    def start(self):
        """Start all behaviors in this branch"""
        for behavior in self.behaviors:
            behavior.start()

    def update(self):
        """Update all active behaviors in this branch"""
        # Check MQTT to see if behaviour is complete
        # If it is complete, set the behaviour_completion_status to True and end the behaviour

        # Activate behaviour once all services are available
        if self.all_services_available and self.behaviour_running is False:
            self.activate_behavior()

        for behavior in self.behaviors:
            behavior.update()

    def end(self):
        # if behaviour is complete, set the behaviour_completion_status to True and end the behaviour
        """Stop all behaviors in this branch"""
        for behavior in self.behaviors:
            behavior.end()

    def activate_behavior(self):
        """Activate a specific behavior by name"""
        # If all services are available, start the behavior
        for behavior in self.behaviors:
            behavior.start()
        self.behaviour_running = True

    def deactivate_behavior(self):
        """Deactivate a specific behavior by name"""
        for behavior in self.behaviors:
            behavior.end()
        self.behaviour_running = False


class BehaviorTree:
    def __init__(self, mqtt_client, finite_state_machine_event_queue, behavior_tree_event_queue):
        self.mqtt_client = mqtt_client
        self.current_branch = None
        self.current_state = None
        self.previous_event = None
        self.previousBehaviourCompletionStatus = None

        self.finite_state_machine_event_queue = finite_state_machine_event_queue
        self.behavior_tree_event_queue = behavior_tree_event_queue

        self.branches = {}

        # Service names to control
        self.behaviours =["reminder","check_in", "configurations"]

        # Dictionary to track acknowledgment status
        self.behaviour_branch_status = {behaviour: False for behaviour in self.behaviours}

        # Reminder
        self.reminder_branch = BehaviorBranch(self.behaviours[0])
        self.reminder_branch.add_behavior(TaskScheduler())
        self.add_branch(self.behaviours[0], self.reminder_branch)

        # Check-in
        self.check_in_dialog_branch = BehaviorBranch(self.behaviours[1])
        self.check_in_dialog_branch.add_behavior(CheckIn())
        self.check_in_dialog_branch.add_behavior(AutonomousBhaviour())
        self.check_in_dialog_branch.add_behavior(EmotionGeneration())
        self.check_in_dialog_branch.add_behavior(AdministerSurvey())
        self.add_branch(self.behaviours[1], self.check_in_dialog_branch)

        # Configuration
        self.configurations_branch = BehaviorBranch(self.behaviours[2])
        self.configurations_branch.add_behavior(Configurations())
        self.add_branch(self.behaviours[2], self.configurations_branch)

    def set_current_state(self, state):
        self.current_state = state

    def get_current_state(self):
        return self.current_state
    
    def get_current_branch(self):
        return self.current_branch.name

    def add_branch(self, branch_name, branch):
        self.branches[branch_name] = branch

    def transition_to_branch(self, branch_name):
        """Transition to a specific branch of behaviors based on FSM state"""
        if branch_name in self.branches:
            if self.current_branch:
                self.current_branch.end()  # Stop all behaviors in the current branch
            self.current_branch = self.branches[branch_name]
            self.current_branch.start()  # Start all behaviors in the new branch
            print(f"Transitioned to {self.current_branch.name} branch")

    def update(self):
        self.check_finite_state_machine_event_queue()
        
        self.check_mqtt_messages_for_user_events()

        if self.current_branch == None: # Default to reminder branch
            self.transition_to_branch(self.behaviours[0])
        
        self.manage_behavior()

        """Update all active behaviors in the current branch"""
        self.current_branch.update()
    
    def check_finite_state_machine_event_queue(self):
        if self.finite_state_machine_event_queue.empty() is False:
            print("Checking FSM event queue...")
            state = self.finite_state_machine_event_queue.get()["state"]
            
            # Set current state if it's different from the existing one
            if self.current_state != state:
                self.set_current_state(state)
                
                # Transition based on the FSM state
                if state == 'sleep':
                    self.transition_to_branch(self.behaviours[0])  # Reminder branch
                elif state == 'active':
                    self.transition_to_branch(self.behaviours[0])  # Reminder branch
                elif state == 'error':
                    pass
                    # Handle error state if required
    
    def check_mqtt_messages_for_user_events(self):
        # check mqtt for new messages and update behaviors accordingly
        event = self.mqtt_client.get_user_event()
        
        if event != self.previous_event:
            if event['check_in'] is True:
                print("Check-in event received")
                self.transition_to_branch(self.behaviours[1])
                self.set_current_state('interacting')
            elif event['configurations'] is True:
                print("Configurations event received")
                self.transition_to_branch(self.behaviours[2])
                self.set_current_state('configuring')
            self.previous_event = event

    def manage_behavior(self):
        """Activate or deactivate a specific behavior in the current branch"""
        behaviourIsRunning = self.current_branch.behaviour_running
        behaviourCompletionStatus = self.mqtt_client.get_behaviour_completion_status()
        behaviourIsComplete = behaviourCompletionStatus[self.current_branch.name]
        previousBehaviourIsComplete = self.previousBehaviourCompletionStatus[self.current_branch.name] if self.previousBehaviourCompletionStatus else None

        if behaviourIsRunning == False and behaviourIsComplete == False:
            self.current_branch.activate_behavior()
        elif behaviourIsRunning and behaviourIsComplete and previousBehaviourIsComplete != behaviourIsComplete:
            print(f"Current branch is: {self.current_branch.name} and the behaviour is complete")
            self.current_branch.deactivate_behavior()
            self.transition_to_branch(self.behaviours[0])
            print("Transitioned to reminder branch")
            self.set_current_state('active')
            self.previousBehaviourCompletionStatus = behaviourCompletionStatus
