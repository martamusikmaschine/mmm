from logging import getLogger
from math import atan2, degrees, sqrt
from time import sleep

import smbus
from threading import Thread, Event

# Power management registers
POWER_MANAGEMENT_1 = 0x6b
POWER_MANAGEMENT_2 = 0x6c

ADDRESS = 0x68

REVISION = 1  # 1 = Revision 2, 0 = Revision 1

SLEEP_BETWEEN_READS = 0.01
TOTAL_READS = 16
TIME_TO_READ = TOTAL_READS * (SLEEP_BETWEEN_READS + 0.00375)

REMOVE_READS = 5
REMAINING_READS = float(TOTAL_READS - (2 * REMOVE_READS))

debug = getLogger('       MPU').debug


class MPU(object):
    def __init__(self, period, threshold, rotation_receiver):

        self._stop_event = Event()
        self._old_x = 10000
        self._old_y = 10000

        self._period = period
        self._threshold = threshold
        self._rotation_receiver = rotation_receiver

        self._bus = smbus.SMBus(REVISION)
        self._bus.write_byte_data(ADDRESS, POWER_MANAGEMENT_1, 0)

        self._mpu_reader_thread = Thread(target=self._read_mpu)
        self._mpu_reader_thread.daemon = True
        self._mpu_reader_thread.start()

    def _read_mpu(self):
        while True:
            self._stop_event.wait(self._period - TIME_TO_READ)
            if self._stop_event.isSet():
                debug("stop event received!")
                break

            x, y = self.get_average_rotation()
            if x is None:
                debug("return value None -> stop")
                break

            if abs(x - self._old_x) > self._threshold or abs(y - self._old_y) > self._threshold:
                self._old_x = x
                self._old_y = y
                self._rotation_receiver(x, y)

    def _read_byte(self, adr):
        return self._bus.read_byte_data(ADDRESS, adr)

    def _read_word(self, adr):
        high = self._bus.read_byte_data(ADDRESS, adr)
        low = self._bus.read_byte_data(ADDRESS, adr + 1)
        val = (high << 8) + low
        return val

    def _read_word_2c(self, adr):
        val = self._read_word(adr)
        if val >= 0x8000:
            return -((65535 - val) + 1)
        else:
            return val

    @staticmethod
    def _dist(a, b):
        return sqrt((a * a) + (b * b))

    @staticmethod
    def _get_y_rotation(x, y, z):
        radians = atan2(x, MPU._dist(y, z))
        return -degrees(radians)

    @staticmethod
    def _get_x_rotation(x, y, z):
        radians = atan2(y, MPU._dist(x, z))
        return degrees(radians)

    def get_rotation(self):
        accel_xout = self._read_word_2c(0x3b)
        accel_yout = self._read_word_2c(0x3d)
        accel_zout = self._read_word_2c(0x3f)

        accel_xout_scaled = accel_xout / 16384.0
        accel_yout_scaled = accel_yout / 16384.0
        accel_zout_scaled = accel_zout / 16384.0

        x = MPU._get_x_rotation(accel_xout_scaled, accel_yout_scaled, accel_zout_scaled)
        y = MPU._get_y_rotation(accel_xout_scaled, accel_yout_scaled, accel_zout_scaled)
        return x, y

    def get_average_rotation(self):
        xs = []
        ys = []
        for i in range(TOTAL_READS):
            x, y = self.get_rotation()
            xs.append(x)
            ys.append(y)
            self._stop_event.wait(SLEEP_BETWEEN_READS)
            if self._stop_event.isSet():
                debug("terminated while reading average rotation")
                return None, None

        return sum(sorted(xs)[REMOVE_READS:-REMOVE_READS]) / REMAINING_READS, sum(
            sorted(ys)[REMOVE_READS:-REMOVE_READS]) / REMAINING_READS

    def terminate(self):
        debug("MPU terminating...")
        self._stop_event.set()

        debug("waiting for mpu thread.")
        self._mpu_reader_thread.join()
        self._mpu_reader_thread = None

        debug("ok, finished.")


################################################################

def main():
    from logging import getLogger, DEBUG, Formatter, StreamHandler
    from sys import stdout

    def print_rot(x, y):
        debug("rot=" + str(x) + ", " + str(y))

    log = getLogger('')
    log.setLevel(DEBUG)

    ch = StreamHandler(stdout)
    ch.setFormatter(Formatter("%(asctime)s.%(msecs)03d | %(name)s |    %(message)s", "%H:%M:%S"))
    log.addHandler(ch)

    mpu = MPU(0.5, 0, print_rot)

    try:
        sleep(1000)
    except KeyboardInterrupt:
        mpu.terminate()


if __name__ == "__main__":
    main()
