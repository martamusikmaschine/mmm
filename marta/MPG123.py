from subprocess import Popen, PIPE, STDOUT
import select
from threading import Thread, Event
from logging import getLogger

debug = getLogger('    MPG123').debug


class MPG123Player(object):
    STOPPED = 0
    PAUSED = 1
    PLAYING = 2
    TERMINATED = 3

    # THIS IS BAD!!!!! The first read takes endless. I don't know why.
    _MAX_WAIT_TIMEOUT_IN_S = 10

    _DEFAULT_VOLUME = 50
    _DEFAULT_PITCH = 100
    _MPG123_BINARY = "mpg123"

    def __init__(self, on_stop, on_error, volume=_DEFAULT_VOLUME, pitch=_DEFAULT_PITCH):
        self._current_state = MPG123Player.STOPPED
        self._something_changed = Event()
        self._length_in_samples = 0
        self._current_position = 0
        self._length_in_ms = 0
        self._volume = None
        self._actual_program_pitch = MPG123Player._DEFAULT_PITCH
        self._pitch = MPG123Player._DEFAULT_PITCH
        self._current_file = None

        self._on_stop = on_stop
        self._on_error = on_error
        self._mpg123_proc = Popen([MPG123Player._MPG123_BINARY, "--remote"], stdin=PIPE, stdout=PIPE, stderr=STDOUT)

        self._read_sout_thread = Thread(target=self.__read_sout)
        self._read_sout_thread.daemon = True
        self._read_sout_thread.start()

        self.command('SILENCE')
        self.set_volume(volume)
        self.set_pitch(pitch)

    def __mpg123_input(self, line):
        debug("< " + str(line))

        if line.startswith('@R MPG123'):
            self._something_changed.set()
            return

        if line.startswith('@P 0'):
            self._current_state = MPG123Player.STOPPED
            self._something_changed.set()
            self._current_file = None
            self._on_stop()
            debug("state=STOPPED")
            return

        if line.startswith('@P 1'):
            self._current_state = MPG123Player.PAUSED
            self._something_changed.set()
            debug("state=PAUSED")
            return

        if line.startswith('@P 2'):
            self._current_state = MPG123Player.PLAYING
            self._something_changed.set()
            debug("state=PLAYING")
            return

        if line.startswith('@SAMPLE '):
            line = line[8:-1]
            line = line.split(' ')
            self._current_position = int(line[0])
            self._length_in_samples = int(line[1])
            self._something_changed.set()
            return

        if line.startswith('@S '):
            self._expecting_input = False
            sample_rate = int(line.split(" ")[3]) / float(1000)
            self._length_in_ms = int(round(self._length_in_samples / sample_rate))
            self._something_changed.set()
            return

        if line.startswith('@K '):
            self._something_changed.set()
            return

        if line.startswith('@V '):
            line = line[3:-1]
            line = line.split('%')[0]
            self._volume = float(line)
            self._something_changed.set()
            return

        if line.startswith('@PITCH '):
            line = line.split(' ')[1]
            self._actual_program_pitch = round((float(line) + 1) * 100)
            self._something_changed.set()
            return

    def __read_sout(self):
        mpg123_stdout_poll = select.poll()
        mpg123_stdout_poll.register(self._mpg123_proc.stdout, select.POLLIN)

        while True:
            mpg123_stdout_poll.poll()

            if self._mpg123_proc.poll() is not None:
                break

            line = self._mpg123_proc.stdout.readline()
            self.__mpg123_input(line)

        debug("mpg123 died")
        mpg123_stdout_poll.unregister(self._mpg123_proc.stdout)

        if self._on_error is not None:
            self._on_error()

        self._something_changed.set()

    def command(self, command):
        self._something_changed.clear()
        debug("> " + str(command))
        self._mpg123_proc.stdin.write(command + '\n')
        self._mpg123_proc.stdin.flush()

        self._something_changed.wait(MPG123Player._MAX_WAIT_TIMEOUT_IN_S)
        if not self._something_changed.isSet():
            raise Exception("lol")

    def is_playing(self):
        return self._current_state == MPG123Player.PLAYING

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

        self.command('V ' + str(volume))

    def get_pitch(self):
        return self._pitch

    def set_pitch(self, pitch):
        if pitch < 50:
            raise ValueError("Out of bounds!")
        elif pitch > 200:
            raise ValueError("Out of bounds!")

        self._pitch = pitch

        if not (self._current_state == MPG123Player.PLAYING or self._current_state == MPG123Player.PAUSED):
            return

        pitch = float(pitch) / 100 - 1
        pitch = str(pitch)[0:8]

        self.command('PITCH ' + pitch)

    def _get_position_in_samples(self):
        self.command('SAMPLE')
        return self._current_position, self._length_in_samples

    def get_position(self):
        current_pos, length = self._get_position_in_samples()
        return int(round((float(current_pos) / length) * self._length_in_ms))

    def set_position(self, position):
        position /= float(self._length_in_ms)
        position = int(round(position * self._length_in_samples))
        self.command('K ' + str(position))

    def get_length(self):
        return self._length_in_ms

    def load(self, file_name):
        if file_name == self._current_file:
            debug("file already loaded")
            return

        self._current_file = file_name
        self.command('LP ' + file_name)
        self._get_position_in_samples()
        # Forcing a '@S ...' output for length in ms

        volume_before = self._volume
        self.set_volume(0)
        self.play()
        self.pause()
        self.set_volume(volume_before)

        self.set_position(0)

        if self._pitch != self._actual_program_pitch:
            self.set_pitch(self._pitch)

    def toggle(self):
        self.command('P')

    def play(self):
        if self._current_state == MPG123Player.PLAYING:
            debug("already playing")
            return

        self.toggle()

    def pause(self):
        if self._current_state == MPG123Player.PAUSED:
            debug("already paused")
            return

        self.toggle()

    def stop(self):
        if self._current_state == MPG123Player.STOPPED:
            debug("already stopped")
            return

        self.command('S')

    def terminate(self):
        debug("MPG123 terminating...")
        if self._current_state == MPG123Player.TERMINATED:
            debug("mpg123 already terminated")
            return

        self._on_error = None
        self._current_state = MPG123Player.TERMINATED
        if self._mpg123_proc.returncode is None:
            # this strange construct is half of a historical artifact from python 3
            # and can probably be destroyed and hopefully be forgotten
            try:
                self.command('Q')
                self._mpg123_proc.wait()
            except:
                self._mpg123_proc.terminate()
                try:
                    self._mpg123_proc.wait()
                except:
                    pass

        debug("waiting for checker thread.")
        self._read_sout_thread.join()
        self._read_sout_thread = None

        debug("ok, finished.")

        return self._mpg123_proc.returncode
