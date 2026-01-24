import struct


def int16_to_bytes(value: int) -> bytes:
    return struct.pack(">h", value)


def bytes_to_int16(data: bytes) -> int:
    return struct.unpack(">h", data)[0]
