#!/usr/bin/env bash

set -e

SERVER=riajenk@jan-center2.ci.kit

ssh $SERVER "mkdir -p project"
rsync -r -p -l --exclude=\.* --exclude=venv . ${SERVER}:project/
ssh $SERVER "cd project; ./prepare_venv.sh; sudo -u xroad ./run_in_venv.sh"
