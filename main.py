import kivy
from kivy import logger
from kivy.app import App
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.uix.screenmanager import ScreenManager, Screen

from datetime import datetime
#import plyer

import asyncio
import bleak

import vesc
import struct

kivy.require('1.9.1')

UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

# create packet that requests current_in(), speed, voltage_in, battery_level from COMM_GET_VALUES_SETUP_SELECTIVE
packet_get_values = vesc.Packet()
packet_get_values.size = 2
packet_get_values.payload = struct.pack('>BI', 51, (1 << 3) | (1 << 4) | (1 << 6) | (1 << 7) | (1 << 8))
packet_get_values.encode()

class DataScreen(Screen):
    pass

class SettingsScreen(Screen):
    pass

class ScanScreen(Screen):
    pass

class MainApp(App):
	def __init__(self):
		super().__init__()
		self.label = None
		self.running = True
		self.buffer = vesc.Buffer()

	def build(self):
		#self.title = "Telemetry System"
		#self.root = Builder.load_file('view/app.kv')
		Builder.load_file('view/app.kv')
		self.screen_manager = ScreenManager()

		self.Data_Screen = DataScreen(name='data')
		self.Settings_Screen = SettingsScreen(name='settings')
		self.Scan_Screen = ScanScreen(name='scan')

		self.screen_manager.add_widget(self.Data_Screen)
		self.screen_manager.add_widget(self.Settings_Screen)
		self.screen_manager.add_widget(self.Scan_Screen)

		#sm.switch_to(DataScreen())

		return self.screen_manager
		#return self.root

	def build_config(self, config):
		#E2:2F:B4:84:6E:B2
		config.setdefaults('wearvesc', {
			'address': 'FA:B2:4E:80:50:90',
			'poll': '0.2',
			'cells': '12',
		})

	def on_stop(self):
		self.running = False
	
	def on_pause(self):
		Logger.info(f'Application: Paused!!')
		return True

	async def timekeeper(self):
		while self.running:
			time = datetime.now()
			try:
				self.Data_Screen.ids.time.text = time.strftime("%I:%M")
			except:
				await asyncio.sleep(1)
			await asyncio.sleep(0.15)

	async def bluetooth(self):
		while self.running:
			try:
				self.Data_Screen.ids.status.text = "Disconnected"
				device = await bleak.BleakScanner.find_device_by_address(self.config.get('wearvesc', 'address'), 10)
				if device == None:
					Logger.info(f'Application: Device Not Found')
					continue

				def handle_disconnect(_: bleak.BleakClient):
					Logger.info(f'Application: Device Disconnected')
					self.Data_Screen.ids.status.text = "Disconnected"

				def handle_rx(_: int, data: bytearray):
					self.buffer.extend(data)
					found, packet = self.buffer.next_packet()

					if found:
						Logger.info(f'Application: Found Packet {str(packet)}')
						if packet.payload[0:5] == struct.pack('>BI', 51, (1 << 3) | (1 << 4) | (1 << 6) | (1 << 7) | (1 << 8)):
							dutycycle : float = struct.unpack('>h', packet.payload[9:11])[0] / 10
							speed : float = (struct.unpack('>i', packet.payload[11:15])[0] / 1000)* 3.6
							voltage : float = struct.unpack('>H', packet.payload[15:17])[0] / 10
							current : float = struct.unpack('>i', packet.payload[5:9])[0] / 100

							cells : int = int(self.config.get('wearvesc', 'cells'))

							self.Data_Screen.ids.speed.text = f'{abs(speed):.1f}'
							self.Data_Screen.ids.voltage.text = f'{voltage:.2f} V'
							self.Data_Screen.ids.cell.text = f'{(voltage / cells):.2f} V'
							self.Data_Screen.ids.current.text = f'{current:.2f} A'
							self.Data_Screen.ids.dutycycle.text = f'{abs(dutycycle):.0f}%'
						pass

				async with bleak.BleakClient(device, disconnected_callback=handle_disconnect) as client:
					await asyncio.sleep(2)
					await client.start_notify(UART_TX_CHAR_UUID, handle_rx)
					if client.is_connected:
						self.Data_Screen.ids.status.text = "Connected"

					loop = asyncio.get_event_loop()

					while self.running:
						await asyncio.sleep(float(self.config.get('wearvesc', 'poll')))
						await client.write_gatt_char(UART_RX_CHAR_UUID, bytearray(packet_get_values.packet))

			except:
				Logger.exception('Bluetooth Error: damn')
				await asyncio.sleep(1)

if __name__ == '__main__':
	app = MainApp()
	loop = asyncio.get_event_loop()
	coroutines = (app.async_run("asyncio"), app.bluetooth(), app.timekeeper())
	firstcompleted = asyncio.wait(coroutines, return_when=asyncio.FIRST_COMPLETED)
	results, ongoing = loop.run_until_complete(firstcompleted)
	for result in results:
			result.result()  # raises exceptions from asyncio.wait