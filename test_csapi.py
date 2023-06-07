import json
import unittest
import csapi
import requests
from flask import Flask, jsonify
from flask_restful import Api
from unittest.mock import patch, MagicMock, mock_open, call


class MainTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.client = self.app.test_client()
        self.api = Api(self.app)
        self.api.add_resource(csapi.MemberApi, '/member', resource_class_kwargs={
            'config': {'allow_all': True}})
        self.api.add_resource(csapi.SubsystemApi, '/subsystem', resource_class_kwargs={
            'config': {'allow_all': True}})
        self.api.add_resource(csapi.StatusApi, '/status', resource_class_kwargs={
            'config': {'allow_all': True}})

    def test_load_config(self):
        # Valid yaml
        with patch('builtins.open', mock_open(read_data=json.dumps({'allow_all': True}))) as m:
            self.assertEqual({'allow_all': True}, csapi.load_config('FILENAME'))
            m.assert_called_once_with('FILENAME', 'r', encoding='utf-8')
        # Invalid yaml
        with patch('builtins.open', mock_open(read_data='INVALID_YAML: {}x')) as m:
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                self.assertEqual({}, csapi.load_config('FILENAME'))
                m.assert_called_once_with('FILENAME', 'r', encoding='utf-8')
                self.assertIn(
                    'INFO:csapi:Loading configuration from file "FILENAME"', cm.output)
                self.assertIn(
                    'ERROR:csapi:Invalid YAML configuration file "FILENAME"', cm.output[1])
        # Invalid file
        with patch('builtins.open', mock_open()) as m:
            m.side_effect = IOError
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                self.assertEqual({}, csapi.load_config('FILENAME'))
                m.assert_called_once_with('FILENAME', 'r', encoding='utf-8')
                self.assertEqual([
                    'ERROR:csapi:Cannot open configuration file "FILENAME": '], cm.output)

    @patch('csapi.load_config', return_value={'log_file': 'LOG_FILE'})
    @patch('os.umask')
    @patch('csapi.LOGGER')
    @patch('logging.FileHandler')
    def test_configure_app(
            self, mock_log_file_handler, mock_logger, mock_os_umask, mock_load_config):
        config = csapi.configure_app('CONFIG_FILE')
        mock_log_file_handler.assert_called_with('LOG_FILE')
        mock_logger.addHandler.assert_has_calls(mock_log_file_handler)
        mock_os_umask.assert_called_with(0o137)
        mock_load_config.assert_called_with('CONFIG_FILE')
        self.assertEqual({'log_file': 'LOG_FILE'}, config)

    @patch('csapi.load_config', return_value={
        'log_file': 'LOG_FILE', 'logging_config': 'LOGGING_CONFIG'})
    @patch('os.umask')
    @patch('csapi.LOGGER')
    @patch('logging.FileHandler')
    @patch('logging.config.dictConfig')
    def test_configure_app_logging_config(
            self, mock_dict_config, mock_log_file_handler, mock_logger,
            mock_os_umask, mock_load_config):
        config = csapi.configure_app('CONFIG_FILE')
        mock_log_file_handler.assert_not_called()
        mock_dict_config.assert_called_with('LOGGING_CONFIG')
        mock_logger.addHandler.assert_has_calls(mock_log_file_handler)
        mock_os_umask.assert_called_with(0o137)
        mock_load_config.assert_called_with('CONFIG_FILE')
        self.assertEqual({'log_file': 'LOG_FILE', 'logging_config': 'LOGGING_CONFIG'}, config)

    @patch('csapi.load_config', return_value={'a': 'b'})
    @patch('os.umask')
    @patch('csapi.LOGGER')
    @patch('logging.StreamHandler')
    def test_configure_app_no_log_file(
            self, mock_console_log_handler, mock_logger, mock_os_umask, mock_load_config):
        config = csapi.configure_app('CONFIG_FILE')
        mock_console_log_handler.assert_called_with()
        mock_logger.addHandler.assert_has_calls(mock_console_log_handler)
        mock_os_umask.assert_called_with(0o137)
        mock_load_config.assert_called_with('CONFIG_FILE')
        self.assertEqual({'a': 'b'}, config)

    def test_api_request_params(self):
        # Default values
        self.assertEqual({
            'headers': {'Authorization': 'X-Road-ApiKey token=None'},
            'timeout': 10,
            'url': 'https://localhost:4000/api/v1/ENDPOINT',
            'verify': 'ca.pem'}, csapi.api_request_params({}, '/ENDPOINT'))
        # Values from config
        self.assertEqual(
            {
                'headers': {'Authorization': 'X-Road-ApiKey token=SECRET_API_TOKEN'},
                'timeout': 20,
                'url': 'https://CENTRALSERVER:4000/api/v1/ENDPOINT',
                'verify': 'ROOT_CA.pem'
            },
            csapi.api_request_params({
                "api_url": "https://CENTRALSERVER:4000/api/v1",
                "api_ca_file": "ROOT_CA.pem",
                "api_key": "SECRET_API_TOKEN",
                "api_timeout": 20
            }, '/ENDPOINT'))

    @patch('csapi.requests')
    @patch('csapi.api_request_params', return_value={
        'url': 'URL', 'headers': {'HEAD': 'VAL'}, 'verify': 'VERIFY', 'timeout': 'TIMEOUT'})
    def test_add_member_member_exists(self, mock_api_request_params, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_requests.post.return_value = mock_response
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'MEMBER_EXISTS', 'http_status': 409,
                    'msg': 'Provided Member already exists'},
                csapi.add_member(
                    'MEMBER_CLASS', 'MEMBER_CODE', 'MEMBER_NAME', 'JSON_DATA', {'CONFIG': 'VAL'}))
            self.assertEqual([
                'WARNING:csapi:MEMBER_EXISTS: Provided Member already exists (Request: '
                'JSON_DATA)'], cm.output)
            mock_api_request_params.assert_called_with({'CONFIG': 'VAL'}, '/members')
            mock_requests.post.assert_called_with(
                'URL', headers={'HEAD': 'VAL'}, verify='VERIFY', timeout='TIMEOUT',
                json={'member_name': 'MEMBER_NAME', 'member_id': {
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE'}})

    @patch('csapi.requests')
    @patch('csapi.api_request_params', return_value={
        'url': 'URL', 'headers': {'HEAD': 'VAL'}, 'verify': 'VERIFY', 'timeout': 'TIMEOUT'})
    def test_add_member_api_error(self, mock_api_request_params, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.RequestException('ERROR')
        mock_requests.post.return_value = mock_response
        with self.assertRaises(requests.exceptions.RequestException):
            csapi.add_member(
                'MEMBER_CLASS', 'MEMBER_CODE', 'MEMBER_NAME', 'JSON_DATA', {'CONFIG': 'VAL'})
        mock_api_request_params.assert_called_with({'CONFIG': 'VAL'}, '/members')
        mock_requests.post.assert_called_with(
            'URL', headers={'HEAD': 'VAL'}, verify='VERIFY', timeout='TIMEOUT',
            json={'member_name': 'MEMBER_NAME', 'member_id': {
                'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE'}})

    @patch('csapi.requests')
    @patch('csapi.api_request_params', return_value={
        'url': 'URL', 'headers': {'HEAD': 'VAL'}, 'verify': 'VERIFY', 'timeout': 'TIMEOUT'})
    def test_add_member_ok(self, mock_api_request_params, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_requests.post.return_value = mock_response
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'CREATED', 'http_status': 201,
                    'msg': 'New Member added'},
                csapi.add_member(
                    'MEMBER_CLASS', 'MEMBER_CODE', 'MEMBER_NAME', 'JSON_DATA', {'CONFIG': 'VAL'}))
            self.assertEqual([
                'INFO:csapi:Added new Member: member_code=MEMBER_CODE, '
                'member_name=MEMBER_NAME, member_class=MEMBER_CLASS'], cm.output)
            mock_api_request_params.assert_called_with({'CONFIG': 'VAL'}, '/members')
            mock_requests.post.assert_called_with(
                'URL', headers={'HEAD': 'VAL'}, verify='VERIFY', timeout='TIMEOUT',
                json={'member_name': 'MEMBER_NAME', 'member_id': {
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE'}})

    @patch('csapi.requests')
    @patch('csapi.api_request_params', return_value={
        'url': 'URL', 'headers': {'HEAD': 'VAL'}, 'verify': 'VERIFY', 'timeout': 'TIMEOUT'})
    def test_add_subsystem_subsystem_exists(self, mock_api_request_params, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_requests.post.return_value = mock_response
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'SUBSYSTEM_EXISTS', 'http_status': 409,
                    'msg': 'Provided Subsystem already exists'},
                csapi.add_subsystem(
                    'MEMBER_CLASS', 'MEMBER_CODE', 'SUBSYSTEM_CODE',
                    'JSON_DATA', {'CONFIG': 'VAL'}))
            self.assertEqual([
                'WARNING:csapi:SUBSYSTEM_EXISTS: Provided Subsystem already exists (Request: '
                'JSON_DATA)'], cm.output)
            mock_api_request_params.assert_called_with({'CONFIG': 'VAL'}, '/subsystems')
            mock_requests.post.assert_called_with(
                'URL', headers={'HEAD': 'VAL'}, verify='VERIFY', timeout='TIMEOUT',
                json={'subsystem_id': {
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                    'subsystem_code': 'SUBSYSTEM_CODE'}})

    @patch('csapi.requests')
    @patch('csapi.api_request_params', return_value={
        'url': 'URL', 'headers': {'HEAD': 'VAL'}, 'verify': 'VERIFY', 'timeout': 'TIMEOUT'})
    def test_add_subsystem_api_error(self, mock_api_request_params, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.RequestException('ERROR')
        mock_requests.post.return_value = mock_response
        with self.assertRaises(requests.exceptions.RequestException):
            csapi.add_subsystem(
                'MEMBER_CLASS', 'MEMBER_CODE', 'SUBSYSTEM_CODE',
                'JSON_DATA', {'CONFIG': 'VAL'})
        mock_api_request_params.assert_called_with({'CONFIG': 'VAL'}, '/subsystems')
        mock_requests.post.assert_called_with(
            'URL', headers={'HEAD': 'VAL'}, verify='VERIFY', timeout='TIMEOUT',
            json={'subsystem_id': {
                'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                'subsystem_code': 'SUBSYSTEM_CODE'}})

    @patch('csapi.requests')
    @patch('csapi.api_request_params', return_value={
        'url': 'URL', 'headers': {'HEAD': 'VAL'}, 'verify': 'VERIFY', 'timeout': 'TIMEOUT'})
    def test_add_subsystem_ok(self, mock_api_request_params, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_requests.post.return_value = mock_response
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'CREATED', 'http_status': 201,
                    'msg': 'New Subsystem added'},
                csapi.add_subsystem(
                    'MEMBER_CLASS', 'MEMBER_CODE', 'SUBSYSTEM_CODE',
                    'JSON_DATA', {'CONFIG': 'VAL'}))
            self.assertEqual([
                'INFO:csapi:Added new Subsystem: member_class=MEMBER_CLASS, '
                'member_code=MEMBER_CODE, subsystem_code=SUBSYSTEM_CODE'], cm.output)
            mock_api_request_params.assert_called_with({'CONFIG': 'VAL'}, '/subsystems')
            mock_requests.post.assert_called_with(
                'URL', headers={'HEAD': 'VAL'}, verify='VERIFY', timeout='TIMEOUT',
                json={'subsystem_id': {
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                    'subsystem_code': 'SUBSYSTEM_CODE'}})

    def test_make_response(self):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = csapi.make_response(
                    {'http_status': 200, 'code': 'OK', 'msg': 'All Correct'})
                self.assertEqual(200, response.status_code)
                self.assertEqual(
                    jsonify({'code': 'OK', 'msg': 'All Correct'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Response: {'http_status': 200, 'code': 'OK', "
                    "'msg': 'All Correct'}"], cm.output)

    def test_get_input(self):
        (value, err) = csapi.get_input(
            {'member_name': 'MEMBER_NAME', 'member_class': 'MEMBER_CLASS'},
            'member_name')
        self.assertEqual('MEMBER_NAME', value)
        self.assertEqual(None, err)

    def test_get_input_err(self):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            (value, err) = csapi.get_input(
                {'member_name': 'MEMBER_NAME', 'member_class': 'MEMBER_CLASS'},
                'member_code')
            self.assertEqual(None, value)
            self.assertEqual({
                'code': 'MISSING_PARAMETER', 'http_status': 400,
                'msg': 'Request parameter member_code is missing'}, err)
            self.assertEqual([
                'WARNING:csapi:MISSING_PARAMETER: Request parameter member_code is missing '
                "(Request: {'member_name': 'MEMBER_NAME', 'member_class': 'MEMBER_CLASS'})"],
                cm.output)

    def test_check_client(self):
        self.assertEqual(False, csapi.check_client(None, 'CLIENT_DN'))
        self.assertEqual(True, csapi.check_client({'allow_all': True}, 'CLIENT_DN'))
        self.assertEqual(False, csapi.check_client({'allowed': ['DN1', 'DN2']}, None))
        self.assertEqual(False, csapi.check_client({'allowed': 'NOT_LIST'}, 'DN3'))
        self.assertEqual(True, csapi.check_client({'allowed': ['DN1', 'DN2']}, 'DN1'))
        self.assertEqual(False, csapi.check_client({'allowed': ['DN1', 'DN2']}, 'DN3'))

    def test_incorrect_client(self):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = csapi.incorrect_client('CLIENT_DN')
                self.assertEqual(403, response.status_code)
                self.assertEqual(
                    jsonify({
                        'code': 'FORBIDDEN',
                        'msg': 'Client certificate is not allowed: CLIENT_DN'}).json,
                    response.json
                )
                self.assertEqual([
                    'ERROR:csapi:FORBIDDEN: Client certificate is not allowed: CLIENT_DN',
                    "INFO:csapi:Response: {'http_status': 403, 'code': 'FORBIDDEN', 'msg': "
                    "'Client certificate is not allowed: CLIENT_DN'}"], cm.output)

    def test_member_empty_query(self):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            response = self.client.post('/member', data=json.dumps({}))
            self.assertEqual(400, response.status_code)
            # Not testing response content, it does not come from application
            self.assertEqual([
                'INFO:csapi:Incoming request: {}',
                'INFO:csapi:Client DN: None',
                'WARNING:csapi:MISSING_PARAMETER: Request parameter member_class is missing '
                '(Request: {})',
                "INFO:csapi:Response: {'http_status': 400, 'code': 'MISSING_PARAMETER', "
                "'msg': 'Request parameter member_class is missing'}"], cm.output)

    def test_member_empty_member_class_query(self):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.post('/member', data=json.dumps(
                    {'member_code': 'MEMBER_CODE', 'member_name': 'MEMBER_NAME'}))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    jsonify({
                        'code': 'MISSING_PARAMETER',
                        'msg': 'Request parameter member_class is missing'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Incoming request: {'member_code': 'MEMBER_CODE', 'member_name': "
                    "'MEMBER_NAME'}",
                    'INFO:csapi:Client DN: None',
                    'WARNING:csapi:MISSING_PARAMETER: Request parameter member_class is missing '
                    "(Request: {'member_code': 'MEMBER_CODE', 'member_name': 'MEMBER_NAME'})",
                    "INFO:csapi:Response: {'http_status': 400, 'code': 'MISSING_PARAMETER', "
                    "'msg': 'Request parameter member_class is missing'}"], cm.output)

    def test_member_empty_member_code_query(self):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.post('/member', data=json.dumps(
                    {'member_class': 'MEMBER_CLASS', 'member_name': 'MEMBER_NAME'}))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    jsonify({
                        'code': 'MISSING_PARAMETER',
                        'msg': 'Request parameter member_code is missing'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Incoming request: {'member_class': 'MEMBER_CLASS', 'member_name': "
                    "'MEMBER_NAME'}",
                    'INFO:csapi:Client DN: None',
                    'WARNING:csapi:MISSING_PARAMETER: Request parameter member_code is missing '
                    "(Request: {'member_class': 'MEMBER_CLASS', 'member_name': 'MEMBER_NAME'})",
                    "INFO:csapi:Response: {'http_status': 400, 'code': 'MISSING_PARAMETER', "
                    "'msg': 'Request parameter member_code is missing'}"], cm.output)

    def test_member_empty_member_name_query(self):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.post('/member', data=json.dumps(
                    {'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE'}))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    jsonify({
                        'code': 'MISSING_PARAMETER',
                        'msg': 'Request parameter member_name is missing'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Incoming request: {'member_class': 'MEMBER_CLASS', 'member_code': "
                    "'MEMBER_CODE'}",
                    'INFO:csapi:Client DN: None',
                    'WARNING:csapi:MISSING_PARAMETER: Request parameter member_name is missing '
                    "(Request: {'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE'})",
                    "INFO:csapi:Response: {'http_status': 400, 'code': 'MISSING_PARAMETER', "
                    "'msg': 'Request parameter member_name is missing'}"], cm.output)

    @patch('csapi.add_member', side_effect=requests.exceptions.RequestException('API_ERROR_MSG'))
    def test_member_api_error_handled(self, mock_add_member):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.post('/member', data=json.dumps({
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                    'member_name': 'MEMBER_NAME'}))
                self.assertEqual(response.status_code, 500)
                self.assertEqual(
                    jsonify({
                        'code': 'API_ERROR',
                        'msg': 'Unclassified API error'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Incoming request: {'member_class': 'MEMBER_CLASS', 'member_code': "
                    "'MEMBER_CODE', 'member_name': 'MEMBER_NAME'}",
                    'INFO:csapi:Client DN: None',
                    'ERROR:csapi:API_ERROR: Unclassified API error: API_ERROR_MSG',
                    "INFO:csapi:Response: {'http_status': 500, 'code': 'API_ERROR', 'msg': "
                    "'Unclassified API error'}"], cm.output)
                mock_add_member.assert_called_with('MEMBER_CLASS', 'MEMBER_CODE', 'MEMBER_NAME', {
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                    'member_name': 'MEMBER_NAME'}, {'allow_all': True})

    @patch('csapi.add_member', return_value={
        'http_status': 201, 'code': 'OK', 'msg': 'New Member added'})
    def test_member_ok_query(self, mock_add_member):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.post('/member', data=json.dumps({
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                    'member_name': 'MEMBER_NAME'}))
                self.assertEqual(response.status_code, 201)
                self.assertEqual(
                    jsonify({
                        'code': 'OK',
                        'msg': 'New Member added'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Incoming request: {'member_class': 'MEMBER_CLASS', 'member_code': "
                    "'MEMBER_CODE', 'member_name': 'MEMBER_NAME'}",
                    'INFO:csapi:Client DN: None',
                    "INFO:csapi:Response: {'http_status': 201, 'code': 'OK', 'msg': 'New Member "
                    "added'}"], cm.output)
                mock_add_member.assert_called_with('MEMBER_CLASS', 'MEMBER_CODE', 'MEMBER_NAME', {
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                    'member_name': 'MEMBER_NAME'}, {'allow_all': True})

    def test_subsystem_empty_query(self):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            response = self.client.post('/subsystem', data=json.dumps({}))
            self.assertEqual(400, response.status_code)
            # Not testing response content, it does not come from application
            self.assertEqual([
                'INFO:csapi:Incoming request: {}',
                'INFO:csapi:Client DN: None',
                'WARNING:csapi:MISSING_PARAMETER: Request parameter member_class is missing '
                '(Request: {})',
                "INFO:csapi:Response: {'http_status': 400, 'code': 'MISSING_PARAMETER', "
                "'msg': 'Request parameter member_class is missing'}"], cm.output)

    def test_subsystem_empty_member_class_query(self):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.post('/subsystem', data=json.dumps(
                    {'member_code': 'MEMBER_CODE', 'subsystem_code': 'SUBSYSTEM_CODE'}))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    jsonify({
                        'code': 'MISSING_PARAMETER',
                        'msg': 'Request parameter member_class is missing'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Incoming request: {'member_code': 'MEMBER_CODE', "
                    "'subsystem_code': 'SUBSYSTEM_CODE'}",
                    'INFO:csapi:Client DN: None',
                    'WARNING:csapi:MISSING_PARAMETER: Request parameter member_class is missing '
                    "(Request: {'member_code': 'MEMBER_CODE', "
                    "'subsystem_code': 'SUBSYSTEM_CODE'})",
                    "INFO:csapi:Response: {'http_status': 400, 'code': 'MISSING_PARAMETER', "
                    "'msg': 'Request parameter member_class is missing'}"], cm.output)

    def test_subsystem_empty_member_code_query(self):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.post('/subsystem', data=json.dumps(
                    {'member_class': 'MEMBER_CLASS', 'subsystem_code': 'SUBSYSTEM_CODE'}))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    jsonify({
                        'code': 'MISSING_PARAMETER',
                        'msg': 'Request parameter member_code is missing'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Incoming request: {'member_class': 'MEMBER_CLASS', "
                    "'subsystem_code': 'SUBSYSTEM_CODE'}",
                    'INFO:csapi:Client DN: None',
                    'WARNING:csapi:MISSING_PARAMETER: Request parameter member_code is missing '
                    "(Request: {'member_class': 'MEMBER_CLASS', "
                    "'subsystem_code': 'SUBSYSTEM_CODE'})",
                    "INFO:csapi:Response: {'http_status': 400, 'code': 'MISSING_PARAMETER', "
                    "'msg': 'Request parameter member_code is missing'}"], cm.output)

    def test_subsystem_empty_subsystem_code_query(self):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.post('/subsystem', data=json.dumps(
                    {'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE'}))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    jsonify({
                        'code': 'MISSING_PARAMETER',
                        'msg': 'Request parameter subsystem_code is missing'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Incoming request: {'member_class': 'MEMBER_CLASS', 'member_code': "
                    "'MEMBER_CODE'}",
                    'INFO:csapi:Client DN: None',
                    'WARNING:csapi:MISSING_PARAMETER: Request parameter subsystem_code is missing '
                    "(Request: {'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE'})",
                    "INFO:csapi:Response: {'http_status': 400, 'code': 'MISSING_PARAMETER', "
                    "'msg': 'Request parameter subsystem_code is missing'}"], cm.output)

    @patch('csapi.add_subsystem', side_effect=requests.exceptions.RequestException('API_ERROR_MSG'))
    def test_subsystem_db_error_handled(self, mock_add_member):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.post('/subsystem', data=json.dumps({
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                    'subsystem_code': 'SUBSYSTEM_CODE'}))
                self.assertEqual(response.status_code, 500)
                self.assertEqual(
                    jsonify({
                        'code': 'API_ERROR',
                        'msg': 'Unclassified API error'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Incoming request: {'member_class': 'MEMBER_CLASS', 'member_code': "
                    "'MEMBER_CODE', 'subsystem_code': 'SUBSYSTEM_CODE'}",
                    'INFO:csapi:Client DN: None',
                    'ERROR:csapi:API_ERROR: Unclassified API error: API_ERROR_MSG',
                    "INFO:csapi:Response: {'http_status': 500, 'code': 'API_ERROR', 'msg': "
                    "'Unclassified API error'}"], cm.output)
                mock_add_member.assert_called_with(
                    'MEMBER_CLASS', 'MEMBER_CODE', 'SUBSYSTEM_CODE', {
                        'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                        'subsystem_code': 'SUBSYSTEM_CODE'}, {'allow_all': True})

    @patch('csapi.add_subsystem', return_value={
        'http_status': 201, 'code': 'OK', 'msg': 'New Member added'})
    def test_subsystem_ok_query(self, mock_add_subsystem):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.post('/subsystem', data=json.dumps({
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                    'subsystem_code': 'SUBSYSTEM_CODE'}))
                self.assertEqual(response.status_code, 201)
                self.assertEqual(
                    jsonify({
                        'code': 'OK',
                        'msg': 'New Member added'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Incoming request: {'member_class': 'MEMBER_CLASS', 'member_code': "
                    "'MEMBER_CODE', 'subsystem_code': 'SUBSYSTEM_CODE'}",
                    'INFO:csapi:Client DN: None',
                    "INFO:csapi:Response: {'http_status': 201, 'code': 'OK', 'msg': 'New Member "
                    "added'}"], cm.output)
                mock_add_subsystem.assert_called_with(
                    'MEMBER_CLASS', 'MEMBER_CODE', 'SUBSYSTEM_CODE', {
                        'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                        'subsystem_code': 'SUBSYSTEM_CODE'}, {'allow_all': True})

    @patch('csapi.requests')
    @patch('csapi.api_request_params', return_value={
        'url': 'URL', 'headers': {'HEAD': 'VAL'}, 'verify': 'VERIFY', 'timeout': 'TIMEOUT'})
    def test_test_api_ok(self, mock_api_request_params, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        self.assertEqual(
            {
                'code': 'OK', 'http_status': 200,
                'msg': 'API is ready'},
            csapi.test_api({'CONFIG': 'VAL'}))
        mock_api_request_params.assert_called_with({'CONFIG': 'VAL'}, '/system/status')
        mock_requests.get.assert_called_with(
            'URL', headers={'HEAD': 'VAL'}, verify='VERIFY', timeout='TIMEOUT')

    @patch('csapi.test_api', side_effect=requests.exceptions.RequestException('API_ERROR_MSG'))
    def test_status_db_error_handled(self, mock_test_api):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.get('/status')
                self.assertEqual(500, response.status_code)
                self.assertEqual(
                    jsonify({
                        'code': 'API_ERROR',
                        'msg': 'Unclassified API error'}).json,
                    response.json
                )
                self.assertEqual([
                    'INFO:csapi:Incoming status request',
                    'ERROR:csapi:API_ERROR: Unclassified API error: API_ERROR_MSG',
                    "INFO:csapi:Response: {'http_status': 500, 'code': 'API_ERROR', 'msg': "
                    "'Unclassified API error'}"], cm.output)
                mock_test_api.assert_called_with({'allow_all': True})

    @patch('csapi.test_api', return_value={
        'http_status': 200, 'code': 'OK', 'msg': 'API is ready'})
    def test_status_ok(self, mock_test_api):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.get('/status')
                self.assertEqual(200, response.status_code)
                self.assertEqual(
                    jsonify({'code': 'OK', 'msg': 'API is ready'}).json,
                    response.json
                )
                self.assertEqual([
                    'INFO:csapi:Incoming status request',
                    "INFO:csapi:Response: {'http_status': 200, 'code': 'OK', 'msg': 'API is "
                    "ready'}"], cm.output)
                mock_test_api.assert_called_with({'allow_all': True})

    @patch('csapi.configure_app', return_value={'log_file': 'LOG_FILE'})
    @patch('csapi.Api')
    def test_create_app(self, mock_api, mock_configure_app):
        mock_api_value = MagicMock()
        mock_api.return_value = mock_api_value
        app = csapi.create_app('CONFIG_FILE')
        mock_configure_app.assert_called_with('CONFIG_FILE')
        self.assertIsInstance(app, csapi.Flask)
        mock_api_value.add_resource.assert_has_calls([
            call(csapi.MemberApi, '/member', resource_class_kwargs={
                'config': {'log_file': 'LOG_FILE'}}),
            call(csapi.SubsystemApi, '/subsystem', resource_class_kwargs={
                'config': {'log_file': 'LOG_FILE'}}),
            call(csapi.StatusApi, '/status', resource_class_kwargs={
                'config': {'log_file': 'LOG_FILE'}})
        ])


class NoConfTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.client = self.app.test_client()
        self.api = Api(self.app)
        self.api.add_resource(csapi.MemberApi, '/member', resource_class_kwargs={
            'config': None})
        self.api.add_resource(csapi.SubsystemApi, '/subsystem', resource_class_kwargs={
            'config': None})

    def test_member_no_conf(self):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            response = self.client.post('/member', data=json.dumps({}))
            self.assertEqual(403, response.status_code)
            self.assertEqual([
                'INFO:csapi:Incoming request: {}',
                'INFO:csapi:Client DN: None',
                'ERROR:csapi:FORBIDDEN: Client certificate is not allowed: None',
                "INFO:csapi:Response: {'http_status': 403, 'code': 'FORBIDDEN', 'msg': "
                "'Client certificate is not allowed: None'}"], cm.output)

    def test_subsystem_no_conf(self):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            response = self.client.post('/subsystem', data=json.dumps({}))
            self.assertEqual(403, response.status_code)
            self.assertEqual([
                'INFO:csapi:Incoming request: {}',
                'INFO:csapi:Client DN: None',
                'ERROR:csapi:FORBIDDEN: Client certificate is not allowed: None',
                "INFO:csapi:Response: {'http_status': 403, 'code': 'FORBIDDEN', 'msg': "
                "'Client certificate is not allowed: None'}"], cm.output)


if __name__ == '__main__':
    unittest.main()
