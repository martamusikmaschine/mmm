from logging import getLogger
from os import listdir, environ, remove

import Buttons
from Util import sorted_aphanumeric
from LEDStrip import LEDStrip
from MartaHandler import MartaHandler
from TagToDir import TAG_TO_DIR, prepare, ALBUM_INDICATOR_FILE
from os.path import exists

debug = getLogger('MscHandler').debug

MARTA_BASE_DIR = environ["MARTA"]


class MusicHandler(MartaHandler):
    PITCHES = [55, 70, 85, 100, 115, 130, 145, 160, 175, 190]
    DEFAULT_PITCH = 100

    VOLUMES = [1, 2, 3, 5, 7, 9, 12, 15, 18, 22]
    DEFAULT_VOLUME = 1

    BRIGHTNESSES = [0, 28, 56, 84, 112, 140, 168, 196, 224, 255]
    DEFAULT_BRIGHTNESS = 255

    CONTROL_PITCH = 0
    CONTROL_VOLUME = 1
    CONTROL_BRIGHTNESS = 2

    SONG_DIR = MARTA_BASE_DIR + "/audio/"
    UNKNOWN_TAG_FILE = SONG_DIR + "/unknown_tag.txt"

    SONG_STATE_FILE = ".songstate"

    LONG_TIMEOUT = 20 * 60
    SHORT_TIMEOUT = 5 * 60

    LONG_CLICK_THRESHOLD = 1500

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
        self.current_song_dir = None
        self.current_tag = None
        self.expected_stop = False

        if exists(MusicHandler.UNKNOWN_TAG_FILE):
            debug("unknown tag file exists. removing")
            remove(MusicHandler.UNKNOWN_TAG_FILE)

        prepare(MusicHandler.SONG_DIR)

    def initialize(self):
        debug("init")
        return MusicHandler.SHORT_TIMEOUT

    def save_state_and_stop(self):
        self.marta.player.pause_track()

        debug("Saving state.")
        with open(self.current_song_dir + "/" + MusicHandler.SONG_STATE_FILE, 'w') as state_file:
            debug("writing to file: " + self.current_song_dir + "/" + MusicHandler.SONG_STATE_FILE)
            state_file.write(
                str(self.current_song_index) + "\n" + str(self.marta.player.get_position_in_millis()) + "\n")
        self.current_song_dir = None
        self.current_tag = None
        self.all_songs = None
        self.current_song_index = 0

        self.expected_stop = True
        self.marta.player.stop_track()

    def load_state(self, tag):
        debug("Loading state.")
        self.current_tag = tag
        self.current_song_dir = TAG_TO_DIR[self.current_tag][0]
        debug("tag name: " + self.current_song_dir)
        songs = sorted_aphanumeric(listdir(self.current_song_dir))

        current_pos = 0

        if ALBUM_INDICATOR_FILE in songs:
            songs.remove(ALBUM_INDICATOR_FILE)

        if MusicHandler.SONG_STATE_FILE in songs:
            songs.remove(MusicHandler.SONG_STATE_FILE)
            with open(self.current_song_dir + "/" + MusicHandler.SONG_STATE_FILE) as state_file:
                debug("reading from file: " + self.current_song_dir + "/" + MusicHandler.SONG_STATE_FILE)
                lines = state_file.readlines()
                lines = [line.strip() for line in lines]
                self.current_song_index = int(lines[0])
                debug("current song index: " + str(self.current_song_index))
                current_pos = long(lines[1])
                debug("current song position: " + str(current_pos))

        self.all_songs = [self.current_song_dir + "/" + song for song in songs]
        debug("all songs: " + str(self.all_songs))

        return current_pos

    def rfid_removed_event(self):
        debug("tag removed.")
        self.marta.leds.fade_up_and_down(LEDStrip.RED)
        self.save_state_and_stop()
        return MusicHandler.SHORT_TIMEOUT

    def rfid_music_tag_event(self, tag):
        current_position = self.load_state(tag)
        self.marta.player.load_track_from_file(self.all_songs[self.current_song_index])
        if current_position != 0:
            self.marta.player.set_position_in_millis(current_position)

        if len(self.all_songs) == 1:
            self.marta.leds.fade_up_and_down(LEDStrip.GREEN)
        else:
            self.marta.leds.song(self.current_song_index, len(self.all_songs))
        self.marta.player.play_track()
        return MusicHandler.LONG_TIMEOUT

    def rfid_tag_event(self, tag):
        debug("tag=%s", tag)

        if tag is None:
            if self.current_tag is None:
                debug("probably removed unknown tag")

                if exists(MusicHandler.UNKNOWN_TAG_FILE):
                    debug("unknown tag file exists. removing")
                    remove(MusicHandler.UNKNOWN_TAG_FILE)

                self.marta.leds.fade_up_and_down(LEDStrip.RED)
                return MusicHandler.SHORT_TIMEOUT

            return self.rfid_removed_event()

        if tag not in TAG_TO_DIR:
            self.current_song_dir = None
            debug("unknown tag")

            with open(MusicHandler.UNKNOWN_TAG_FILE, "w") as unknown_tag_file:
                debug("writing to unknown tag file")
                unknown_tag_file.write(tag)

            self.marta.leds.fade_up_and_down(LEDStrip.ORANGE)
            return MusicHandler.LONG_TIMEOUT

        return self.rfid_music_tag_event(tag)

    def rotation_event(self, x, y):
        debug("rotation event!")
        if x < -45:
            if self.currently_controlling == MusicHandler.CONTROL_BRIGHTNESS:
                return

            self.currently_controlling = MusicHandler.CONTROL_BRIGHTNESS
            self.marta.leds.fade_up_and_down(LEDStrip.PURPLE)
            debug("now controlling brightness")
            return

        if x > 45:
            if self.currently_controlling == MusicHandler.CONTROL_PITCH:
                return

            self.currently_controlling = MusicHandler.CONTROL_PITCH
            self.marta.leds.fade_up_and_down(LEDStrip.YELLOW)
            debug("now controlling pitch")
            return

        if self.currently_controlling == MusicHandler.CONTROL_VOLUME:
            return

        self.currently_controlling = MusicHandler.CONTROL_VOLUME
        self.marta.leds.fade_up_and_down(LEDStrip.BLUE)
        debug("now controlling volume")

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
        self.marta.player.load_track_from_file(self.all_songs[self.current_song_index])
        self.marta.player.play_track()

    def button_red_green_event(self, pin, millis):
        if self.currently_controlling == MusicHandler.CONTROL_VOLUME:
            debug("change volume")
            arr = MusicHandler.VOLUMES
            current = self.marta.player.get_volume()
        elif self.currently_controlling == MusicHandler.CONTROL_PITCH:
            debug("change pitch")
            arr = MusicHandler.PITCHES
            current = self.marta.player.get_pitch()
        else:
            debug("change brightness")
            arr = MusicHandler.BRIGHTNESSES
            current = self.marta.leds.get_brightness()

        debug("current value: " + str(current))

        current = arr.index(current)

        if pin == Buttons.RED_BUTTON:
            new = current + 1
        else:
            new = current - 1

        if new < 0 or new >= len(arr):
            debug("would be out of bounds")
            self.marta.leds.volume(current)
            return

        self.marta.leds.volume(new)

        new = arr[new]
        debug("new value: " + str(new))

        if self.currently_controlling == MusicHandler.CONTROL_VOLUME:
            self.marta.player.set_volume(new)
        elif self.currently_controlling == MusicHandler.CONTROL_PITCH:
            self.marta.player.set_pitch(new)
        else:
            self.marta.leds.set_brightness(new)

    def button_next_previous_album(self, pin):
        album_indicator = self.current_song_dir + "/" + ALBUM_INDICATOR_FILE
        if exists(album_indicator):
            debug("removing album indicator: " + album_indicator)
            remove(album_indicator)

        tag = self.current_tag

        off = 1 if pin == Buttons.YELLOW_BUTTON else -1
        TAG_TO_DIR[self.current_tag] = TAG_TO_DIR[self.current_tag][off:] + TAG_TO_DIR[self.current_tag][:off]
        debug("changed album order: " + self.current_tag + "=" + str(TAG_TO_DIR[self.current_tag]))

        self.rfid_removed_event()
        self.rfid_tag_event(tag)

        album_indicator = self.current_song_dir + "/" + ALBUM_INDICATOR_FILE
        open(album_indicator, 'w').close()

    def button_next_previous_song(self, pin):
        if pin == Buttons.BLUE_BUTTON:
            pos = self.marta.player.get_position_in_millis()
            debug("pos=" + str(pos))

            # if we are at the beginning of a song, skip to the beginning
            if pos > 2000:
                self.marta.player.set_position_in_millis(0)
                off = 0
            else:
                off = -1
        else:
            off = 1

        if off != 0:
            self.expected_stop = True
            self.marta.player.stop_track()
            self.current_song_index = (self.current_song_index + off) % len(self.all_songs)
            self.marta.player.load_track_from_file(self.all_songs[self.current_song_index])
            self.marta.player.play_track()

        if len(self.all_songs) == 1:
            self.marta.leds.fade_up_and_down(LEDStrip.GREEN)
            return

        self.marta.leds.song(self.current_song_index, len(self.all_songs), forward=pin == Buttons.YELLOW_BUTTON)

    def button_event(self, pin, millis):
        debug("pin: " + Buttons.BUTTONS_HUMAN_READABLE[pin])

        if pin == Buttons.YELLOW_BUTTON or pin == Buttons.BLUE_BUTTON:
            if self.current_tag is None:
                debug("no tag. ignore")
                return MusicHandler.SHORT_TIMEOUT

            if millis > MusicHandler.LONG_CLICK_THRESHOLD and len(TAG_TO_DIR[self.current_tag]) > 1:
                self.button_next_previous_album(pin)
            else:
                self.button_next_previous_song(pin)
        elif pin == Buttons.GREEN_BUTTON or pin == Buttons.RED_BUTTON:
            self.button_red_green_event(pin, millis)

        if self.current_tag is None:
            return MusicHandler.SHORT_TIMEOUT
        else:
            return MusicHandler.LONG_TIMEOUT

    def uninitialize(self):
        debug("uninitialize")
        if self.current_tag is not None:
            self.save_state_and_stop()
