from ButtonLightHandler import ButtonLightHandler
from MusicHandler import MusicHandler
from RainbowHandler import RainbowHandler

TAG_TO_HANDLER = {
    "5A00834F9204": ButtonLightHandler,
    "5500ACB96121": RainbowHandler,
    "default": MusicHandler
}
