# system
from logging import handlers, getLogger, DEBUG, Formatter, StreamHandler
from sys import stdout, argv
from Queue import Queue, Empty
from time import sleep, strftime
from signal import signal, SIGINT
from subprocess import call
from monotonic import monotonic as mtime
import traceback

import Buttons
from MartaHandler import MartaHandler
from LEDStrip import LEDStrip
from MPG123 import MPG123Player
from MPU import MPU
from RFIDReader import RFIDReader
from TagToHandler import TAG_TO_HANDLER

LOG_FILE = "/home/pi/logs/m3.log"

debug = getLogger('     Marta').debug


class Marta(object):
    ################
    # EVENTS
    EVENT_SONG_STOPPED = 0
    EVENT_RFID_TAG = 1
    EVENT_BUTTON = 2
    EVENT_MPG123_ERROR = 3
    EVENT_ROTATION = 4
    EVENT_INTERRUPT = 5

    EVENT_HUMAN_READABLE = [
        "EVENT_SONG_STOPPED",
        "EVENT_TAG",
        "EVENT_BUTTON",
        "EVENT_MPG123_ERROR",
        "EVENT_ROTATION",
        "EVENT_INTERRUPT"
    ]

    ################
    # SPECIAL TAGS

    INTERRUPT_TAG = "5A008360DC65"

    ################
    # AUDIO

    AUDIO_DIR = "/home/pi/audio/"
    SYSTEM_AUDIO_DIR = AUDIO_DIR + "system/"
    START_SOUND_PATH = SYSTEM_AUDIO_DIR + "xp_start.mp3"
    SHUTDOWN_SOUND_PATH = SYSTEM_AUDIO_DIR + "xp_shutdown.mp3"
    SYSTEM_SOUND_VOLUME = 2

    ################
    # FILES

    SHUTDOWN_SCRIPT = "/home/pi/shutdown_in.sh"

    def __init__(self):
        self.__message_queue = Queue()
        Buttons.setup_gpio(lambda pin: self.__message_queue.put([Marta.EVENT_BUTTON, pin]))

        if Buttons.is_pushed(Buttons.POWER_BUTTON) and Buttons.is_pushed(Buttons.RED_BUTTON):
            Buttons.terminate()
            debug("Early user interrupt!")
            exit(1)

        self.player = MPG123Player(lambda: self.__message_queue.put([Marta.EVENT_SONG_STOPPED]),
                                   lambda: self.__message_queue.put([Marta.EVENT_MPG123_ERROR]),
                                   volume=Marta.SYSTEM_SOUND_VOLUME)

        self.leds = LEDStrip()

        self.player.load_track_from_file(Marta.START_SOUND_PATH)
        self.leds.startup()
        self.player.play_track()

        # hacky because MPG123Player is async
        while not self.player.is_track_playing():
            sleep(0.05)

        # True = GPIO.HIGH = 1
        # False = GPIO.LOW = 0
        g = True
        while self.player.is_track_playing():
            Buttons.set_status_led(g)
            sleep(0.2)
            g = not g

        Buttons.set_status_led(0)

        # Empty q after short period of time (player stop event and button pushes)
        sleep(0.1)
        while not self.__message_queue.empty():
            self.__message_queue.get(block=False)

        self.mpu = MPU(period=1, threshold=5,
                       rotation_receiver=lambda x, y: self.__message_queue.put([Marta.EVENT_ROTATION, x, y]))

        self.rfid_reader = RFIDReader(lambda tag: self.__message_queue.put([Marta.EVENT_RFID_TAG, tag]))

    def interrupt(self):
        self.__message_queue.put([Marta.EVENT_INTERRUPT])

    def message_loop(self):

        current_handler = TAG_TO_HANDLER["default"].get_instance(self)
        max_mono_time = mtime() + current_handler.initialize()

        while True:
            now = mtime()
            debug("now = " + str(now))

            if now >= max_mono_time:
                debug("timeout occured.")
                break

            timeout = max_mono_time - now
            debug("waiting for " + str(timeout))
            try:
                msg = self.__message_queue.get(block=True, timeout=timeout)
            except Empty:
                # If a time change (due to network time) occurs while waiting for an event,
                # Queue.get will return Empty early:

                # 14:46:31.368 | main | now = 54.502526
                # 14:46:31.380 | main | waiting for 299.955775
                # -- NOW THE TIME CHANGE OCCURS --
                # 19:29:13.403 | main | timeout @ 67.323505
                # 19:29:13.410 | main | Terminating!

                # Instead of breaking here, we just continue, because we have another check on top of this function
                #  which checks the timeout again but using a monotonic timer
                debug("possible timeout @ " + str(mtime()))
                continue

            event = msg[0]
            params = msg[1:]

            if event == Marta.EVENT_INTERRUPT:
                debug("Critical: Interrupt event!")
                break

            elif event == Marta.EVENT_MPG123_ERROR:
                debug("Critical: MPG123 error event!")
                break

            elif event == Marta.EVENT_BUTTON and params[0] == Buttons.POWER_BUTTON:
                debug("Critical: Power button event!")
                break

            elif event == Marta.EVENT_RFID_TAG:
                tag = params[0]
                if tag == Marta.INTERRUPT_TAG:
                    debug("Critical: Interrupt tag event!")
                    break
                elif tag in TAG_TO_HANDLER:
                    current_handler.uninitialize()
                    current_handler = TAG_TO_HANDLER[tag].get_instance(self)
                    current_handler.initialize()

            debug(Marta.EVENT_HUMAN_READABLE[event] + ": " + str(params))
            if event == Marta.EVENT_ROTATION:
                return_val = current_handler.rotation_event(params[0], params[1])
            elif event == Marta.EVENT_SONG_STOPPED:
                return_val = current_handler.player_stop_event()
            elif event == Marta.EVENT_RFID_TAG:
                return_val = current_handler.rfid_tag_event(params[0])
            elif event == Marta.EVENT_BUTTON:
                return_val = current_handler.button_event(params[0])
            else:
                raise Exception("Unknown event: " + str(event))

            if return_val is None:
                debug("Don't change the timeout.")
            else:
                if return_val == MartaHandler.EVENT_HANDLER_DONE:
                    debug("This event handler is done.")
                    current_handler.uninitialize()
                    current_handler = TAG_TO_HANDLER["default"].get_instance(self)
                    return_val = current_handler.initialize()
                max_mono_time = mtime() + return_val

        current_handler.uninitialize()

    def terminate(self):
        debug("Terminating!")

        try:
            self.player.set_volume(Marta.SYSTEM_SOUND_VOLUME)
            self.player.set_pitch(100)
            self.player.load_track_from_file(Marta.SHUTDOWN_SOUND_PATH)
            self.player.play_track()
        except:
            pass

        try:
            self.leds.shutdown()
        except:
            pass

        try:
            for i in range(20):
                Buttons.set_status_led(i % 2)
                sleep(0.2)
        except:
            pass

        try:
            self.mpu.terminate()
        except:
            pass

        try:
            self.player.terminate()
        except:
            pass

        try:
            self.rfid_reader.terminate()
        except:
            pass

        try:
            self.leds.terminate()
        except:
            pass

        try:
            for i in range(10):
                Buttons.set_status_led(i % 2)
                sleep(0.2)
        except:
            pass

        try:
            Buttons.terminate()
        except:
            pass


def main():
    logger = getLogger('')
    logger.setLevel(DEBUG)
    formatter = Formatter("%(asctime)s.%(msecs)03d | %(name)s |    %(message)s", "%H:%M:%S")

    if "log2stdout" in argv:
        ch = StreamHandler(stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    fh = handlers.RotatingFileHandler(LOG_FILE, maxBytes=(1024 * 1024 * 10), backupCount=10)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    debug("#################################################")
    debug("#                  INITIALIZED                  #")
    debug("#              " + strftime("%Y-%m-%d %H:%M:%S") + "              #")
    debug("#################################################")

    marta = Marta()
    signal(SIGINT, lambda s, f: marta.interrupt())

    try:
        marta.message_loop()
    except Exception as e:
        debug("Exception: " + str(e))
        debug(traceback.format_exc())

    marta.terminate()

    if "noshutdown" not in argv:
        debug("Shutting down in 1!")
        call(["sh", Marta.SHUTDOWN_SCRIPT, "1"])

    debug("exiting")
    exit(0)


if __name__ == "__main__":
    main()
