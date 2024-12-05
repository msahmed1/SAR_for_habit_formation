import queue
import time
from dotenv import load_dotenv
from pathlib import Path
import os
from google.cloud import speech

import pyaudio
import audioop

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms
SILENCE_THRESHOLD = 400  # RMS threshold for silence (This value was arbitrarily chosen based on testing)
INITIAL_SILENCE_DURATION = 15 # Silence duration in seconds
SILENCE_DURATION = 4  # Silence duration in seconds

# Relative path to the .env file in the config directory
# Move up one level and into config
dotenv_path = Path('../../../configurations/.env')

# Load the .env file
load_dotenv(dotenv_path=dotenv_path)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

class SpeedToText:
    def __init__(self):
        # Load API keys from environment variables
        self.speech_key = os.getenv('SPEECH_KEY')
        self.service_region = os.getenv('SPEECH_REGION')
        self.communication_interface = None

        self.client = speech.SpeechClient()
    
    def recognise_response(self, response_type):
        while True:
            # Configure recognition settings based on the response type
            config = self.short_response() if response_type == "short" else self.long_response()
            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True,
                single_utterance=False,
            )
            
            transcript = ""
            with MicrophoneStream(RATE, CHUNK, self.communication_interface) as stream:
                audio_generator = stream.generator()
                requests = (
                    speech.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator
                )
                responses = self.client.streaming_recognize(streaming_config, requests)

                # Process the responses
                transcript = self.listen_print_loop(responses)
                print(f"Captured transcript: {transcript}")

            return transcript
    
    def long_response(self):
        return speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=RATE,
            language_code="en-US",
        )


    def short_response(self):
        return speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=RATE,
            language_code="en-US",
            speech_contexts=[speech.SpeechContext(phrases=["yes", "no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"])],
        )
    
    def listen_print_loop(self, responses):
        """Processes server responses and captures transcripts."""
        transcript = ""
        print(f"Entered listen_print_loop and transcript is {transcript}")
        for response in responses:
            if not response.results:
                continue

            result = response.results[0]
            if not result.alternatives:
                continue
            
            # Append interim results to the transcript
            if result.is_final:
                transcript += result.alternatives[0].transcript + " "
                print(f"Final result: {result.alternatives[0].transcript}")
            else:
                print(f"Interim result: {result.alternatives[0].transcript}", end="\r")

        return transcript.strip()

class MicrophoneStream:
    """Opens a recording stream as a generator yielding the audio chunks."""

    def __init__(self, rate=RATE, chunk=CHUNK, communication_interface=None):
        self._rate = rate
        self._chunk = chunk
        self._buff = queue.Queue()
        self.closed = True
        self.communication_interface = communication_interface

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            stream_callback=self._fill_buffer,
        )
        self.closed = False
        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        self._buff.put(in_data)
        return None, pyaudio.paContinue


    def generator(self):
        """Generate audio chunks and detect silence.
        Waits {INITIAL_SILENCE_DURATION} seconds for the user to start speaking.
        Once the user starts talking, if the user is silent for {SILENCE_DURATION}, the conversation will end.
        """
        silence_start = time.time()
        silence_detected = False
        initial_silence = True
        print("Waiting for user to start speaking.")
        self.communication_interface.publish_silance_detected(INITIAL_SILENCE_DURATION)
        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            yield chunk

            # Detect silence by measuring RMS
            rms = audioop.rms(chunk, 2)
            if initial_silence:
                if rms < SILENCE_THRESHOLD:
                    if time.time() - silence_start >= INITIAL_SILENCE_DURATION:
                        print("No response detected within initial silence duration.")
                        self.closed = True
                else:
                    print("User started speaking.")
                    initial_silence = False
                    silence_detected = False
                    silence_start = time.time()  # Reset silence timer for post-speaking silence detection
                    self.communication_interface.publish_silance_detected(0)
            else:
                if rms < SILENCE_THRESHOLD:
                    if not silence_detected: # publish silence detected only once per silent period
                        silence_detected = True
                        self.communication_interface.publish_silance_detected(SILENCE_DURATION)
                    if time.time() - silence_start >= SILENCE_DURATION:
                        print("Silence detected after response. Ending recording.")
                        self.closed = True
                else:
                    silence_start = time.time()  # Reset silence timer when sound is detected
                    self.communication_interface.publish_silance_detected(0)
                    silence_detected = False
                    print("Sound detected.")
