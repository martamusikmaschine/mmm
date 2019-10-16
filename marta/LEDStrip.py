from Queue import Queue, Empty

from neopixel import *
from threading import Thread
from logging import getLogger

debug = getLogger('  LEDStrip').debug


class SleepInterruptedException(Exception):
    def __init__(self, message):
        super(SleepInterruptedException, self).__init__("")
        self.msg = message


class LEDStrip(object):
    _LED_COUNT = 28  # Number of LED pixels.
    _LED_PIN = 12  # GPIO pin connected to the pixels (18 uses PWM!).
    _LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
    _LED_DMA = 10  # DMA channel to use for generating signal (try 10)
    _LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
    _LED_INVERT = False  # True to invert the signal (when using NPN transistor level shift)
    _LED_CHANNEL = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
    _LED_STRIP = ws.WS2811_STRIP_GRB  # Strip type and colour ordering

    _EVENT_TERMINATE = 0
    _EVENT_RAINBOW_DEMO = 1
    _EVENT_VOLUME = 2
    _EVENT_FADE_UP_AND_DOWN = 3
    _EVENT_STARTUP = 4
    _EVENT_SHUTDOWN = 5
    _EVENT_SONG = 6
    _EVENT_CLEAR = 7

    _EVENTS_HUMAN_READABLE = ["TERMINATE", "RAINBOW_DEMO", "VOLUME", "FADE_UP_AND_DOWN", "STARTUP", "SHUTDOWN", "SONG",
                              "CLEAR"]

    RED = Color(255, 0, 0)
    GREEN = Color(0, 255, 0)
    BLUE = Color(0, 0, 255)
    YELLOW = Color(255, 255, 0)
    PURPLE = Color(255, 0, 255)
    WHITE = Color(255, 255, 255)
    ORANGE = Color(0xFF, 0x8C, 0x00)

    _LEDS = range(_LED_COUNT)
    _VOLUME_LEDS = _LEDS[4:14]
    _LEDS_FROM_MIDDLE = _LEDS[2:] + _LEDS[:2]
    _LEDS_SONG = _LEDS_FROM_MIDDLE[2:-2]

    # Color gradient from Green to Red
    _VOLUME_LED_COLORS = [0x00FF00, 0x1CE200, 0x38C600, 0x55AA00, 0x718D00, 0x8D7100, 0xAA5500, 0xC63800, 0xE21C00,
                          0xFF0000]

    def __init__(self):
        self._strip = Adafruit_NeoPixel(LEDStrip._LED_COUNT, LEDStrip._LED_PIN, LEDStrip._LED_FREQ_HZ,
                                        LEDStrip._LED_DMA, LEDStrip._LED_INVERT, LEDStrip._LED_BRIGHTNESS,
                                        LEDStrip._LED_CHANNEL, LEDStrip._LED_STRIP)
        self._strip.begin()
        self._message_queue = Queue()

        self._led_controller_thread = Thread(target=self._control_leds)
        self._led_controller_thread.daemon = True
        self._led_controller_thread.start()

    def _control_leds(self):
        msg = None
        while True:
            msg = self._message_queue.get(block=True, timeout=None) if msg is None else msg

            event = msg[0]

            debug("event: %s", LEDStrip._EVENTS_HUMAN_READABLE[event])

            if event == LEDStrip._EVENT_TERMINATE:
                break

            # # Ignore if others are waiting
            # if not self._message_queue.empty():
            #     debug("ignoring that one...")
            #     continue

            try:
                if event == LEDStrip._EVENT_RAINBOW_DEMO:
                    self._rainbow_cycle_animation()

                elif event == LEDStrip._EVENT_VOLUME:
                    self._volume_animation(msg[1])

                elif event == LEDStrip._EVENT_FADE_UP_AND_DOWN:
                    self._fade_animation(msg[1])

                elif event == LEDStrip._EVENT_STARTUP:
                    self._startup_animation()

                elif event == LEDStrip._EVENT_SHUTDOWN:
                    self._shutdown_animation()

                elif event == LEDStrip._EVENT_SONG:
                    self._song_animation(msg[1], msg[2], msg[3])

                elif event == LEDStrip._EVENT_CLEAR:
                    self._clear_all()

                msg = None

            except SleepInterruptedException as sie:
                msg = sie.msg

    def _sleep(self, timeout):
        try:
            raise SleepInterruptedException(self._message_queue.get(block=True, timeout=timeout))
        except Empty:
            pass

    def startup(self):
        self._message_queue.put([LEDStrip._EVENT_STARTUP])

    def shutdown(self):
        self._message_queue.put([LEDStrip._EVENT_SHUTDOWN])

    def rainbow_demo(self):
        self._message_queue.put([LEDStrip._EVENT_RAINBOW_DEMO])

    def volume(self, volume):
        self._message_queue.put([LEDStrip._EVENT_VOLUME, volume])

    def song(self, i, n, forward=True):
        self._message_queue.put([LEDStrip._EVENT_SONG, i, n, forward])

    def fade_up_and_down(self, color):
        self._message_queue.put([LEDStrip._EVENT_FADE_UP_AND_DOWN, color])

    def clear(self):
        self._message_queue.put([LEDStrip._EVENT_CLEAR])

    def _clear_all(self):
        for i in range(LEDStrip._LED_COUNT):
            self._strip.setPixelColor(i, 0)
        self._strip.show()

    def _fade_up(self, leds, colors):
        rgbs = []
        for color in colors:
            rgbs.append(((color >> 16) & 255, (color >> 8) & 255, color & 255))

        for c in range(11):
            for i in range(len(leds)):
                self._strip.setPixelColor(leds[i], Color(int(round(rgbs[i][0] * 0.1 * c)),
                                                         int(round(rgbs[i][1] * 0.1 * c)),
                                                         int(round(rgbs[i][2] * 0.1 * c))))
            self._strip.show()
            self._sleep(0.05)

    def _fade_down(self, leds):
        initial_rgbs = []
        for led in leds:
            color = self._strip.getPixelColor(led)
            initial_rgbs.append(((color >> 16) & 255, (color >> 8) & 255, color & 255))

        for c in range(-9, 1):
            for i in range(len(leds)):
                self._strip.setPixelColor(leds[i], Color(int(round(initial_rgbs[i][0] * -0.1 * c)),
                                                         int(round(initial_rgbs[i][1] * -0.1 * c)),
                                                         int(round(initial_rgbs[i][2] * -0.1 * c))))
            self._strip.show()
            self._sleep(0.05)

    def _fade_up_and_down(self, leds, colors):
        self._fade_up(leds, colors)
        self._sleep(0.5)
        self._fade_down(leds)

    def _walk_around(self, leds, color, timeout=0.03):
        color_is_fun = callable(color)
        for i in leds:
            self._strip.setPixelColor(i, color(i) if color_is_fun else color)
            self._strip.show()
            self._sleep(timeout)

    @staticmethod
    def _rainbow_wheel(pos):
        return LEDStrip._wheel((int(pos * 256 / LEDStrip._LED_COUNT)) & 255)

    def _startup_animation(self):
        debug("startup animation")
        for c in [LEDStrip.GREEN, LEDStrip._rainbow_wheel, Color(0, 0, 0)]:
            self._walk_around(LEDStrip._LEDS_FROM_MIDDLE, c)

    def _shutdown_animation(self):
        debug("shutdown animation")
        for c in [LEDStrip._rainbow_wheel, LEDStrip.RED, Color(0, 0, 0)]:
            self._walk_around(LEDStrip._LEDS_FROM_MIDDLE, c)

    def _volume_animation(self, volume):
        debug("animating volume " + str(volume))
        self._clear_all()

        self._fade_up_and_down(LEDStrip._VOLUME_LEDS[0:volume + 1], LEDStrip._VOLUME_LED_COLORS)

    def _fade_animation(self, color):
        debug("fading " + str(color))
        self._clear_all()
        self._fade_up_and_down(LEDStrip._LEDS, [color] * LEDStrip._LED_COUNT)

    def _song_animation(self, i, n, forward):
        debug("song " + str(i) + " " + str(n))

        walk = LEDStrip._LEDS_SONG[2:2 + i] if forward else list(reversed(LEDStrip._LEDS_SONG[3 + i: 2 + n]))

        debug("walk=" + str(walk))

        self._clear_all()
        self._fade_up(LEDStrip._LEDS_SONG[:2] + LEDStrip._LEDS_SONG[2 + n: 4 + n],
                      [LEDStrip.GREEN] * 2 + [LEDStrip.RED] * 2)
        self._walk_around(walk, LEDStrip.YELLOW)
        self._fade_up(LEDStrip._LEDS_SONG[i + 2: i + 3], [LEDStrip.BLUE])
        self._walk_around(list(reversed(walk)), Color(0, 0, 0))
        self._sleep(1)
        self._fade_down(LEDStrip._LEDS_SONG[:2] + LEDStrip._LEDS_SONG[i + 2: i + 3] + LEDStrip._LEDS_SONG[2 + n: 4 + n])

    @staticmethod
    def _wheel(pos):
        if pos < 85:
            return Color(pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return Color(255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return Color(0, pos * 3, 255 - pos * 3)

    def set_brightness(self, brightness):
        self._strip.setBrightness(brightness)

    def get_brightness(self):
        return self._strip.getBrightness()

    def _rainbow_cycle_animation(self):
        while True:
            for j in range(256):
                for i in range(LEDStrip._LED_COUNT):
                    self._strip.setPixelColor(i, LEDStrip._wheel((int(i * 256 / LEDStrip._LED_COUNT) + j) & 255))
                    self._strip.show()

                self._sleep(0.02)

    def terminate(self):
        debug("led strip terminating.")
        if self._led_controller_thread is None:
            debug("already terminated")
            return

        self._message_queue.put([LEDStrip._EVENT_TERMINATE])
        self._led_controller_thread.join()

        for i in range(LEDStrip._LED_COUNT):
            self._strip.setPixelColor(i, 0)
        self._strip.show()

        self._led_controller_thread = None


################################################################

def main():
    from SetupLogging import setup_stdout_logging
    setup_stdout_logging()

    debug("see the beautiful lights")
    debug("ENTER or CTRL + C to quit")

    leds = LEDStrip()
    leds.rainbow_demo()

    try:
        raw_input()
    except:
        pass

    leds.terminate()


if __name__ == "__main__":
    main()
