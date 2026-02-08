# Module for FC interface

from pymavlink import mavutil

serial = "/dev/serial/by-id/usb-ArduPilot_MatekH743_390030000851333335323632-if00"
# serial = "/dev/serial/by-path/pci-0000\:05\:00.3-usb"
# serial = "/dev/serial0"

fc = mavutil.mavlink_connection(serial, baud=115200)
fc.wait_heartbeat()

print("CONNECTED")

while True:
    msg = fc.recv_match(type="ATTITUDE", blocking=True)
    print(f"roll={msg.roll:.2f} " f"pitch={msg.pitch:.2f} " f"yaw={msg.yaw:.2f}")
