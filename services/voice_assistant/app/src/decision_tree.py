from services.voice_assistant.app.src.speech_to_text_recognition import SpeedToText
import datetime
import re
import time
import logging


class DecisionTree:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.sr = SpeedToText()
        self.communication_interface = None

    def set_up(self):
        self.sr.communication_interface = self.communication_interface
        if not self.communication_interface:
            self.logger.debug("Communication interface is not set!")
            return
        self.logger.info("Communication interface is set and ready to use.")
        self.communication_interface.publish_voice_assistant_status("ready")

        # Wait for the start command
        while not self.communication_interface.command == "start":
            time.sleep(1)
        
        self.communication_interface.publish_voice_assistant_status("running")
    
    def check_in(self):
        self.set_up()
        
        # Step 1: Send greeting
        self.communication_interface.publish_robot_speech(
            message_type = "greeting",
            content = "Hello! Welcome to your daily check-in."
        )
        time.sleep(2)

        self.logger.info("Starting the check-in process.")

        # Step 2: Weekday-specific questions
        try:
            self.ask_questions(self.get_current_day_questions)
        except Exception as e:
            self.logger.error(f"Error asking weekday questions: {e}")
        
        # Step 3: Experience sampling questions
        try:
            self.ask_questions(self.experience_sampling_questions)
        except Exception as e:
            self.logger.error(f"Error asking experience questions: {e}")
        
        # Step 4: Summarise the conversation

        # Step 5: Wish participants farewell
        self.communication_interface.publish_robot_speech(
            message_type = "farewell",
            content = "Thank you for checking in. Have a great day!"
        )

        time.sleep(0.2)

        # Step 6: Save the conversation to a database or file
        self.logger.info("Voice assistant service completed successfully.")
        self.communication_interface.publish_voice_assistant_status("completed")
        self.communication_interface.end_check_in()

    # Function to determine the day and adjust the questions accordingly
    def get_current_day_questions(self, question = "", response = ""):
        self.logger.info(f"In get_current_day_questions: question = {question}, response = {response}")
        """
        Determine the initial question based on the current day of the week.

        Returns:
            dict: A dictionary containing the question and expected response format.
        """

        QUESTION_MAP = {
            "Monday": "What specific goals do you have for this week?",
            "Tuesday": "What would you like to reflect on this week?",
            "Wednesday": "What can you improve next week?",
            "Thursday": "What strategies worked well for you?",
            "Friday": "What is your main goal for today?",
            "Saturday": "What have you done to stay on track with your behaviour change goals?",
            "Sunday": "What strategies helped you this week?",
        }

        # Get the current day of the week
        current_day = datetime.datetime.now().strftime('%A')
        self.logger.info(f"Current day: {current_day}")

        if question == "":
            # Assign different initial questions based on the day
            self.logger.info(f"Initial question: {QUESTION_MAP.get(current_day)}")
            question = QUESTION_MAP.get(
                current_day,
                "What specific goals do you have for this week?"
                )
            self.logger.info(f"Initial question: {question}")
        else:
            if question == "What specific goals do you have for this week?": # Monday
                question = "What strategies will you use to achieve these goals?"
            elif question == "What would you like to reflect on this week?": # Tuesday
                question = "What did you learn from your reflections?"
            elif question == "What can you improve next week?": # Wednesday
                question = "What specific actions will you take to improve?"
            elif question == "What strategies worked well for you?": # Thursday
                question = "How can you apply these strategies in the future?"
            elif question == "What is your main goal for today?": # Friday
                question = "What strategies will you use to achieve this goal?"
            elif question == "What have you done to stay on track with your behaviour change goals?": # Saturday
                question = "What will you do differently next week?"
            elif question == "What strategies helped you this week?": # Sunday
                question = "How can you build on these strategies for next week?"
            else:
                self.logger.info(f"No more questions for the week. Returning None.")
                return None
        self.logger.info(f"Returning question: {question}")

        return {"question": question, "expected_format": "open-ended"}

    def experience_sampling_questions(self, question = "", response = ""):
        self.logger.info(f"In experience_sampling_questions: question = {question}, response = {response}")
        if question == "":
            return {"question": "How would you rate your progress on a scale of 1 to 10?", "expected_format": "short"}
        elif question == "How would you rate your progress on a scale of 1 to 10?":
            try:
                if response is None or response == "" or response < 1 or response > 10:
                    # Handle the case where no valid number was found
                    return {"question": "Please provide a valid number between 1 and 10.", "expected_format": "short"}
                elif response < 5:
                    return {"question": "What obstacles kept you from meeting your goals?", "expected_format": "open-ended"}
                elif 5 <= response <= 7:
                    return {"question": "What can you improve next week?", "expected_format": "open-ended"}
                else:
                    return {"question": "Great! What strategies worked well for you?", "expected_format": "open-ended"}
            except ValueError:
                return {"question": "Please provide a valid number between 1 and 10.", "expected_format": "short"}
        # Branching based on responses for obstacles
        elif question == "What obstacles kept you from meeting your goals?":
            if "time" in response.lower():
                return {"question": "Would allocating more time next week help?", "expected_format": "open-ended"}
            elif "motivation" in response.lower():
                return {"question": "What could help you stay motivated?", "expected_format": "open-ended"}
            else:
                return {"question": "What can you change to improve your progress?", "expected_format": "open-ended"}
        elif question == "What can you improve next week?":
            return {"question": "What specific actions will you take to improve?", "expected_format": "open-ended"}
        elif question == "Great! What strategies worked well for you?":
            return {"question": "How can you apply these strategies in the future?", "expected_format": "open-ended"}
        else:
            self.logger.info(f"No more questions for experience sampling. Returning None.")
            return None
    
    def ask_questions(self, next_question):
        question_data = next_question()
        while question_data:
            self.communication_interface.publish_robot_speech(
                message_type = "question",
                content = question_data["question"]
            )
            time.sleep(2)

            response = self._get_response(question_data["expected_format"])

            # If the response is invalid, ask the same question again
            if response == "" or response is None:
                continue

            self.communication_interface.publish_user_response(
                message_type = "Response",
                content = response
            )

            # Determine the next question based on the current response
            question_data = next_question(
                question = question_data["question"],
                response  = response
            )
    
    def _get_response(self, expected_format):
        response = self.sr.recognise_response(expected_format)
        if not isinstance(response, str) or not response.strip():
            self.logger.debug(f"Invalid response: {response}. Expected a non-empty string.")
            return ""
        if expected_format == "short":
            # Check if the response is a valid number
            try:
                response = self._extract_number_from(response)
            except ValueError:
                self.logger.debug(f"Invalid response: {response}. Expected a number.")
                return ""
        return response

    def _extract_number_from(self, response):
        if not isinstance(response, str):
            self.logger.debug(f"Invalid response type: {type(response)}. Expected string.")
            return None
        # Use regex to find the first occurrence of a number (integer)
        match = re.search(r'\d+', response)
        if match:
            return int(match.group())
        else:
            return None

    # def save_response(question, response, summary=""):
        # Save the response to a database or file
