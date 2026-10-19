"""
Builds small .wpilog files for testing, following the WPILib DataLog format spec:
  header:  "WPILOG" + version (2 bytes) + extra header length (4 bytes) + extra header
  record:  1 length byte + entry id + payload size + timestamp + payload
"""

import struct


class LogWriter:
    def __init__(self):
        self.buf = bytearray(b"WPILOG" + struct.pack("<H", 0x0100) + struct.pack("<I", 0))
        self.next_entry = 1
        self.types = {}

    def _record(self, entry, timestamp_us, payload):
        # always use 4-byte entry, 4-byte size, 8-byte timestamp
        length_byte = 0x3 | (0x3 << 2) | (0x7 << 4)
        self.buf += bytes([length_byte])
        self.buf += struct.pack("<I", entry)
        self.buf += struct.pack("<I", len(payload))
        self.buf += struct.pack("<Q", timestamp_us)
        self.buf += payload

    @staticmethod
    def _string(text):
        data = text.encode("utf-8")
        return struct.pack("<I", len(data)) + data

    def start(self, name, entry_type, timestamp_s=0.0):
        entry = self.next_entry
        self.next_entry += 1
        self.types[name] = (entry, entry_type)
        payload = bytes([0]) + struct.pack("<I", entry) + self._string(name) + self._string(entry_type) + self._string("")
        self._record(0, int(timestamp_s * 1_000_000), payload)
        return entry

    def append(self, name, timestamp_s, value):
        entry, entry_type = self.types[name]
        if entry_type == "double":
            payload = struct.pack("<d", value)
        elif entry_type == "float":
            payload = struct.pack("<f", value)
        elif entry_type == "int64":
            payload = struct.pack("<q", value)
        elif entry_type == "boolean":
            payload = bytes([1 if value else 0])
        else:
            raise ValueError(entry_type)
        self._record(entry, int(round(timestamp_s * 1_000_000)), payload)

    def save(self, path):
        with open(path, "wb") as f:
            f.write(self.buf)
