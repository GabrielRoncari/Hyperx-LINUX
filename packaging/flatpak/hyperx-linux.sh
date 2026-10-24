#!/bin/sh
export PYTHONPATH="/app/share/hyperx-linux${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m hyperx_linux "$@"
