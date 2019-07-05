#!/usr/bin/env python3

import logging
from flask import Flask
from flask_restful import Api
from csapi import MemberApi

handler = logging.FileHandler('/var/log/xroad/csapi.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(process)d - %(levelname)s: %(message)s'))

# CS API module logger
logger_m = logging.getLogger('csapi')
logger_m.setLevel(logging.INFO)
logger_m.addHandler(handler)

# Application logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

app = Flask(__name__)
api = Api(app)
api.add_resource(MemberApi, '/member')

logger.info('Starting Central Server API')
