from struct import pack
import vesc

print("Testing Packet Encode")
test1 = vesc.Packet()
test1.size = 2
test1.payload = b'\x04'
test1.encode()
print(test1)
if test1.packet == b'\x02\x01\x04\x40\x84\x03':
	print("Encode Passed")

print("Testing Packet Decode")
test2 = vesc.Packet()
test2.packet = b'\x02\x01\x04\x40\x84\x03'
test2.decode()
print(test1.size, test1.payload, test1.crc)
if test1.payload == b'\x04' and test1.crc == b'\x40\x84' and test1.size == 2:
	print("Decode Passed")

print("Testing Packet Validate")
test3 = vesc.Packet()
test3.payload = b'\x04'
test3.crc = b'\x40\x84'

test4 = vesc.Packet()
test4.payload = b'\x04'
test4.crc = b'\x38\x82'

print(test3.validate(), test4.validate())

if test3.validate() and not test4.validate():
	print("Validate Passed")


print("testing buffer")
buffer1 = vesc.Buffer()
buffer1.extend(b'\x02\x04\x02\x01\x04\x40\x84\x03\x02\x03')
packet_exists, packet = buffer1.next_packet()
print(packet_exists)
print(packet)
print(buffer1.buffer)

if buffer1.buffer == bytearray(b'\x02\x03') and packet_exists and packet.payload == b'\x04':
	print("buffer Passed")