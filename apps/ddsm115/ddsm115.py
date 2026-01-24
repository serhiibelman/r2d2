import struct

import crcmod.predefined

import serial
import serial.rs485

from apps.common.converters import int16_to_bytes
from apps.common.formatting import print_info, print_error, print_warning
from settings import DEVICE


class Int16ToBytesArray:
    def __init__(self, data: int):
        self.byte1 = (data & 0xFF00) >> 8
        self.byte2 = data & 0x00FF

    def get_bytes(self):
        return [self.byte1, self.byte2]


class DDS115:
    def __init__(self, device=DEVICE):
        self.ser = serial.rs485.RS485(device, 115200, timeout=0)
        self.ser.rs485_mode = serial.rs485.RS485Settings()
        self.crc8 = crcmod.predefined.mkPredefinedCrcFun("crc-8-maxim")
        self.str_10bytes = ">BBBBBBBBBB"
        self.str_9bytes = ">BBBBBBBBB"

        self.prev_fb_rpm = [0, 0, 0, 0]
        self.prev_fb_cur = [0, 0, 0, 0]

    def crc_attach(self, data_bytes: bytes):
        crc_int = self.crc8(data_bytes)
        data_bytearray = bytearray(data_bytes)
        data_bytearray.append(crc_int)
        return bytes(data_bytearray)

    def set_id(self, motor_id: int):
        """
        Connect only 1 motor, and call this function to set the ID of that motor
        """
        # fmt: off
        set_id = struct.pack(
            self.str_10bytes,0xAA, 0x55, 0x53, motor_id, 0x00, 0x00, 0x00, 0x00, 0x00, 0xDE
        )
        for i in range(5):
            self.ser.write(set_id)

    def get_motor_id(self):
        # fmt: off
        id_que = struct.pack(
            self.str_10bytes, 0xC8, 0x64, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xDE
        )
        self.ser.write(id_que)
        data = self.ser.read_until(size=10)

        print(data)
        print_info(f"ID: {data[0]}")
        print_info(f"Mode: {data[1]}")
        print_error(f"Error: {data[8]}")

    def send_rpm(self, motor_id: int, rpm):

        rpm = int(rpm)
        # TODO: check function
        # rpm_ints = Int16ToBytesArray(rpm).get_bytes()
        rpm_ints = int16_to_bytes(rpm)
        cmd_bytes = struct.pack(
            self.str_9bytes, motor_id, 0x64, rpm_ints[0], rpm_ints[1], 0x00, 0x00, 0x00, 0x00, 0x00
        )
        cmd_bytes = self.crc_attach(cmd_bytes)

        while not self.ser.writable():
            print_warning("send_rpm not writable")
            pass
        self.ser.write(cmd_bytes)

        # _, _, _ = self.read_reply(_id)

    def set_brake(self, motor_id: int):
        # fmt: off
        cmd_bytes = struct.pack(
            self.str_9bytes, motor_id, 0x64, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00
        )
        cmd_bytes = self.crc_attach(cmd_bytes)
        self.ser.write(cmd_bytes)
        res = self.ser.read_until(size=10)
