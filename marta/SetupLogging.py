from logging import getLogger, DEBUG, Formatter, StreamHandler
from sys import stdout


def setup_stdout_logging():
    log = getLogger('')
    log.setLevel(DEBUG)

    ch = StreamHandler(stdout)
    ch.setFormatter(Formatter("%(asctime)s.%(msecs)03d | %(name)s |    %(message)s", "%H:%M:%S"))
    log.addHandler(ch)
