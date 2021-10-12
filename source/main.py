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
from kivy.properties import BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.utils import platform
from kivy.gesture import Gesture, GestureDatabase
from kivy.graphics import Color, Ellipse, Line
from gestures import SwipeRight, SwipeLeft

if kivy.utils.platform == 'android':
	from android.permissions import check_permission
	from android.permissions import Permission

from datetime import datetime
#import plyer

import asyncio
import bleak

import vesc
import struct
import circular_layout
import circular_progress_bar


kivy.require('1.9.1')
INF = float('inf')

UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

class DataScreenPrimary(Screen):
	def __init__(self, *args, **kwargs):
		super(Screen, self).__init__()
		self.name='dataPrimary'
		self.gdb = GestureDatabase()
		# add pre-recorded gestures to database
		self.gdb.add_gesture(SwipeRight)
		self.gdb.add_gesture(SwipeLeft)


	def on_touch_down(self, touch):
		#create an user defined variable and add the touch coordinates 
		touch.ud['gesture_path'] = [(touch.x, touch.y)]    
		super(DataScreenPrimary, self).on_touch_down(touch)

	def on_touch_move(self, touch):
		touch.ud['gesture_path'].append((touch.x, touch.y))
		super(DataScreenPrimary, self).on_touch_move(touch)

	def on_touch_up(self, touch):
		if 'gesture_path' in touch.ud:
			#create a gesture object
			gesture = Gesture()    
			#add the movement coordinates 
			gesture.add_stroke(touch.ud['gesture_path'])
			gesture.normalize()
			match = self.gdb.find(gesture, minscore=0.70)
			#Logger.info(f'WearVesc: RecordedGesture {self.gdb.gesture_to_str(gesture)}')
			#Logger.info(f'WearVesc: SwipeRight Score {gesture.get_score(SwipeRight)}')
			#Logger.info(f'WearVesc: SwipeLeft Score {gesture.get_score(SwipeLeft)}')
			if match:
				if match[1] == SwipeRight:
					Logger.info(f'WearVesc: ExitSwipe Detected')
					app.stop()
				if match[1] == SwipeLeft:
					Logger.info(f'WearVesc: SettingsSwipe Detected')
					app.root.transition.direction = 'left'
					app.root.current = 'settings'



class DataScreenSecondary(Screen):
    pass

class DataScreen(Screen):
    pass

class SettingsScreen(Screen):
    pass

class ScanScreen(Screen):
    pass

class DisclosureScreen(Screen):
    pass


class NumericInput(BoxLayout):
	title = StringProperty('')
	value = NumericProperty(0)
	min = NumericProperty(-INF)
	max = NumericProperty(INF)
	step = NumericProperty(1)

class SwapLabel(Button):
	
	switched = BooleanProperty(False)

	def __init__(self, **kwargs):
		super(SwapLabel, self).__init__(**kwargs)
		self._primary_text = ""
		self._secondary_text = ""
		self._update()

	@property
	def primary_text(self):
		return self._primary_text

	@primary_text.setter
	def primary_text(self, primary_text: str):
		if type(primary_text) != str:
			raise TypeError("primary_text must be an string, not {}!".format(type(primary_text)))
		elif primary_text != self._primary_text:
			self._primary_text = primary_text
			self._update()
	@property
	def secondary_text(self):
		return self._secondary_text

	@secondary_text.setter
	def secondary_text(self, secondary_text: str):
		if type(secondary_text) != str:
			raise TypeError("secondary_text must be an string, not {}!".format(type(secondary_text)))
		elif secondary_text != self._secondary_text:
			self._secondary_text = secondary_text
			self._update()

	def switch(self):
		self.switched = not self.switched
		self._update()

	def _update(self):
		if self.switched:
			self.text = self._secondary_text
		else:
			self.text = self._primary_text



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
		self.Data_Screen_Primary = DataScreenPrimary(name='dataPrimary')
		self.Data_Screen_Secondary = DataScreenSecondary(name='dataSecondary')
		self.Settings_Screen = SettingsScreen(name='settings')
		self.Scan_Screen = ScanScreen(name='scan')
		self.Disclosure_Screen = DisclosureScreen(name='disclosure')

		self.screen_manager.add_widget(self.Data_Screen_Primary)
		self.screen_manager.add_widget(self.Data_Screen_Secondary)
		self.screen_manager.add_widget(self.Settings_Screen)
		self.screen_manager.add_widget(self.Scan_Screen)
		self.screen_manager.add_widget(self.Disclosure_Screen)

		self.screen_manager.current = 'dataPrimary'

		if kivy.utils.platform == 'android':
			if not check_permission(Permission.ACCESS_FINE_LOCATION):
				self.screen_manager.current = 'disclosure'

		return self.screen_manager

	def build_config(self, config):
		config.setdefaults('wearvesc', {
			'address': 'FA:B2:4E:80:50:90',
			'poll': '5',
			'cells': '12',
			'cmin': '3.0',
			'cmax': '4.2',
			'unit': 'KMH',
		})

	def update_config(self):
		self.config.set('wearvesc','cells', self.Settings_Screen.ids.cells.value)
		self.config.set('wearvesc','unit', self.Settings_Screen.ids.unit.text)
		self.config.set('wearvesc','poll', self.Settings_Screen.ids.poll.value)
		self.config.set('wearvesc','cmin', self.Settings_Screen.ids.cmin.value)
		self.config.set('wearvesc','cmax', self.Settings_Screen.ids.cmax.value)
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
				self.Data_Screen_Primary.ids.time.text = time.strftime("%I:%M")
			except:
				await asyncio.sleep(1)
			await asyncio.sleep(0.15)

	async def bluetooth(self):
		# create packet that requests current_in(), speed, voltage_in, battery_level from COMM_GET_VALUES_SETUP_SELECTIVE
		packet_get_values = vesc.Packet()
		packet_get_values.size = 2
		packet_get_values.payload = struct.pack('>BI', 51, (1 << 0) | (1 << 1) | (1 << 3) | (1 << 4) | (1 << 6) | (1 << 7))
		packet_get_values.encode()

		packet_get_ballance = vesc.Packet()
		packet_get_ballance.size = 2
		packet_get_ballance.payload = struct.pack('>B', 79)
		packet_get_ballance.encode()
		self.is_balance = True

		def handle_disconnect(_: bleak.BleakClient):
			Logger.info(f'WearVesc: Device Disconnected')
			self.Data_Screen_Primary.ids.status.text = "Disconnected"

		def handle_rx(_: int, data: bytearray):
			#Logger.info(f'WearVesc: Got Data {str(data)}')
			self.buffer.extend(data)
			found, packet = self.buffer.next_packet()

			if found:
				Logger.info(f'WearVesc: Found Packet {str(packet)}')
				if packet.payload[0:len(packet_get_values.payload)] == packet_get_values.payload:
					if self.config.get('wearvesc','unit') == 'KMH':
						conversion_factor = 3.6
					else:
						conversion_factor = 2.237
					mostemp : float = struct.unpack('>H', packet.payload[5:7])[0] / 10
					mottemp : float = struct.unpack('>H', packet.payload[7:9])[0] / 10
					current : float = struct.unpack('>i', packet.payload[9:13])[0] / 100
					dutycycle : float = struct.unpack('>h', packet.payload[13:15])[0] / 10
					speed : float = (struct.unpack('>i', packet.payload[15:19])[0] / 1000) * conversion_factor
					voltage : float = struct.unpack('>H', packet.payload[19:21])[0] / 10

					cells : int = int(self.config.get('wearvesc', 'cells'))
					cellv : float = voltage / cells
					cmin : float = float(self.config.get('wearvesc', 'cmin'))
					cmax : float = float(self.config.get('wearvesc', 'cmax'))
					batp : float = (cellv-cmin)/(cmax-cmin)*100

					self.Data_Screen_Primary.ids.speed.text = f'{abs(speed):.1f}'
					self.Data_Screen_Primary.ids.voltage.primary_text = f'{voltage:.2f} V'
					self.Data_Screen_Primary.ids.voltage.secondary_text = f'{cellv:.2f} V'
					self.Data_Screen_Primary.ids.current.text = f'{current:.2f} A'
					self.Data_Screen_Primary.ids.dutycycle.value = int(round(abs(dutycycle), 0))
					self.Data_Screen_Primary.ids.battery.value = int(round(min(batp, 100), 0))
					self.Data_Screen_Primary.ids.temp.primary_text = f'FET\n{mostemp:.0f}°C'
					self.Data_Screen_Primary.ids.temp.secondary_text = f'MOT\n{mottemp:.0f}°C'
			
				if packet.payload[0:len(packet_get_ballance.payload)] == packet_get_ballance.payload:
					balappstate : int = struct.unpack('>H', packet.payload[25:27])[0]
					if balappstate > 0:
						footstate : int = struct.unpack('>H', packet.payload[27:29])[0]
						footstates = ["OFF", "HALF", "FULL"]
						self.Data_Screen_Primary.ids.state.text = f'{footstates[footstate]}'
					else:
						self.is_balance = False

		def setAddress(instance):
			Logger.info(f'WearVesc: Setting Address to {instance.address}')
			self.config.set('wearvesc','address', instance.address)
			self.update_config()
			self.scanning = False
			self.root.transition.direction = 'right'
			self.root.current = 'dataPrimary'

		while self.running:
			try:
				if hasattr(self, 'Data_Screen_Primary'):
					self.Data_Screen_Primary.ids.status.text = "Disconnected"

				if self.screen_manager.current == 'disclosure':
					continue
				
				#scann for devices

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

				async with bleak.BleakClient(self.config.get('wearvesc', 'address'), disconnected_callback=handle_disconnect) as client:
					await client.start_notify(UART_TX_CHAR_UUID, handle_rx)
					if client.is_connected:
						self.Data_Screen_Primary.ids.status.text = "Connected"

					while self.running and not self.scanning:
						await asyncio.sleep(1/int(self.config.get('wearvesc', 'poll')))
						if client.is_connected:
							await client.write_gatt_char(UART_RX_CHAR_UUID, bytearray(packet_get_values.packet))
							if self.is_balance:
								await client.write_gatt_char(UART_RX_CHAR_UUID, bytearray(packet_get_ballance.packet))

			except bleak.exc.BleakError as e:
				Logger.info(f'WearVesc: {e}')
				await asyncio.sleep(1)
			except asyncio.exceptions.TimeoutError as e:
				Logger.info(f'WearVesc: async Timeout Error')
				await asyncio.sleep(1)

async def main(app):
	await asyncio.gather(app.async_run("asyncio"), app.bluetooth(), app.timekeeper())

if __name__ == '__main__':
	app = MainApp()
	asyncio.run(main(app))