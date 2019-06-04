import io
import json
import unittest
import member
import psycopg2
from flask import Flask, jsonify
from flask_restful import Api
from unittest.mock import patch, mock_open, MagicMock


class MemberTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.client = self.app.test_client()
        self.api = Api(self.app)
        self.api.add_resource(member.MemberApi, '/member')

    @patch('builtins.open', return_value=io.StringIO('''adapter=postgresql
encoding=utf8
username =centerui_user
password = centerui_pass
database= centerui_production
reconnect=true
'''))
    def test_get_db_conf(self, mock_open):
        response = member.get_db_conf()
        self.assertEqual({
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': 'centerui_user'}, response)
        mock_open.assert_called_with('/etc/xroad/db.properties', 'r')

    @patch('builtins.open', side_effect=IOError)
    def test_get_db_conf_ioerr(self, mock_open):
        response = member.get_db_conf()
        self.assertEqual({'database': '', 'password': '', 'username': ''}, response)
        mock_open.assert_called_with('/etc/xroad/db.properties', 'r')

    def test_make_response(self):
        with self.app.app_context():
            with self.assertLogs(member.logger, level='INFO') as cm:
                response = member.make_response(
                    {'http_status': 200, 'code': 'OK', 'msg': 'All Correct'})
                self.assertEqual(200, response.status_code)
                self.assertEqual(
                    jsonify({'code': 'OK', 'msg': 'All Correct'}).json,
                    response.json
                )
                self.assertEqual(cm.output, [
                    "INFO:member:Response: {'http_status': 200, 'code': 'OK', "
                    + "'msg': 'All Correct'}"])

    def test_get_input(self):
        (value, err) = member.get_input(
            {'member_name': 'MEMBER_NAME', 'member_class': 'MEMBER_CLASS'},
            'member_name')
        self.assertEqual('MEMBER_NAME', value)
        self.assertEqual(None, err)

    def test_get_input_err(self):
        with self.assertLogs(member.logger, level='INFO') as cm:
            (value, err) = member.get_input(
                {'member_name': 'MEMBER_NAME', 'member_class': 'MEMBER_CLASS'},
                'member_code')
            self.assertEqual(None, value)
            self.assertEqual({
                'code': 'MISSING_PARAMETER', 'http_status': 400,
                'msg': 'Request parameter member_code is missing'}, err)
            self.assertEqual([
                'WARNING:member:MISSING_PARAMETER: Request parameter member_code is missing '
                "(Request: {'member_name': 'MEMBER_NAME', 'member_class': 'MEMBER_CLASS'})"],
                cm.output)

    def test_empty_query(self):
        with self.assertLogs(member.logger, level='INFO') as cm:
            response = self.client.post('/member', data=json.dumps({}))
            self.assertEqual(400, response.status_code)
            # Not testing response content, it does not come from application
            self.assertEqual([
                'INFO:member:Incoming request: {}',
                'WARNING:member:MISSING_PARAMETER: Request parameter member_code is missing '
                '(Request: {})',
                "INFO:member:Response: {'http_status': 400, 'code': 'MISSING_PARAMETER', "
                "'msg': 'Request parameter member_code is missing'}"], cm.output)

    def test_empty_member_code_query(self):
        with self.app.app_context():
            with self.assertLogs(member.logger, level='INFO') as cm:
                response = self.client.post('/member', data=json.dumps(
                    {'member_name': 'MEMBER_NAME', 'member_class': 'MEMBER_CLASS'}))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    jsonify({
                        'code': 'MISSING_PARAMETER',
                        'msg': 'Request parameter member_code is missing'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:member:Incoming request: {'member_name': 'MEMBER_NAME', 'member_class': "
                    "'MEMBER_CLASS'}",
                    'WARNING:member:MISSING_PARAMETER: Request parameter member_code is missing '
                    "(Request: {'member_name': 'MEMBER_NAME', 'member_class': 'MEMBER_CLASS'})",
                    "INFO:member:Response: {'http_status': 400, 'code': 'MISSING_PARAMETER', "
                    "'msg': 'Request parameter member_code is missing'}"], cm.output)

    def test_empty_member_name_query(self):
        with self.app.app_context():
            with self.assertLogs(member.logger, level='INFO') as cm:
                response = self.client.post('/member', data=json.dumps(
                    {'member_code': 'MEMBER_CODE', 'member_class': 'MEMBER_CLASS'}))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    jsonify({
                        'code': 'MISSING_PARAMETER',
                        'msg': 'Request parameter member_name is missing'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:member:Incoming request: {'member_code': 'MEMBER_CODE', 'member_class': "
                    "'MEMBER_CLASS'}",
                    'WARNING:member:MISSING_PARAMETER: Request parameter member_name is missing '
                    "(Request: {'member_code': 'MEMBER_CODE', 'member_class': 'MEMBER_CLASS'})",
                    "INFO:member:Response: {'http_status': 400, 'code': 'MISSING_PARAMETER', "
                    "'msg': 'Request parameter member_name is missing'}"], cm.output)

    def test_empty_member_class_query(self):
        with self.app.app_context():
            with self.assertLogs(member.logger, level='INFO') as cm:
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
                    "INFO:member:Incoming request: {'member_code': 'MEMBER_CODE', 'member_name': "
                    "'MEMBER_NAME'}",
                    'WARNING:member:MISSING_PARAMETER: Request parameter member_class is missing '
                    "(Request: {'member_code': 'MEMBER_CODE', 'member_name': 'MEMBER_NAME'})",
                    "INFO:member:Response: {'http_status': 400, 'code': 'MISSING_PARAMETER', "
                    "'msg': 'Request parameter member_class is missing'}"], cm.output)

    @patch('member.add_member', side_effect=psycopg2.Error)
    def test_db_error_handled(self, mock_add_member):
        with self.app.app_context():
            with self.assertLogs(member.logger, level='INFO') as cm:
                response = self.client.post('/member', data=json.dumps({
                    'member_code': 'MEMBER_CODE', 'member_name': 'MEMBER_NAME',
                    'member_class': 'MEMBER_CLASS'}))
                self.assertEqual(response.status_code, 500)
                self.assertEqual(
                    jsonify({
                        'code': 'DB_ERROR',
                        'msg': 'Unclassified database error'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:member:Incoming request: {'member_code': 'MEMBER_CODE', 'member_name': "
                    "'MEMBER_NAME', 'member_class': 'MEMBER_CLASS'}",
                    'ERROR:member:DB_ERROR: Unclassified database error',
                    "INFO:member:Response: {'http_status': 500, 'code': 'DB_ERROR', 'msg': "
                    "'Unclassified database error'}"], cm.output)
                mock_add_member.assert_called_with('MEMBER_CODE', 'MEMBER_NAME', 'MEMBER_CLASS', {
                    'member_code': 'MEMBER_CODE', 'member_name': 'MEMBER_NAME',
                    'member_class': 'MEMBER_CLASS'})

    @patch('member.add_member', return_value={
        'http_status': 200, 'code': 'OK', 'msg': 'All Correct'})
    def test_ok_query(self, mock_add_member):
        with self.app.app_context():
            with self.assertLogs(member.logger, level='INFO') as cm:
                response = self.client.post('/member', data=json.dumps({
                    'member_code': 'MEMBER_CODE', 'member_name': 'MEMBER_NAME',
                    'member_class': 'MEMBER_CLASS'}))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    jsonify({
                        'code': 'OK',
                        'msg': 'All Correct'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:member:Incoming request: {'member_code': 'MEMBER_CODE', 'member_name': "
                    "'MEMBER_NAME', 'member_class': 'MEMBER_CLASS'}",
                    "INFO:member:Response: {'http_status': 200, 'code': 'OK', 'msg': 'All "
                    "Correct'}"], cm.output)
                mock_add_member.assert_called_with('MEMBER_CODE', 'MEMBER_NAME', 'MEMBER_CLASS', {
                    'member_code': 'MEMBER_CODE', 'member_name': 'MEMBER_NAME',
                    'member_class': 'MEMBER_CLASS'})


if __name__ == '__main__':
    unittest.main()
