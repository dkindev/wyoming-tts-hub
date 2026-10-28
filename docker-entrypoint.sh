#!/bin/sh

set -e

if [ "$(id -u)" = "0" ]
then
    chown -R wthub:wthub /app

    # restart script as wthub user
    exec gosu wthub "$@"
fi

exec "$@"