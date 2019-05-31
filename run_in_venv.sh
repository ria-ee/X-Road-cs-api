#!/usr/bin/env bash

set -e

source venv/bin/activate
# Flask (Werkzeug) server
#python server_dev.py
# Production ready Gunicorn server
gunicorn -w 4 -b 127.0.0.1:5444 server:app
