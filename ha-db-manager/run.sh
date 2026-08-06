#!/usr/bin/env sh
# Export add-on options to environment variables, then start the app.
# Home Assistant stores the configured options in /data/options.json.

OPTIONS_FILE="${OPTIONS_FILE:-/data/options.json}"

if [ -f "$OPTIONS_FILE" ]; then
    LOG_LEVEL="$(python3 -c "import json;print(json.load(open('$OPTIONS_FILE')).get('log_level','info'))")"
    export HA_LOG_LEVEL="${LOG_LEVEL:-info}"
fi

exec python3 /opt/app.py
