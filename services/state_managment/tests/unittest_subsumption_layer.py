# test_reactive_layer.py

import unittest
from unittest.mock import MagicMock
import sys
import os

# Add the project root directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
sys.path.insert(0, project_root)

from services.state_managment.app.reactive_layer.subsumption_layer import ReactiveLayer

from queue import Queue
subsumption_layer_event_queue = Queue()


class TestReactiveLayer(unittest.TestCase):

    def setUp(self):
        # Clear the event queue to avoid interference between tests
        while not subsumption_layer_event_queue.empty():
            subsumption_layer_event_queue.get()

        # Create a mock MQTT client
        self.mock_mqtt_client = MagicMock()
        self.mock_mqtt_client.get_inputs.return_value = {
            'switch_state': None,
            'error': None
        }

        # Instantiate ReactiveLayer with the mock MQTT client
        self.reactive_layer = ReactiveLayer(mqtt_client=self.mock_mqtt_client, event_queue=subsumption_layer_event_queue)

    def test_switch_to_active_state(self):
        # Simulate receiving 'switch_state' set to True
        self.mock_mqtt_client.get_inputs.return_value = {
            'switch_state': True,
            'error': None
        }

        # Call detect_critical_condition and check if FSM transitions to Active
        self.reactive_layer.detect_critical_condition()
        current_state = subsumption_layer_event_queue.get()["state"]
        self.assertEqual(current_state, 'Active')

    def test_switch_to_sleep_state(self):
        # Simulate receiving 'switch_state' set to False
        self.mock_mqtt_client.get_inputs.return_value = {
            'switch_state': False,
            'error': None
        }

        # Call detect_critical_condition and check if FSM transitions to Sleep
        self.reactive_layer.detect_critical_condition()
        current_state = subsumption_layer_event_queue.get()["state"]
        self.assertEqual(current_state, 'Sleep')

    def test_error_state(self):
        # Simulate receiving 'error' set to True
        self.mock_mqtt_client.get_inputs.return_value = {
            'switch_state': None,
            'error': True
        }

        # Call detect_critical_condition and check if FSM transitions to Error
        self.reactive_layer.detect_critical_condition()
        current_state = subsumption_layer_event_queue.get()["state"]
        self.assertEqual(current_state, 'Error')

    def test_default_to_sleep_state(self):
        # Simulate receiving 'switch_state' and 'error' set to None
        self.mock_mqtt_client.get_inputs.return_value = {
            'switch_state': None,
            'error': None
        }

        # Call detect_critical_condition and check if FSM transitions to Sleep
        self.reactive_layer.detect_critical_condition()
        current_state = subsumption_layer_event_queue.get()["state"]
        self.assertEqual(current_state, 'Sleep')

    def test_priority_order(self):
        # Simulate receiving 'error' set to True
        self.mock_mqtt_client.get_inputs.return_value = {
            'switch_state': True,
            'error': True
        }

        # Call detect_critical_condition and check if FSM transitions to Error
        self.reactive_layer.detect_critical_condition()
        current_state = subsumption_layer_event_queue.get()["state"]
        self.assertEqual(current_state, 'Error')

    def test_switching_states(self):
        self.mock_mqtt_client.get_inputs.return_value = {
            'switch_state': False,
            'error': True
        }

        # Call detect_critical_condition and check if FSM transitions to Active
        self.reactive_layer.detect_critical_condition()
        current_state = subsumption_layer_event_queue.get()["state"]
        self.assertEqual(current_state, 'Error')

        self.mock_mqtt_client.get_inputs.return_value = {
            'switch_state': True,
            'error': False
        }

        # Call detect_critical_condition and check if FSM transitions to Active
        self.reactive_layer.detect_critical_condition()
        current_state = subsumption_layer_event_queue.get()["state"]
        self.assertEqual(current_state, 'Active')
        
if __name__ == '__main__':
    unittest.main()
