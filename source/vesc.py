from PyCRC.CRCCCITT import CRCCCITT
import struct

class Buffer:
	"""Vesc Buffer loads and finds packets"""
	def __init__(self):
		self.__buffer : bytearray = bytearray()

	def extend(self, data: bytearray):
		self.__buffer.extend(data)

	def clear(self, data: bytearray):
		self.__buffer.clear()

	@property
	def buffer(self):
		return bytearray(self.__buffer)

	def next_packet(self):
		packet_exists = False
		packet = Packet()

		for v_index, v_byte in enumerate(self.__buffer):
			#check if valid packet
			#fist byte in packet for size mode 2
			if v_byte == 2:
				v_length = self.__buffer[v_index+1]
				v_end = v_index + v_length + 4
				#check for end byte in packet
				if v_end + 1 > len(self.__buffer):
					break

				if self.__buffer[v_end] == 3:
					packet.packet = bytes(self.__buffer[v_index : v_end])
					packet.decode()
					#check crc of packet
					if packet.validate():
						#clear out bad data and proccesed packet from buffer
						packet_exists = True
						del self.__buffer[0:v_end+1]
		
		return packet_exists, packet

	def __str__(self):
		"""Buffer as string"""
		return ' '.join([hex(x) for x in self.__buffer])



class Packet:
	"""Vesc Packet load data then encode or decode"""
	def __init__(self):
		"""Vesc Packet load data then encode or decode. size is 2 for small packets and 3 for large packets. size 2 is the only implemented size so far"""
		self.__size : int = None
		self.__payload : bytes = bytes()
		self.__packet : bytes = bytes()
		self.__crc : bytes = bytes()

	@property
	def size(self):
		return self.__size

	@size.setter
	def size(self, size):
		if (size == 2 or size == 3):
			self.__size = size
		else:
			raise ValueError('Size must be 2 or 3')

	@property
	def payload(self):
		return self.__payload

	@payload.setter
	def payload(self, payload : bytes):
		self.__payload = bytes(payload)

	@property
	def packet(self):
		return self.__packet

	@packet.setter
	def packet(self, packet : bytes):
		self.__packet = bytes(packet)

	@property
	def crc(self):
		return self.__crc

	@crc.setter
	def crc(self, crc : bytes):
		self.__crc = bytes(crc)

	def encode(self):
		self.__crc = struct.pack('>H', CRCCCITT().calculate(self.__payload))
		if self.__size == 2:
			self.__packet = struct.pack('>BB' + str(len(self.__payload)) + 's2sB', self.__size, len(self.__payload), self.__payload, self.__crc, 3)
		elif self.__size == 3:
			# TODO: implement size 3 packets
			pass

	def decode(self):
		self.__size = ord(self.__packet[:1])
		if self.__size == 2:
			length = ord(self.__packet[1:2])
			self.__payload = self.__packet[2:2+length]
			self.__crc = self.__packet[2+length:4+length]
			self.__packet = struct.pack('>BB' + str(len(self.__payload)) + 's2sB', self.__size, len(self.__payload), self.__payload, self.__crc, 3)
		elif self.__size == 3:
			# TODO: implement size 3 packets
			pass

	def validate(self):
		return struct.pack('>H', CRCCCITT().calculate(self.__payload)) == self.__crc

	def __str__(self):
		"""Packet as string"""
		return ' '.join([hex(x) for x in self.__packet])