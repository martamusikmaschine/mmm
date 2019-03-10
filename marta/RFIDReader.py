from serial import Serial
from threading import Thread, Event
from logging import getLogger

debug = getLogger('RFIDReader').debug


class RFIDReader(object):
    DEFAULT_BAUD_RATE = 9600

    DEFAULT_PORT = "/dev/ttyS0"

    DEFAULT_TIMEOUT = 0.5

    def __init__(self, on_detection, port=DEFAULT_PORT, baud_rate=DEFAULT_BAUD_RATE, timeout=DEFAULT_TIMEOUT):
        self._old_tag = ""
        self._stop_read_thread = Event()

        self._on_detection = on_detection
        self._serial_conn = Serial(port, baud_rate, timeout=timeout)

        self._read_rfid_thread = Thread(target=self._read_rfid)
        self._read_rfid_thread.daemon = True
        self._read_rfid_thread.start()

    def _read_rfid(self):

        while not self._stop_read_thread.isSet():

            start = self._serial_conn.read()
            if len(start) == 0 and self._old_tag != "":
                self._on_detection(None)
                self._old_tag = ""
            elif start == "\x02":
                tag = self._serial_conn.read(12)

                if self._old_tag != tag:
                    if self._old_tag != "":
                        self._on_detection(None)
                    self._on_detection(tag)
                    self._old_tag = tag

    def terminate(self):
        debug("rfid terminating.")
        if self._read_rfid_thread is None:
            debug("already terminated")
            return

        self._stop_read_thread.set()
        self._read_rfid_thread.join()

        self._serial_conn.close()
        self._read_rfid_thread = None
