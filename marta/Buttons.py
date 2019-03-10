from logging import getLogger

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
    str(YELLOW_BUTTON): "YELLOW",
    str(BLUE_BUTTON): "BLUE",
    str(RED_BUTTON): "RED",
    str(GREEN_BUTTON): "GREEN",
    str(POWER_BUTTON): "POWER",
}


def setup_gpio(button_callback):
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RUN_LED, GPIO.OUT)

    for pin in COLOR_BUTTONS + [POWER_BUTTON]:
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(pin, GPIO.RISING, callback=button_callback, bouncetime=200)


def set_status_led(value):
    GPIO.output(RUN_LED, value)


def is_pushed(pin):
    v = False if GPIO.input(pin) == 1 else True
    debug("pin " + str(pin) + ": " + str(v))
    return v


def terminate():
    GPIO.cleanup()
