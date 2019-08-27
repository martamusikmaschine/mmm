from subprocess import Popen, PIPE, STDOUT
import select
from threading import Thread, Event
from logging import getLogger

debug = getLogger('    MPG123').debug


class MPG123Player(object):
    STATE_STOPPED = 0
    STATE_PAUSED = 1
    STATE_PLAYING = 2
    STATE_TERMINATED = 3

    # The first interaction with mpg123 takes really long, so this constant will not be considered
    # but all subsequent commands will not take longer than this time
    _DEFAULT_IPC_TIMEOUT_IN_SECONDS = 1

    _DEFAULT_VOLUME = 50
    _DEFAULT_PITCH = 100
    _MPG123_BINARY = "mpg123"

    def __init__(self, on_stop_callback, on_error_callback, volume=_DEFAULT_VOLUME, pitch=_DEFAULT_PITCH):
        self._ipc_timeout = 10
        self._current_state = MPG123Player.STATE_STOPPED
        self._program_responded = Event()

        self._track_length_in_samples = 0
        self._track_position_in_samples = 0
        self._track_length_in_millis = 0

        self._volume = None
        self._actual_program_pitch = MPG123Player._DEFAULT_PITCH
        self._pitch = MPG123Player._DEFAULT_PITCH

        self._current_file = None

        self._on_stop_callback = on_stop_callback
        self._on_error_callback = on_error_callback
        self._mpg123_process = Popen([MPG123Player._MPG123_BINARY, "--remote"], stdin=PIPE, stdout=PIPE, stderr=STDOUT)

        self._read_sout_thread = Thread(target=self._read_sout)
        self._read_sout_thread.daemon = True
        self._read_sout_thread.start()
        self._was_error = False

        # this prevents mpg123 from spamming the stdout with positional information
        self._command('SILENCE')
        self._ipc_timeout = MPG123Player._DEFAULT_IPC_TIMEOUT_IN_SECONDS

        self.set_volume(volume)
        self.set_pitch(pitch)
        debug("mpg123 initialized")

    def _mpg123_input(self, line):
        debug("< " + str(line))

        if line.startswith('@R MPG123'):
            debug("mpg123 startup")
            self._program_responded.set()
            return

        if line.startswith('@E '):
            self._was_error = True
            self._program_responded.set()
            return

        if line.startswith('@P 0'):
            self._current_state = MPG123Player.STATE_STOPPED
            self._program_responded.set()
            self._current_file = None
            self._on_stop_callback()
            debug("state=STOPPED")
            return

        if line.startswith('@P 1'):
            self._current_state = MPG123Player.STATE_PAUSED
            debug("state=PAUSED")
            self._program_responded.set()
            return

        if line.startswith('@P 2'):
            self._current_state = MPG123Player.STATE_PLAYING
            debug("state=PLAYING")
            self._program_responded.set()
            return

        if line.startswith('@SAMPLE '):
            line = line[8:-1]
            line = line.split(' ')
            self._track_position_in_samples = int(line[0])
            debug("current position: %d", self._track_position_in_samples)
            self._track_length_in_samples = int(line[1])
            self._program_responded.set()
            return

        if line.startswith('@S '):
            self._expecting_input = False
            sample_rate = int(line.split(" ")[3]) / float(1000)
            self._track_length_in_millis = int(round(self._track_length_in_samples / sample_rate))
            debug("track length: %d", self._track_length_in_millis)
            self._program_responded.set()
            return

        if line.startswith('@K '):
            self._program_responded.set()
            return

        if line.startswith('@V '):
            line = line[3:-1]
            line = line.split('%')[0]
            self._volume = float(line)
            debug("volume: %f", self._volume)
            self._program_responded.set()
            return

        if line.startswith('@PITCH '):
            line = line.split(' ')[1]
            self._actual_program_pitch = round((float(line) + 1) * 100)
            debug("pitch: %f", self._actual_program_pitch)
            self._program_responded.set()
            return

    def _read_sout(self):
        mpg123_stdout_poll = select.poll()
        mpg123_stdout_poll.register(self._mpg123_process.stdout, select.POLLIN)

        while True:
            mpg123_stdout_poll.poll()

            if self._mpg123_process.poll() is not None:
                break

            line = self._mpg123_process.stdout.readline()
            self._mpg123_input(line)

        debug("mpg123 died")
        mpg123_stdout_poll.unregister(self._mpg123_process.stdout)

        if self._on_error_callback is not None:
            self._on_error_callback()

        self._program_responded.set()

    def _command(self, command):
        self._program_responded.clear()
        debug("> " + str(command))
        self._mpg123_process.stdin.write(command + '\n')
        self._mpg123_process.stdin.flush()

        debug("waiting for max " + str(self._ipc_timeout) + " seconds")
        self._program_responded.wait(self._ipc_timeout)
        if not self._program_responded.isSet():
            raise Exception("timeout: " + str(self._ipc_timeout) + " sec")

        if self._was_error:
            self._was_error = False
            return False

        return True

    def is_track_playing(self):
        return self._current_state == MPG123Player.STATE_PLAYING

    def get_volume(self):
        return self._volume

    def set_volume(self, volume):
        if volume < 0:
            raise ValueError("Out of bounds!")
        elif volume > 100:
            raise ValueError("Out of bounds!")

        if volume == self._volume:
            debug("volume already set")
            return

        self._command('V ' + str(volume))

    def get_pitch(self):
        return self._pitch

    def set_pitch(self, pitch):
        if pitch < 50:
            raise ValueError("Out of bounds!")
        elif pitch > 200:
            raise ValueError("Out of bounds!")

        self._pitch = pitch

        if not (self._current_state == MPG123Player.STATE_PLAYING or self._current_state == MPG123Player.STATE_PAUSED):
            return

        pitch = float(pitch) / 100 - 1
        pitch = str(pitch)[0:8]

        self._command('PITCH ' + pitch)

    def _get_position_in_samples(self):
        self._command('SAMPLE')
        return self._track_position_in_samples, self._track_length_in_samples

    def get_position_in_millis(self):
        current_pos, length = self._get_position_in_samples()
        return int(round((float(current_pos) / length) * self._track_length_in_millis))

    def set_position_in_millis(self, position_in_millis):
        position_in_millis /= float(self._track_length_in_millis)
        position_in_millis = int(round(position_in_millis * self._track_length_in_samples))
        self._command('K ' + str(position_in_millis))

    def get_track_length_in_millis(self):
        return self._track_length_in_millis

    def load_track_from_file(self, file_name):
        if file_name == self._current_file:
            debug("file already loaded")
            return

        self._current_file = file_name
        okay = self._command('LP ' + file_name)
        if not okay:
            return False

        self._get_position_in_samples()
        # Forcing '@S ...' output in order to get the track's length in ms

        volume_before = self._volume
        self.set_volume(0)
        self.play_track()
        self.pause_track()
        self.set_volume(volume_before)

        self.set_position_in_millis(0)

        if self._pitch != self._actual_program_pitch:
            self.set_pitch(self._pitch)

        return True

    def toggle(self):
        self._command('P')

    def play_track(self):
        if self._current_state == MPG123Player.STATE_PLAYING:
            debug("already playing")
            return

        self.toggle()

    def pause_track(self):
        if self._current_state == MPG123Player.STATE_PAUSED:
            debug("already paused")
            return

        self.toggle()

    def stop_track(self):
        if self._current_state == MPG123Player.STATE_STOPPED:
            debug("already stopped")
            return

        self._command('S')

    def terminate(self):
        debug("MPG123 terminating...")
        if self._current_state == MPG123Player.STATE_TERMINATED:
            debug("mpg123 already terminated")
            return

        self._on_error_callback = None
        self._current_state = MPG123Player.STATE_TERMINATED
        if self._mpg123_process.returncode is None:
            # This strange construct is half of a historical artifact from python 3
            # and can probably be destroyed and hopefully be forgotten.
            # On the other hand: I don't know what happens then and at this point I'm too afraid to ask (or test).
            try:
                self._command('Q')
                self._mpg123_process.wait()
            except:
                try:
                    self._mpg123_process.terminate()
                    self._mpg123_process.wait()
                except:
                    pass

        debug("waiting for checker thread.")
        self._read_sout_thread.join()
        self._read_sout_thread = None

        debug("ok, finished.")

        return self._mpg123_process.returncode


def main():
    from logging import DEBUG, Formatter, StreamHandler
    from sys import stdout
    from time import sleep

    logger = getLogger('')
    logger.setLevel(DEBUG)
    formatter = Formatter("%(asctime)s.%(msecs)03d | %(name)s |    %(message)s", "%H:%M:%S")
    stdout_handler = StreamHandler(stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    def on_stop():
        debug("callback: song stopped")

    def on_error():
        debug("callback: error :-(")

    player = MPG123Player(on_stop, on_error, 50)

    mp3_path = raw_input("enter mp3 path: ")

    success = player.load_track_from_file(mp3_path)

    if not success:
        debug("file could not be loaded")
        return

    player.play_track()

    try:
        while True:
            sleep(.5)
            debug("position: " + str(player.get_position_in_millis()) + " ms")
    except KeyboardInterrupt:
        debug("keyboard interrupt")
        pass

    player.terminate()

    debug("good bye")


if __name__ == "__main__":
    main()
