from ButtonLightHandler import ButtonLightHandler
from MusicHandler import MusicHandler
from RainbowHandler import RainbowHandler

TAG_TO_HANDLER = {
    "5A0084EEF3C3": ButtonLightHandler,
    "5600C7AC4B76": RainbowHandler,
    "default": MusicHandler
}
