import struct
import time
from typing import Optional

import crcmod.predefined

import serial
import serial.rs485

from settings import DEVICE
from lib.common.converters import int16_to_bytes
from lib.common.formatting import print_info, print_error, print_warning
from .motor_frame import Frame


class DDS115:
    BAUDRATE = 115200
    CMD_SET_ID = 0x53
    CMD_CONTROL = 0x64
    FRAME_END = 0xDE

    def __init__(self, device=DEVICE):
        try:
            self.ser = serial.rs485.RS485(device, self.BAUDRATE, timeout=0.1)
            self.ser.rs485_mode = serial.rs485.RS485Settings()
        except serial.SerialException as e:
            raise RuntimeError(f"Failed to open serial device {device}") from e

        self.crc8 = crcmod.predefined.mkPredefinedCrcFun("crc-8-maxim")

        self._fmt_10 = ">BBBBBBBBBB"
        self._fmt_9 = ">BBBBBBBBB"

        self.prev_fb_rpm = [0] * 4
        self.prev_fb_cur = [0] * 4

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def _check_motor_id(self, motor_id: int) -> None:
        if not 0 <= motor_id <= 255:
            raise ValueError("motor_id must be in range 0..255")

    def _crc_attach(self, payload: bytes) -> bytes:
        return payload + bytes([self.crc8(payload)])

    def _write(self, data: bytes) -> None:
        """
        RS-485 safe write.
        No busy-looping, no fake 'writable()' checks.
        """
        self.ser.reset_output_buffer()
        self.ser.write(data)
        self.ser.flush()
        time.sleep(0.001)  # allow TX to finish on half-duplex bus

    # -------------------------------------------------
    # protocol commands
    # -------------------------------------------------

    def set_id(self, motor_id: int) -> None:
        """
        Connect ONLY one motor when calling this.
        """
        self._check_motor_id(motor_id)

        frame = struct.pack(
            self._fmt_10,
            0xAA,
            0x55,
            self.CMD_SET_ID,
            motor_id,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            self.FRAME_END,
        )

        for _ in range(5):
            self._write(frame)
            time.sleep(0.05)

    def get_motor_id(self) -> None:
        frame = struct.pack(
            self._fmt_10,
            0xC8,
            self.CMD_CONTROL,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            self.FRAME_END,
        )

        self._write(frame)

        reply = self.read_reply(motor_id=0xC8, timeout=0.05)
        if reply is None:
            print_warning("No response")
            return

        print_info(f"ID: {reply.id}")
        print_info(f"Mode: {reply.mode}")
        print_error(f"Error: {reply.error}")

    def send_rpm(self, motor_id: int, rpm: int = 0) -> None:
        self._check_motor_id(motor_id)

        if not -32768 <= rpm <= 32767:
            raise ValueError("rpm must fit int16")

        hi, lo = int16_to_bytes(rpm)

        frame = struct.pack(
            self._fmt_9,
            motor_id,
            self.CMD_CONTROL,
            hi,
            lo,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
        )

        self._write(self._crc_attach(frame))
        self.read_reply(motor_id)

    def set_brake(self, motor_id: int):
        frame = struct.pack(
            self._fmt_9,
            motor_id,
            self.CMD_CONTROL,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0xFF,
            0x00,
        )

        self._write(self._crc_attach(frame))
        self.read_reply(motor_id)

    def read_reply(
        self,
        motor_id: int,
        timeout: float = 0.02,
    ) -> Optional[Frame]:
        """
        Sliding-window frame parser.
        Safe for noisy RS-485 lines.
        """
        buffer = bytearray()
        start = time.monotonic()

        while time.monotonic() - start < timeout:
            chunk = self.ser.read(1)
            if not chunk:
                continue

            buffer.append(chunk[0])

            if len(buffer) > Frame.FRAME_SIZE:
                buffer.pop(0)

            if len(buffer) == Frame.FRAME_SIZE:
                try:
                    frame = Frame.from_bytes(bytes(buffer), self.crc8)
                except ValueError:
                    continue

                if frame.id == motor_id:
                    self.prev_fb_rpm[motor_id - 1] = frame.rpm
                    self.prev_fb_cur[motor_id - 1] = frame.current_raw
                    return frame

        return None
