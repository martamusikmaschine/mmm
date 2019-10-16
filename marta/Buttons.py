from logging import getLogger
from monotonic import monotonic as mtime

import RPi.GPIO as GPIO

debug = getLogger('   Buttons').debug

POWER_BUTTON = 17
RUN_LED = 20

YELLOW_BUTTON = 5
BLUE_BUTTON = 6
RED_BUTTON = 13
GREEN_BUTTON = 26

COLOR_BUTTONS = [YELLOW_BUTTON, BLUE_BUTTON, RED_BUTTON, GREEN_BUTTON]

BUTTONS_HUMAN_READABLE = {
    YELLOW_BUTTON: "YELLOW",
    BLUE_BUTTON: "BLUE",
    RED_BUTTON: "RED",
    GREEN_BUTTON: "GREEN",
    POWER_BUTTON: "POWER"
}


def setup_gpio(button_callback):
    debug("setting up gpio")

    # GPIO 20 is already in use? By whom? I have no idea.
    GPIO.setwarnings(False)

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RUN_LED, GPIO.OUT)

    buttons_last_pushed_time = {
    }

    def edge_detected_on_pin(event_pin):
        # debug("button event: " + BUTTONS_HUMAN_READABLE[pin])
        event_pin_is_pushed = False if GPIO.input(event_pin) == 1 else True
        event_pin_was_already_pushed = buttons_last_pushed_time[event_pin] is not 0

        # debug("is: " + str(event_pin_is_pushed) + ", war: " + str(event_pin_was_already_pushed))

        if event_pin_is_pushed is event_pin_was_already_pushed:
            # debug("ignoring. no new state")
            return

        now = int(mtime() * 1000)

        if event_pin_is_pushed:
            # debug("now on")
            buttons_last_pushed_time[event_pin] = now
            return

        diff = now - buttons_last_pushed_time[event_pin]
        buttons_last_pushed_time[event_pin] = 0

        if diff < 50:
            return

        debug("push event on pin " + str(event_pin) + ": " + str(diff))
        button_callback(event_pin, diff)

    for pin in COLOR_BUTTONS + [POWER_BUTTON]:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(pin, GPIO.BOTH, callback=edge_detected_on_pin)
        buttons_last_pushed_time[pin] = 0


def set_status_led(value):
    GPIO.output(RUN_LED, value)


def is_pushed(pin):
    v = False if GPIO.input(pin) == 1 else True
    debug("pin " + str(pin) + ": " + str(v))
    return v


def terminate():
    debug("terminating")
    GPIO.cleanup()


################################################################

def main():
    from SetupLogging import setup_stdout_logging
    setup_stdout_logging()

    debug("push the buttons!")
    debug("ENTER or CTRL + C to quit")

    setup_gpio(lambda pin, millis: debug(BUTTONS_HUMAN_READABLE[pin] + ": " + str(millis) + " ms"))

    try:
        raw_input()
    except:
        pass

    terminate()


if __name__ == "__main__":
    main()
