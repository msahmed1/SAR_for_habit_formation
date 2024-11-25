import sys
from src.communication_interface import CommunicationInterface
from custom_logging.logging_config import setup_logger
from time import sleep
from dotenv import load_dotenv
from pathlib import Path
import os
import logging
import threading
import time

# Relative path to the .env file in the config directory
# Move up one level and into config
dotenv_path = Path('../../configurations/.env')

# Load the .env file
load_dotenv(dotenv_path=dotenv_path)

from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QTextEdit
)
from PyQt6.QtGui import QPalette, QColor, QIcon, QPixmap
from PyQt6.QtCore import Qt, QSize


class Color(QWidget):
    def __init__(self, color):
        super(Color, self).__init__()
        self.setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(color))
        self.setPalette(palette)


class HomeScreen(QWidget):
    def __init__(self):
        super().__init__()

        vLayout = QVBoxLayout()

        implementationIntention = QLabel(
            "Implementation intention", alignment=Qt.AlignmentFlag.AlignCenter)
        implementationIntention.setStyleSheet("font-size: 20px")
        vLayout.addWidget(implementationIntention)

        hLayout = QHBoxLayout()
        hLayout.addWidget(QLabel("Check in Date and Time",
                          alignment=Qt.AlignmentFlag.AlignCenter))
        hLayout.addWidget(
            QLabel("Days remaining", alignment=Qt.AlignmentFlag.AlignCenter))

        vLayout.addLayout(hLayout)
        self.setLayout(vLayout)


class CheckInScreen(QWidget):
    def __init__(self, communication_interface):
        self.communication_interface = communication_interface
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        self.vLayout = QVBoxLayout()

        self.conversation_history = QTextEdit(self)
        self.conversation_history.setReadOnly(True)  # Prevent user from editing
        self.conversation_history.setPlaceholderText("Conversation history will appear here...")
        self.vLayout.addWidget(self.conversation_history)

        # infoLayout.addWidget(QLabel("contact"))
        self.start_conversatin_button = QPushButton(
            # Icon made by alimasykurm from @flaticon
            icon=QIcon("../assets/check_in.png"),
            text="Start check in",
            parent=self
        )
        self.start_conversatin_button.clicked.connect(self.button_clicked)
        # self.setCentralWidget(button)
        self.vLayout.addWidget(self.start_conversatin_button)
        self.setLayout(self.vLayout)

        # Connect MQTT signal for updating conversation history
        self.communication_interface.message_signal.connect(self.update_conversation)

    def button_clicked(self):
        sleep(1)
        self.communication_interface.start_check_in()

    def update_conversation(self, message):
        """
        Updates the conversation history with a new message.
        """
        self.logger.info(f"Message received: {message}")
        # Append the new message to the text edit
        self.conversation_history.append(f"{message['sender'].upper()}: {message['content']}")

        # Auto-scroll to the bottom if the user hasn't scrolled up
        scrollbar = self.conversation_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

class NotificationBar(QWidget):
    def __init__(self):
        super().__init__()

        appBarLayout = QHBoxLayout()

        infoLayout = QHBoxLayout()
        # infoLayout.addWidget(QLabel("contact"))
        contactButton = QPushButton(
            # Icon made by alimasykurm from @flaticon
            icon=QIcon("../assets/support_alimasykurm.png"),
            text="Contact",
            parent=self
        )
        contactButton.clicked.connect(self.button_clicked)
        # self.setCentralWidget(button)
        infoLayout.addWidget(contactButton)
        # infoLayout.addWidget(QLabel("help"))
        helpButton = QPushButton(
            # Icon made by Freepik from @flaticon
            icon=QIcon("../assets/question_Freepik.png"),
            text="Help",
            parent=self
        )
        helpButton.clicked.connect(self.button_clicked)
        infoLayout.addWidget(helpButton)
        timeLayout = QHBoxLayout()
        timeLayout.addWidget(QLabel("time"))

        indicatorLayout = QHBoxLayout()

        # wifiStatus = QLabel(self)
        # pixmap = QPixmap('wifi_redempticon.png')
        # wifiStatus.setPixmap(pixmap)
        # self.setCentralWidget(wifiStatus)
        # self.resize(pixmap.width(), pixmap.height())

        wifiStatus = QLabel(self)
        pixmap = QPixmap('../assets/wifi_redempticon.png')
        scaled_pixmap = pixmap.scaled(
            QSize(24, 24), Qt.AspectRatioMode.KeepAspectRatio)
        wifiStatus.setPixmap(scaled_pixmap)
        indicatorLayout.addWidget(wifiStatus)

        self.micStatus = QLabel(self)
        self.micOffPixmap = QPixmap('../assets/microphone-off_Dave_Gandy.png').scaled(
            QSize(24, 24), Qt.AspectRatioMode.KeepAspectRatio)
        self.micOnPixmap = QPixmap('../assets/microphone-black-shape.png').scaled(
            QSize(24, 24), Qt.AspectRatioMode.KeepAspectRatio)
        self.micStatus.setPixmap(self.micOffPixmap)
        indicatorLayout.addWidget(self.micStatus)
        # Dave Gandy for microphone on and off image

        self.camStatus = QLabel(self)
        self.camOffPixmap = QPixmap('../assets/videocam_off_icon_small.png').scaled(
            QSize(24, 24), Qt.AspectRatioMode.KeepAspectRatio)
        self.camOnPixmap = QPixmap('../assets/videocam_icon_small.png').scaled(
            QSize(24, 24), Qt.AspectRatioMode.KeepAspectRatio)
        self.camStatus.setPixmap(self.camOffPixmap)
        indicatorLayout.addWidget(self.camStatus)
        # icon_small for videocam on image
        # icon_small for videocam off image

        appBarLayout.addLayout(infoLayout)
        appBarLayout.addLayout(timeLayout)
        appBarLayout.addLayout(indicatorLayout)

        self.setLayout(appBarLayout)

    def button_clicked(self, s):
        dlg = QMessageBox.about(
            self, "about", "If you need help or encounter any issued with the system please dont hesitate to contact Shabaj using the following contact details:\nEmail:\nPhone:")

        # Method to update mic status
    def update_mic_status(self, is_active):
        if is_active:
            self.micStatus.setPixmap(self.micOnPixmap)
        else:
            self.micStatus.setPixmap(self.micOffPixmap)

    # Method to update cam status
    def update_cam_status(self, is_active):
        if is_active:
            self.camStatus.setPixmap(self.camOnPixmap)
        else:
            self.camStatus.setPixmap(self.camOffPixmap)


class MainWindow(QMainWindow):
    def __init__(self, communication_interface):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        self.setWindowTitle("My App ")

        self.communication_interface = communication_interface

        verticalSpace = QVBoxLayout()

        self.notification_bar = NotificationBar()
        verticalSpace.addWidget(self.notification_bar)
        verticalSpace.addWidget(self.buildTab())

        widget = QWidget()
        widget.setLayout(verticalSpace)
        self.setCentralWidget(widget)

        self.communication_interface.switch_state_signal.connect(self.update_switch_state)
        self.communication_interface.wake_word_signal.connect(self.update_wake_word)
        self.communication_interface.error_signal.connect(self.show_error_message)
        self.communication_interface.audio_signal.connect(
            self.notification_bar.update_mic_status)
        self.communication_interface.camera_signal.connect(
            self.notification_bar.update_cam_status)
        
        self.showMaximized() 

    def buildTab(self):
        home = HomeScreen()
        check_in = CheckInScreen(self.communication_interface)

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.TabPosition.West)
        tabs.setMovable(True)

        tabs.addTab(home, "Home")
        tabs.addTab(check_in, "Check-In")
        tabs.addTab(Color("green"), "History")
        tabs.addTab(Color("yellow"), "Profile")

        return tabs

    def update_switch_state(self, state):
        self.logger.info(f"Switch state changed: {state}")

    def update_wake_word(self, wake_word):
        self.logger.info(f"Wake word detected: {wake_word}")

    def show_error_message(self, error_message):
        QMessageBox.critical(self, "Error", f"Error received: {error_message}")

def publish_heartbeat():
    while True:
        communication_interface.publish_status("running")
        time.sleep(30)  # Publish heartbeat every 30 seconds

if __name__ == "__main__":
    setup_logger()

    logger = logging.getLogger("Main")

    communication_interface = CommunicationInterface(
        broker_address=str(os.getenv("MQTT_BROKER_ADDRESS")),
        port=int(os.getenv("MQTT_BROKER_PORT"))
    )

    threading.Thread(target=publish_heartbeat, daemon=True).start()

    app = QApplication(sys.argv)

    window = MainWindow(communication_interface)

    try:
        window.show()
        app.exec()
    except KeyboardInterrupt:
        logger.info("Exiting user interface service...")
    finally:
        communication_interface.disconnect()