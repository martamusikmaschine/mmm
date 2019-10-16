from logging import getLogger

from MartaHandler import MartaHandler

debug = getLogger('RnbwHndler').debug


class RainbowHandler(MartaHandler):
    TIMEOUT = 60

    #################
    # SINGLETON

    instance = None

    @staticmethod
    def get_instance(marta):
        if RainbowHandler.instance is None:
            RainbowHandler.instance = RainbowHandler(marta)
        return RainbowHandler.instance

    #################

    def rfid_tag_event(self, tag):
        debug("tag: " + str(tag))
        if tag is None:
            return MartaHandler.EVENT_HANDLER_DONE

    def initialize(self):
        debug("init!!!")
        self.marta.leds.rainbow_demo()
        return RainbowHandler.TIMEOUT

    def uninitialize(self):
        self.marta.leds.clear()
        debug("uninit!!!")
