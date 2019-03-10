from logging import getLogger
from os import listdir

import Buttons
from LEDStrip import LEDStrip
from MartaHandler import MartaHandler
from TagToAudio import TAG_TO_AUDIO

debug = getLogger('MscHandler').debug


class MusicHandler(MartaHandler):
    PITCHES = [55, 70, 85, 100, 115, 130, 145, 160, 175, 190]
    DEFAULT_PITCH = 100

    VOLUMES = [1, 2, 3, 5, 7, 9, 12, 15, 18, 22]
    DEFAULT_VOLUME = 1

    CONTROL_PITCH = 0
    CONTROL_VOLUME = 1

    SONG_DIR = "/home/pi/audio/songs/"
    STATE_FILE = "music_state.txt"

    LONG_TIMEOUT = 20 * 60
    SHORT_TIMEOUT = 5 * 60

    #################
    # SINGLETON
    instance = None

    @staticmethod
    def get_instance(marta):
        if MusicHandler.instance is None:
            MusicHandler.instance = MusicHandler(marta)
        return MusicHandler.instance

    #################

    def __init__(self, marta):
        super(MusicHandler, self).__init__(marta)
        self.currently_controlling = MusicHandler.CONTROL_VOLUME
        self.all_songs = None
        self.current_song_index = 0
        self.current_tag_name = None
        self.expected_stop = False

    def initialize(self):
        debug("init")
        return MusicHandler.SHORT_TIMEOUT

    def save_state(self, song_position):
        debug("Saving state.")
        with open(MusicHandler.SONG_DIR + self.current_tag_name + "/" + MusicHandler.STATE_FILE,
                  'w') as state_file:
            state_file.write(str(self.current_song_index) + "\n" + str(song_position) + "\n")
        self.current_tag_name = None
        self.all_songs = None
        self.current_song_index = 0

    def load_state(self, tag):
        debug("Loading state.")
        self.current_tag_name = TAG_TO_AUDIO[tag]
        debug("tag name: " + self.current_tag_name)
        songs = sorted(listdir(MusicHandler.SONG_DIR + self.current_tag_name))

        current_pos = 0

        try:
            songs.remove(MusicHandler.STATE_FILE)
            with open(
                    MusicHandler.SONG_DIR + self.current_tag_name + "/" + MusicHandler.STATE_FILE) as state_file:
                lines = state_file.readlines()
                lines = [line.strip() for line in lines]
                self.current_song_index = int(lines[0])
                debug("current song index: " + str(self.current_song_index))
                current_pos = long(lines[1])
                debug("current song position: " + str(current_pos))
        except ValueError:
            pass

        self.all_songs = [MusicHandler.SONG_DIR + self.current_tag_name + "/" + song for song in songs]
        debug("all songs: " + str(self.all_songs))

        return current_pos

    def rfid_tag_event(self, tag):
        debug("tag=%s", tag)
        if tag is None:
            debug("tag removed.")
            self.marta.player.pause()
            self.marta.leds.fade_up_and_down(LEDStrip.RED)
            self.save_state(self.marta.player.get_position())
            self.expected_stop = True
            self.marta.player.stop()
            return MusicHandler.SHORT_TIMEOUT
        else:
            current_position = self.load_state(tag)
            self.marta.player.load(self.all_songs[self.current_song_index])
            if current_position != 0:
                self.marta.player.set_position(current_position)

            if len(self.all_songs) == 1:
                self.marta.leds.fade_up_and_down(LEDStrip.GREEN)
            else:
                self.marta.leds.song(self.current_song_index, len(self.all_songs))
            self.marta.player.play()
            return MusicHandler.LONG_TIMEOUT

    def rotation_event(self, x, y):
        debug("rotation event!")
        if self.currently_controlling == MusicHandler.CONTROL_VOLUME:
            if x > 45:
                self.currently_controlling = MusicHandler.CONTROL_PITCH
                self.marta.leds.fade_up_and_down(LEDStrip.YELLOW)
                debug("Now controlling pitch.")
        else:
            if x <= 45:
                self.currently_controlling = MusicHandler.CONTROL_VOLUME
                self.marta.leds.fade_up_and_down(LEDStrip.BLUE)
                debug("Now controlling volume.")

    def player_stop_event(self):
        if self.expected_stop:
            self.expected_stop = False
            debug("ignoring this event because stopping is expected")
            return

        self.current_song_index = (self.current_song_index + 1) % len(self.all_songs)
        if len(self.all_songs) == 1:
            self.marta.leds.fade_up_and_down(LEDStrip.GREEN)
        else:
            self.marta.leds.song(self.current_song_index, len(self.all_songs))
        self.marta.player.load(self.all_songs[self.current_song_index])
        self.marta.player.play()

    def button_event(self, pin):
        debug("pin: " + Buttons.BUTTONS_HUMAN_READABLE[str(pin)])

        if pin == Buttons.BLUE_BUTTON:
            if not self.marta.player.is_playing():
                debug("ignore")
                return

            pos = self.marta.player.get_position()
            debug("pos=" + str(pos))
            if pos > 2000:
                self.marta.player.set_position(0)
            else:
                self.expected_stop = True
                self.marta.player.stop()
                self.current_song_index = (self.current_song_index - 1) % len(self.all_songs)
                self.marta.player.load(self.all_songs[self.current_song_index])
                self.marta.player.play()

            if len(self.all_songs) == 1:
                self.marta.leds.fade_up_and_down(LEDStrip.GREEN)
            else:
                self.marta.leds.song(self.current_song_index, len(self.all_songs), forward=False)

        elif pin == Buttons.YELLOW_BUTTON:
            if not self.marta.player.is_playing():
                debug("player is not playing. so ignore")
                return

            self.expected_stop = True
            self.marta.player.stop()
            self.current_song_index = (self.current_song_index + 1) % len(self.all_songs)
            self.marta.player.load(self.all_songs[self.current_song_index])
            self.marta.player.play()

            if len(self.all_songs) == 1:
                self.marta.leds.fade_up_and_down(LEDStrip.GREEN)
            else:
                self.marta.leds.song(self.current_song_index, len(self.all_songs))

        elif pin == Buttons.GREEN_BUTTON or pin == Buttons.RED_BUTTON:
            arr = MusicHandler.VOLUMES if self.currently_controlling == MusicHandler.CONTROL_VOLUME else MusicHandler.PITCHES
            current = self.marta.player.get_volume() if self.currently_controlling == MusicHandler.CONTROL_VOLUME else self.marta.player.get_pitch()
            current = arr.index(current)
            new = current + (1 if pin == Buttons.RED_BUTTON else -1)

            if new < 0 or new >= len(arr):
                debug("would be out of bounds.")
            else:
                if self.currently_controlling == MusicHandler.CONTROL_VOLUME:
                    debug("new volume: " + str(arr[new]))
                    self.marta.player.set_volume(arr[new])
                else:
                    debug("new pitch: " + str(arr[new]))
                    self.marta.player.set_pitch(arr[new])
                current = new

            self.marta.leds.volume(current)

        if self.current_tag_name is None:
            return MusicHandler.SHORT_TIMEOUT
        else:
            return MusicHandler.LONG_TIMEOUT

    def uninitialize(self):
        debug("uninitialize")
        if self.current_tag_name is not None:
            self.marta.player.pause()
            self.save_state(self.marta.player.get_position())
            self.marta.player.stop()
