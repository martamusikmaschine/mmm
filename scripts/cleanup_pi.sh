#!/bin/bash

SCRIPT=$(readlink -f "$0")
SCRIPT_LOCATION=$(dirname "$SCRIPT")
MARTA=$(readlink -f "$SCRIPT_LOCATION/..")

# https://stackoverflow.com/a/226724
while true; do
    read -p "Do you really want to clean the project? y/N " yn
    case $yn in
        y|Y ) break;;
        * ) echo "Not doing anything."; exit 1;;
    esac
done

rm -rf "$MARTA/3d"
rm -rf "$MARTA/pcb"

echo "Project cleaned."

exit 0
