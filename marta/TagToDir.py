from os import listdir
from os.path import isdir
from logging import getLogger
from re import compile, match
from Util import sorted_aphanumeric

TAG_TO_DIR = {}

debug = getLogger('  TagToDir').debug

ALBUM_INDICATOR_FILE = ".albumindicator"


def prepare_albums(tag_path):
    possible_albums = sorted_aphanumeric(listdir(tag_path))
    if len(possible_albums) is 0:
        raise Exception("empty tag directory: " + tag_path)

    albums = []

    current_album_dir = None
    at_least_one_file = False
    for album_dir in possible_albums:
        current = tag_path + "/" + album_dir

        if isdir(current):
            files = listdir(current)
            if len(files) is 0:
                raise Exception("empty album directory: " + current)

            if ALBUM_INDICATOR_FILE in files:
                current_album_dir = current

            albums.append(current)

        else:
            at_least_one_file = True

    # we have to shift and cannot simply insert in place at index 0 because that doesn't rotate the other entries
    if current_album_dir is not None:
        i = albums.index(current_album_dir)
        albums = albums[i:] + albums[:i]

    if len(albums) is 0:
        albums.append(tag_path)
    elif at_least_one_file:
        raise Exception("directory and files mixed: " + tag_path)

    return albums


def prepare(audio_path):
    if not isdir(audio_path):
        debug("not a directory: " + audio_path)
        exit(1)

    if not isdir(audio_path + "/system"):
        raise Exception("missing directory: " + audio_path + "/system")

    dirs = listdir(audio_path)

    regex = compile("^.*([0-9A-F]{12})$")

    debug(audio_path + "/system exists")

    for d in dirs:

        current = audio_path + "/" + d

        if not isdir(audio_path + "/" + d):
            raise Exception("not a directory: " + current)

        if d == "system":
            continue

        if not match(regex, d):
            raise Exception("naming convention error: " + current)

        tag = d[-12:]

        if tag in TAG_TO_DIR:
            raise Exception("tag found twice: " + d + ", " + TAG_TO_DIR[tag])

        TAG_TO_DIR[tag] = prepare_albums(current)
        debug(tag + "=" + str(TAG_TO_DIR[tag]))


if __name__ == "__main__":
    from SetupLogging import setup_stdout_logging
    from sys import argv

    setup_stdout_logging()

    if len(argv) is not 2:
        debug("Error: Missing path argument.")
        exit(1)

    try:
        prepare(argv[1])
    except Exception as e:
        debug("Error: " + str(e))
        exit(1)

    debug("Everything seems fine.")
    exit(0)
