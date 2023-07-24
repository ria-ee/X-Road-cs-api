#!/usr/bin/env python3

"""This is a module for X-Road Central Server API Wrapper.

This module allows:
    * adding new member to the X-Road Central Server.
    * adding new subsystem to the X-Road Central Server.
"""

__version__ = '1.1'

import logging
import logging.config
import os
from flask import Flask, request, jsonify
from flask_restful import Api, Resource
import requests
import yaml

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG_FILE = 'config.yaml'
DEFAULT_API_URL = 'https://localhost:4000/api/v1'
DEFAULT_API_CA_FILE = 'ca.pem'
DEFAULT_API_TIMEOUT = 10
FILE_UMASK = 0o137

API_ERROR_MSG = 'Unclassified API error'


def load_config(config_file):
    """Load configuration from YAML file"""
    try:
        with open(config_file, 'r', encoding='utf-8') as conf:
            LOGGER.info('Loading configuration from file "%s"', config_file)
            return yaml.safe_load(conf)
    except IOError as err:
        LOGGER.error('Cannot open configuration file "%s": %s', config_file, str(err))
        return {}
    except yaml.YAMLError as err:
        LOGGER.error('Invalid YAML configuration file "%s": %s', config_file, str(err))
        return {}


def configure_app(config_file):
    """Prepare service logging and directories using config"""
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(process)d - %(levelname)s: %(message)s'))
    LOGGER.addHandler(console_handler)
    LOGGER.setLevel(logging.INFO)

    config = load_config(config_file)

    # Set umask for created files
    os.umask(FILE_UMASK)

    # Reconfigure logging if logging_config or log_file configuration parameters were provided
    if config.get('logging_config'):
        logging.config.dictConfig(config['logging_config'])
        LOGGER.info(
            'Configured logging using "logging_config" parameter '
            'from "%s" configuration file', config_file)
    elif config.get('log_file'):
        file_handler = logging.FileHandler(config['log_file'])
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(process)d - %(levelname)s: %(message)s'))
        LOGGER.addHandler(file_handler)
        LOGGER.info(
            'Configured logging using "log_file" parameter '
            'from "%s" configuration file', config_file)
        LOGGER.removeHandler(console_handler)

    return config


def api_request_params(config, endpoint):
    """Prepare parameters for API request"""
    return {
        'url': f'{config.get("api_url", DEFAULT_API_URL)}{endpoint}',
        'headers': {'Authorization': f'X-Road-ApiKey token={config.get("api_key")}'},
        'verify': config.get('api_ca_file', DEFAULT_API_CA_FILE),
        'timeout': config.get('api_timeout', DEFAULT_API_TIMEOUT)
    }


def add_member(member_class, member_code, member_name, json_data, config):
    """Add new X-Road member to Central Server"""
    params = api_request_params(config, '/members')
    payload = {
        'member_name': member_name,
        'member_id': {
            'member_class': member_class,
            'member_code': member_code
        }
    }
    req = requests.post(
        params['url'], headers=params['headers'], verify=params['verify'],
        timeout=params['timeout'], json=payload)

    if req.status_code == 409:
        LOGGER.warning(
            'MEMBER_EXISTS: Provided Member already exists '
            '(Request: %s)', json_data)
        return {
            'http_status': 409, 'code': 'MEMBER_EXISTS',
            'msg': 'Provided Member already exists'}

    req.raise_for_status()

    LOGGER.info(
        'Added new Member: member_code=%s, member_name=%s, member_class=%s',
        member_code, member_name, member_class)

    return {'http_status': 201, 'code': 'CREATED', 'msg': 'New Member added'}


def add_subsystem(member_class, member_code, subsystem_code, json_data, config):
    """Add new X-Road subsystem to Central Server"""
    params = api_request_params(config, '/subsystems')
    payload = {
        'subsystem_id': {
            'member_class': member_class,
            'member_code': member_code,
            'subsystem_code': subsystem_code
        }
    }
    req = requests.post(
        params['url'], headers=params['headers'], verify=params['verify'],
        timeout=params['timeout'], json=payload)

    if req.status_code == 409:
        LOGGER.warning(
            'SUBSYSTEM_EXISTS: Provided Subsystem already exists '
            '(Request: %s)', json_data)
        return {
            'http_status': 409, 'code': 'SUBSYSTEM_EXISTS',
            'msg': 'Provided Subsystem already exists'}

    req.raise_for_status()

    LOGGER.info(
        'Added new Subsystem: member_class=%s, member_code=%s, subsystem_code=%s',
        member_class, member_code, subsystem_code)
    return {'http_status': 201, 'code': 'CREATED', 'msg': 'New Subsystem added'}


def test_api(config):
    """Test if Central Server API is alive"""
    params = api_request_params(config, '/system/status')
    req = requests.get(
        params['url'], headers=params['headers'], verify=params['verify'],
        timeout=params['timeout'])

    req.raise_for_status()

    return {
        'http_status': 200, 'code': 'OK',
        'msg': 'API is ready'}


def make_response(data):
    """Create JSON response object"""
    response = jsonify({'code': data['code'], 'msg': data['msg']})
    response.status_code = data['http_status']
    LOGGER.info('Response: %s', data)
    return response


def get_input(json_data, param_name):
    """Get parameter from request parameters

    Returns two items:
    * parameter value
    * error response (if parameter not found).
    If one parameter is set then other is always None.
    """
    try:
        param = json_data[param_name]
    except KeyError:
        LOGGER.warning(
            'MISSING_PARAMETER: Request parameter %s is missing '
            '(Request: %s)', param_name, json_data)
        return None, {
            'http_status': 400, 'code': 'MISSING_PARAMETER',
            'msg': f'Request parameter {param_name} is missing'}

    return param, None


def check_client(config, client_dn):
    """Check if client dn is in whitelist"""
    # If config is None then all clients are not allowed
    if config is None:
        return False
    if config.get('allow_all', False) is True:
        return True

    allowed = config.get('allowed')
    if client_dn is None or not isinstance(allowed, list):
        return False

    if client_dn in allowed:
        return True

    return False


def incorrect_client(client_dn):
    """Return error response when client is not allowed"""
    LOGGER.error('FORBIDDEN: Client certificate is not allowed: %s', client_dn)
    return make_response({
        'http_status': 403, 'code': 'FORBIDDEN',
        'msg': f'Client certificate is not allowed: {client_dn}'})


class MemberApi(Resource):  # pylint: disable=too-few-public-methods
    """Member API class for Flask"""
    def __init__(self, config):
        self.config = config

    def post(self):
        """POST method"""
        json_data = request.get_json(force=True)
        client_dn = request.headers.get('X-Ssl-Client-S-Dn')

        LOGGER.info('Incoming request: %s', json_data)
        LOGGER.info('Client DN: %s', client_dn)

        if not check_client(self.config, client_dn):
            return incorrect_client(client_dn)

        (member_class, fault_response) = get_input(json_data, 'member_class')
        if member_class is None:
            return make_response(fault_response)

        (member_code, fault_response) = get_input(json_data, 'member_code')
        if member_code is None:
            return make_response(fault_response)

        (member_name, fault_response) = get_input(json_data, 'member_name')
        if member_name is None:
            return make_response(fault_response)

        try:
            response = add_member(member_class, member_code, member_name, json_data, self.config)
        except requests.exceptions.RequestException as err:
            LOGGER.error('API_ERROR: %s: %s', API_ERROR_MSG, err)
            response = {
                'http_status': 500, 'code': 'API_ERROR',
                'msg': API_ERROR_MSG}

        return make_response(response)


class SubsystemApi(Resource):  # pylint: disable=too-few-public-methods
    """Subsystem API class for Flask"""
    def __init__(self, config):
        self.config = config

    def post(self):
        """POST method"""
        json_data = request.get_json(force=True)
        client_dn = request.headers.get('X-Ssl-Client-S-Dn')

        LOGGER.info('Incoming request: %s', json_data)
        LOGGER.info('Client DN: %s', client_dn)

        if not check_client(self.config, client_dn):
            return incorrect_client(client_dn)

        (member_class, fault_response) = get_input(json_data, 'member_class')
        if member_class is None:
            return make_response(fault_response)

        (member_code, fault_response) = get_input(json_data, 'member_code')
        if member_code is None:
            return make_response(fault_response)

        (subsystem_code, fault_response) = get_input(json_data, 'subsystem_code')
        if subsystem_code is None:
            return make_response(fault_response)

        try:
            response = add_subsystem(
                member_class, member_code, subsystem_code, json_data, self.config)
        except requests.exceptions.RequestException as err:
            LOGGER.error('API_ERROR: %s: %s', API_ERROR_MSG, err)
            response = {
                'http_status': 500, 'code': 'API_ERROR',
                'msg': API_ERROR_MSG}

        return make_response(response)


class StatusApi(Resource):  # pylint: disable=too-few-public-methods
    """Status API class for Flask"""
    def __init__(self, config):
        self.config = config

    def get(self):
        """GET method"""
        LOGGER.info('Incoming status request')

        try:
            response = test_api(self.config)
        except requests.exceptions.RequestException as err:
            LOGGER.error('API_ERROR: %s: %s', API_ERROR_MSG, err)
            response = {
                'http_status': 500, 'code': 'API_ERROR',
                'msg': API_ERROR_MSG}

        return make_response(response)


def create_app(config_file=DEFAULT_CONFIG_FILE):
    """Create Flask application"""
    config = configure_app(config_file)

    app = Flask(__name__)
    api = Api(app)
    api.add_resource(MemberApi, '/member', resource_class_kwargs={'config': config})
    api.add_resource(SubsystemApi, '/subsystem', resource_class_kwargs={'config': config})
    api.add_resource(StatusApi, '/status', resource_class_kwargs={'config': config})

    LOGGER.info('Starting Central Server API v%s', __version__)

    return app
