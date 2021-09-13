import kivy
from kivy import logger
from kivy import config
from kivy.app import App
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.properties import NumericProperty
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout

from datetime import datetime
#import plyer

import asyncio
import bleak

import vesc
import struct

kivy.require('1.9.1')
INF = float('inf')

UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

class DataScreen(Screen):
    pass

class SettingsScreen(Screen):
    pass

class ScanScreen(Screen):
    pass


class NumericInput(BoxLayout):
	title = StringProperty('')
	value = NumericProperty(0)
	min = NumericProperty(-INF)
	max = NumericProperty(INF)
	step = NumericProperty(1)

class MainApp(App):
	def __init__(self):
		super().__init__()
		self.label = None
		self.running = True
		self.scanning = False
		self.buffer = vesc.Buffer()

	def build(self):
		self.title = "Telemetry System"
		self.icon = 'icon/1024.png'
		Builder.load_file('view/app.kv')
		self.screen_manager = ScreenManager()

		self.Data_Screen = DataScreen(name='data')
		self.Settings_Screen = SettingsScreen(name='settings')
		self.Scan_Screen = ScanScreen(name='scan')

		self.screen_manager.add_widget(self.Data_Screen)
		self.screen_manager.add_widget(self.Settings_Screen)
		self.screen_manager.add_widget(self.Scan_Screen)

		return self.screen_manager

	def build_config(self, config):
		config.setdefaults('wearvesc', {
			'address': 'FA:B2:4E:80:50:90',
			'poll': '5',
			'cells': '12',
			'unit': 'KMH',
		})

	def update_config(self):
		self.config.set('wearvesc','cells', self.Settings_Screen.ids.cells.value)
		self.config.set('wearvesc','unit', self.Settings_Screen.ids.unit.text)
		self.config.set('wearvesc','poll', self.Settings_Screen.ids.poll.value)
		self.config.write()

	def on_stop(self):
		self.running = False
	
	def on_pause(self):
		Logger.info(f'WearVesc: Paused!!')
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
		# create packet that requests current_in(), speed, voltage_in, battery_level from COMM_GET_VALUES_SETUP_SELECTIVE
		packet_get_values = vesc.Packet()
		packet_get_values.size = 2
		packet_get_values.payload = struct.pack('>BI', 51, (1 << 3) | (1 << 4) | (1 << 6) | (1 << 7) | (1 << 8))
		packet_get_values.encode()

		while self.running:
			try:
				self.Data_Screen.ids.status.text = "Disconnected"

				#scann for devices

				def setAddress(instance):
					Logger.info(f'WearVesc: Setting Address to {instance.address}')
					self.config.set('wearvesc','address', instance.address)
					self.update_config()
					self.scanning = False
					self.root.transition.direction = 'right'
					self.root.current = 'data'

				if self.scanning:
					scanned_address = []
					def find_uart_device(device, adv):
						if UART_SERVICE_UUID.lower() in adv.service_uuids and not device.address in scanned_address:
							Logger.info(f'WearVesc: {str(device)[:24]} {device.rssi}dB')
							button = Button(text=str(device.name), on_release=setAddress)
							button.address = str(device.address)
							self.Scan_Screen.ids.devices.add_widget(button)
							scanned_address.append(device.address)
					
					scanner = bleak.BleakScanner()
					scanner.register_detection_callback(find_uart_device)
					scanned_address.clear()
					self.Scan_Screen.ids.devices.clear_widgets()
					await scanner.start()
					Logger.info(f'WearVesc: Scanning For Devices')
					await asyncio.sleep(5.0)
					await scanner.stop()

					await asyncio.sleep(10)

					continue

				device = await bleak.BleakScanner.find_device_by_address(self.config.get('wearvesc', 'address'), 5)

				if device == None:
					Logger.info(f'WearVesc: Device Not Found')
					continue

				def handle_disconnect(_: bleak.BleakClient):
					Logger.info(f'WearVesc: Device Disconnected')
					self.Data_Screen.ids.status.text = "Disconnected"

				def handle_rx(_: int, data: bytearray):
					self.buffer.extend(data)
					found, packet = self.buffer.next_packet()

					if found:
						Logger.info(f'WearVesc: Found Packet {str(packet)}')
						if packet.payload[0:len(packet_get_values.payload)] == packet_get_values.payload:
							if self.config.get('wearvesc','unit') == 'KMH':
								conversion_factor = 3.6
							else:
								conversion_factor = 2.237
							dutycycle : float = struct.unpack('>h', packet.payload[9:11])[0] / 10
							speed : float = (struct.unpack('>i', packet.payload[11:15])[0] / 1000) * conversion_factor
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

					while self.running and not self.scanning:
						await asyncio.sleep(1/int(self.config.get('wearvesc', 'poll')))
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