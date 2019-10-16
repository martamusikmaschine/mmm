#!/bin/bash

 echo -e "
 
       Welcome to
  __  __ __  __ __  __ 
 |  \/  |  \/  |  \/  |
 | |\/| | |\/| | |\/| |
 | |  | | |  | | |  | |
 |_|  |_|_|  |_|_|  |_|
                       
  Marta Musik Maschine
"

SCRIPT=$(readlink -f "$0")
SCRIPT_LOCATION=$(dirname "$SCRIPT")
MARTA=$(readlink -f "$SCRIPT_LOCATION/..")

export MARTA=$MARTA

echo "Main directory: $MARTA"

MARTA_MAIN_SCRIPT="$MARTA/marta/Marta.py"

if [[ ! -f $MARTA_MAIN_SCRIPT ]]; then
    echo "Argument error. Marta main script not a file: $MARTA_MAIN_SCRIPT"
    exit 1
fi

echo "Starting Marta main script."

until python "$MARTA_MAIN_SCRIPT"
do

if [ $? -eq 2 ]
then
echo "Debug exit."
exit 2
fi

echo "Restarting..."
sleep 1

done

echo "Shutting down."
shutdown now &

echo "Good bye."
exit 0
