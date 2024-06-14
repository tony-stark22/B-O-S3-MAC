import sys
import asyncio
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QLineEdit, QWidgetAction, QLabel, QSlider, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QMetaObject, Q_ARG, pyqtSlot, QTimer, QEvent, QObject
import bleak
from bleak import BleakScanner, BleakClient
from typing import Optional, Dict
import threading
import time

# Define the UUIDs and profiles for the Beoplay S3 device
PROFILES = [
    {
        'NAME': "Beoplay S3",
        'FUNCTION_SERVICE_ID': "0000fe89-0000-1000-8000-00805f9b34fb",
        'INFO_SERVICE_ID': "0000180a-0000-1000-8000-00805f9b34fb",
        'POWER_CHAR_ID': "7dd2f744-16c4-4c58-88a4-0fafecc78343",
        'VOLUME_CHAR_ID': "44fa50b2-d0a3-472e-a939-d80cf17638bb",
        'NAME_CHAR_ID': "3ba91c2e-8b08-4c27-9d4e-4936a793fcfb",
        'SLEEP_CHAR_ID': "4446cf5f-12f2-4c1e-afe1-b15797535ba8"
    },
    {
        'NAME': "Beoplay SX",
        'FUNCTION_SERVICE_ID': "0000fe89-0000-1000-8000-00805f9b34fb",
        'INFO_SERVICE_ID': "0000180a-0000-1000-8000-00805f9b34fb",
        'POWER_CHAR_ID': "7dd2f744-16c4-4c58-88a4-0fafecc78343",
        'VOLUME_CHAR_ID': "44fa50b2-d0a3-472e-a939-d80cf17638bb",
        'NAME_CHAR_ID': "3ba91c2e-8b08-4c27-9d4e-4936a793fcfb",
        'SLEEP_CHAR_ID': "4446cf5f-12f2-4c1e-afe1-b15797535ba8"
    }
]

# Define the settings
SETTINGS = {
    'ALWAYS_AWAKE': False,
    'CONSUME_MEDIA_KEYS': False,
    'LOAD_AT_STARTUP': True,
    'POWER_OFF_AT_SHUTDOWN': False,
    'SCAN_TIME': 10000,  # 10 seconds
    'SHOW_WINDOW_WHEN_CHANGE': True
}
class MenuBarApp(QSystemTrayIcon):
    update_menu_signal = pyqtSignal(bool)
    update_volume_label_signal = pyqtSignal(int)
    def __init__(self):
        super().__init__()
        self.setIcon(QIcon("icon.png"))  # Replace with your icon path
        self.setVisible(True)
        self.menu = QMenu()
        self.loading_label = QLabel("Loading...")
        self.clients: Dict[str, BleakClient] = {}
        self.volume_characteristics: Dict[str, str] = {}
        self.connection_thread = threading.Thread(target=self.connect_to_devices)
        self.connection_thread.start()
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.valueChanged.connect(self.slider_value_changed)  # Connect directly to slider_value_changed
        self.volume_label = QLabel("Current Volume: --")
        self.update_menu_signal.connect(self.update_menu)
        self.update_volume_label_signal.connect(self.update_volume_label)
        self.setContextMenu(self.menu)
    def slider_value_changed(self, value):
        """Handle slider value changes by setting the volume immediately."""
        self.update_volume_label_signal.emit(value)  # Update the label immediately
        loop = asyncio.new_event_loop()  # Create a new event loop for the async call
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.set_volume(value))  # Set the volume immediately
    async def set_volume(self, volume):
        for name, client in self.clients.items():
            if client.is_connected:
                try:
                    volume_char_id = self.volume_characteristics[name]
                    await client.write_gatt_char(volume_char_id, bytes([volume]))
                    print(f"Volume set to {volume} for {name}")
                except Exception as e:
                    print(f"Error setting volume for {name}: {e}")
            else:
                print(f"{name} is not connected.")
    def update_volume_label(self, volume):
        """Update the volume label with the current volume."""
        self.volume_label.setText(f"Current Volume: {volume}")
    def connect_to_devices(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.setup_connections())
    async def setup_connections(self):
        devices = await BleakScanner.discover()
        for device in devices:
            for profile in PROFILES:
                if device.name == profile['NAME']:
                    client = BleakClient(device.address)
                    try:
                        await client.connect()
                        self.clients[device.name] = client
                        self.volume_characteristics[device.name] = profile['VOLUME_CHAR_ID']
                    except Exception as e:
                        print(f"Failed to connect to {device.name}: {e}")
        self.update_menu_signal.emit(False)
    def update_volume_from_slider(self):
        value = self.volume_slider.value()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.set_volume(value))
    def update_menu(self, loading=False):
        self.menu.clear()
        if loading: 
            self.menu.addAction(self.loading_label)
        else:
            volume_widget = QWidget()
            volume_layout = QVBoxLayout()
            volume_layout.addWidget(self.volume_slider)
            volume_widget.setLayout(volume_layout)
            volume_widget_action = QWidgetAction(self.menu)
            volume_widget_action.setDefaultWidget(volume_widget)
            self.menu.addAction(volume_widget_action)
            self.volume_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            volume_label_action = QWidgetAction(self.menu)
            volume_label_action.setDefaultWidget(self.volume_label)
            self.menu.addAction(volume_label_action)
            quit_action = QAction("Quit", self.menu)
            quit_action.triggered.connect(self.quit)
            self.menu.addAction(quit_action)
        self.setContextMenu(self.menu)
    def quit(self):
        # Create a new event loop for disconnecting clients
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)  # Set it as the current event loop
        
        try:
            loop.run_until_complete(self.disconnect_all())
        finally:
            loop.close()  # Close the event loop after use
            
        QApplication.quit()
    async def disconnect_all(self):
        for client in self.clients.values():
            if client.is_connected:
                await client.disconnect()
if __name__ == "__main__":
    app = QApplication(sys.argv)
    menu_bar_app = MenuBarApp()
    sys.exit(app.exec())
