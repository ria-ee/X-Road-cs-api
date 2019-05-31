#!/usr/bin/env python3

import logging
from flask import Flask, request
from flask_restful import Resource, Api
from member import MemberApi


# NB! For developing only
class StopApi(Resource):
    @staticmethod
    def get():
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
        func()
        return 'Server shutting down...'


handler = logging.FileHandler('/var/log/xroad/csapi.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(process)d - %(levelname)s: %(message)s'))

# Member module logger
logger_m = logging.getLogger('member')
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

if __name__ == '__main__':
    # Flask logger
    logger_f = logging.getLogger('werkzeug')
    logger_f.setLevel(logging.INFO)
    logger_f.addHandler(handler)

    # Running Flask (Werkzeug) server for development
    api.add_resource(StopApi, '/stop')
    app.run(debug=False, host='0.0.0.0', port=5444)
