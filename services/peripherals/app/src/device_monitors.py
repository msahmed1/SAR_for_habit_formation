import speedtest
import subprocess

class NetworkMonitor:
    def __init__(self, event_dispatcher):
        self.servers = []
        self.threads = None
        self.speed_test = speedtest.Speedtest()
        self.dispatcher = event_dispatcher
    
    def get_servers(self):
        self.speed_test.get_servers(self.servers)
    
    def get_best_server(self):
        self.speed_test.get_best_server()
    
    def download(self):
        self.speed_test.download(threads=self.threads)
    
    def upload(self):
        self.speed_test.upload(threads=self.threads)
    
    def run_speed_test(self):
        self.get_servers()
        self.get_best_server()
        self.download()
        self.upload()
    
    def get_results(self):
        return self.speed_test.results.dict()
    
    def check_internet_speed(self):
        self.run_speed_test()
        results = self.get_results()
        if results:
            print(f"Download = {results['download']/1000000}Mbps and upload = {results['upload']/1000000}Mbps")
        self.dispatcher.dispatch_event("send_network_speed", results)
    
    def check_internet_connection(self):
        ps = subprocess.Popen(['iwgetid'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            output = subprocess.check_output(('grep', 'ESSID'), stdin=ps.stdout)
            if 'TP-Link_A58E' in str(output):
                print("Connected to the TP-Link_A58E network")
                self.dispatcher.dispatch_event("send_network_status", "connected")
            else:
                print(f"Could not find the TP-Link_A5BE network in the output: {str(output)}")
        except subprocess.CalledProcessError:
            # grep did not match any lines
            print("No wireless networks connected")

import time

class ScreenMonitor:
    def __init__(self, event_dispatcher):
        self.dispatcher = event_dispatcher
        self.brightness = 50
        self.is_sleep_timer_enabled = True
        self.is_screen_awake = True
        self.countdown = time.time()

        self.dispatcher.register_event("configure_sleep_timer", self._configure_sleep_timer)
        self.dispatcher.register_event("update_screen_brightness", self._set_screen_brightness)
        self.dispatcher.register_event("reset_sleep_timer", self.reset_sleep_timer)
        self.dispatcher.register_event("update_state_variable", self._update_service_state)

    def _update_service_state(self, payload):
        state_name = payload.get("state_name", "")
        state = payload.get("state_value", [])
        if state_name == "brightness":
            self.brightness = state

    def _configure_sleep_timer(self, control):
        self.is_sleep_timer_enabled = control
        self.reset_sleep_timer()

    def _set_screen_brightness(self, brightness):
        self.brightness = brightness

    def reset_sleep_timer(self):
        self.countdown = time.time()
        self.wake_up_screen()
    
    def put_to_sleep(self):
        print("Putting screen to sleep")
        for brightness in range(0, self.brightness, -1):

            # Map the brightness value from range 1-100 to 1-255
            mapped_value = int(20 + (int(brightness) - 1) * 235 / 99)
            
            try:
                # Update the brightness using the mapped value
                subprocess.run(
                    f'echo {mapped_value} | sudo tee /sys/class/backlight/6-0045/brightness',
                    shell=True,
                    check=True
                )
                # Return a success response
            except subprocess.CalledProcessError as e:
                # Return an error response if the command fails
                return f"send_service_error: {e}"
            
            time.sleep(0.004)
        return f"Brightness successfully dimmed",
    
    def wake_up(self):
        print("Waking up screen")
        self.dispatcher.dispatch_event("send_screen_status", "awake")
        for brightness in range(0, self.brightness):

            # Map the brightness value from range 1-100 to 1-255
            mapped_value = int(20 + (int(brightness) - 1) * 235 / 99)
            
            try:
                # Update the brightness using the mapped value
                subprocess.run(
                    f'echo {mapped_value} | sudo tee /sys/class/backlight/6-0045/brightness',
                    shell=True,
                    check=True
                )
                # Return a success response
            except subprocess.CalledProcessError as e:
                # Return an error response if the command fails
                return f"send_service_error: {e}"
            
            time.sleep(0.004)
        return f"Brightness successfully lit",
            
    def check_for_screen_timeout(self):
        if self.is_sleep_timer_enabled:
            if time.time() - self.countdown > 10:
                self.put_to_sleep()
                print("########################### Screen saver started ############################")
                self.is_sleep_timer_enabled = False
                self.is_screen_awake = False
    
    def wake_up_screen(self):
        if not self.is_screen_awake:
            self.wake_up()
            self.is_sleep_timer_enabled = True
            self.is_screen_awake = True
            self.reset_sleep_timer()