from logging import getLogger

from LEDStrip import LEDStrip
from MartaHandler import MartaHandler
import Buttons

debug = getLogger('BtnLgtHdlr').debug


class ButtonLightHandler(MartaHandler):
    TIMEOUT = 60

    #################
    # SINGLETON

    instance = None

    @staticmethod
    def get_instance(marta):
        if ButtonLightHandler.instance is None:
            ButtonLightHandler.instance = ButtonLightHandler(marta)
        return ButtonLightHandler.instance

    #################

    def button_event(self, pin, millis):
        if pin == Buttons.BLUE_BUTTON:
            self.marta.leds.fade_up_and_down(LEDStrip.BLUE)
        elif pin == Buttons.RED_BUTTON:
            self.marta.leds.fade_up_and_down(LEDStrip.RED)
        elif pin == Buttons.GREEN_BUTTON:
            self.marta.leds.fade_up_and_down(LEDStrip.GREEN)
        elif pin == Buttons.YELLOW_BUTTON:
            self.marta.leds.fade_up_and_down(LEDStrip.YELLOW)

        return ButtonLightHandler.TIMEOUT

    def rfid_tag_event(self, tag):
        debug("tag: " + str(tag))
        if tag is None:
            return MartaHandler.EVENT_HANDLER_DONE

    def initialize(self):
        self.marta.leds.fade_up_and_down(LEDStrip.WHITE)
        debug("init!!!")
        return ButtonLightHandler.TIMEOUT

    def uninitialize(self):
        self.marta.leds.fade_up_and_down(LEDStrip.WHITE)
        debug("uninit!!!")
