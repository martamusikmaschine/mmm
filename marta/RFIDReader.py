from serial import Serial
from threading import Thread, Event
from logging import getLogger

debug = getLogger('RFIDReader').debug


#  RDM6300 RFID tag data structure
#
# | 00 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 1A | 1B | 1C |
# | 00 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 | 12 | 13 |
# |====|====|====|====|====|====|====|====|====|====|====|====|====|====|
# |    |                                                 |         |    |
# |    | <-------------------- DATA -------------------> |         |    |
# |    |                                                 |         |    |
# | 02 | VERSION | <----------- RFID TAG --------------> | CHCKSUM | 03 |
#
#    ^      ^                      ^                          ^       ^
#    |      |                      |                          |       |
#    |      |                      |                          |       +--> 1 byte tail is always 0x3
#    |      |                      |                          |
#    |      |                      |                          +--> 2 bytes checksum calculated by XORING the DATA bytes
#    |      |                      |
#    |      |                       +--> 8 bytes tag identifier
#    |      |
#    |      +--> 2 bytes version information
#    |
#    +--> 1 byte header is always 0x2

class RFIDReader(object):
    DEFAULT_BAUD_RATE = 9600

    DEFAULT_PORT = "/dev/ttyS0"

    DEFAULT_TIMEOUT = 0.5

    START_BYTE = "\x02"

    END_BYTE = "\x03"

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

            head = self._serial_conn.read()
            if len(head) == 0 and self._old_tag != "":
                self._on_detection(None)
                self._old_tag = ""

            elif head == RFIDReader.START_BYTE:

                # actually the tag data is divided into 2 bytes version + 8 bytes tag + 2 bytes checksum
                # I couldn't find out anything about the version differences, so I just ignored it.
                tag = self._serial_conn.read(12)

                tail = self._serial_conn.read()
                if tail == RFIDReader.END_BYTE and self._old_tag != tag:

                    # the checksum is calculated by XORing the version and tag bytes
                    calc_checksum = 0
                    for i in range(0, 10, 2):
                        calc_checksum ^= int(tag[i:i + 2], 16)

                    if calc_checksum == int(tag[10:12], 16):

                        # make sure, on_detection is always called alternating (tag, None, tag, None, tag, ...
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


################################################################

def main():
    from SetupLogging import setup_stdout_logging
    setup_stdout_logging()

    debug("place tags on the reader!")
    debug("ENTER or CTRL + C to quit")

    reader = RFIDReader(lambda tag: debug("tag: " + str(tag)))

    try:
        raw_input()
    except:
        pass

    reader.terminate()


if __name__ == "__main__":
    main()
