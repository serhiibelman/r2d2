from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class Frame:
    FRAME_SIZE: ClassVar[int] = 10
    MODE_EXPECTED: ClassVar[int] = 0x02

    id: int
    mode: int
    current_raw: int
    rpm: int
    error: int
    crc: int

    @classmethod
    def from_bytes(cls, raw: bytes, crc8_func) -> "Frame":
        if len(raw) != cls.FRAME_SIZE:
            raise ValueError("Invalid frame length")

        if raw[1] != cls.MODE_EXPECTED:
            raise ValueError("Invalid mode")

        crc_expected = crc8_func(raw[:-1])
        if raw[-1] != crc_expected:
            raise ValueError("CRC mismatch")

        current_raw = (raw[2] << 8) | raw[3]
        rpm = (raw[4] << 8) | raw[5]

        return cls(
            id=raw[0],
            mode=raw[1],
            current_raw=current_raw,
            rpm=rpm,
            error=raw[8],
            crc=raw[9],
        )
