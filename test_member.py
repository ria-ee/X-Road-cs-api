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

    @patch('psycopg2.connect')
    def test_get_db_connection(self, mock_pg_connect):
        member.get_db_connection({
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': 'centerui_user'})
        mock_pg_connect.assert_called_with(
            'host=localhost port=5432 dbname=centerui_production user=centerui_user '
            'password=centerui_pass')

    def test_get_member_class_id(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[12345])
        self.assertEqual(12345, member.get_member_class_id(cur, 'MEMBER_CLASS'))
        cur.execute.assert_called_with(
            'select id from member_classes where code=%(str)s', {'str': 'MEMBER_CLASS'})
        cur.fetchone.assert_called_once()

    def test_get_member_class_id_empty(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[])
        self.assertEqual(None, member.get_member_class_id(cur, 'MEMBER_CLASS'))

    def test_get_member_class_id_none(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=None)
        self.assertEqual(None, member.get_member_class_id(cur, 'MEMBER_CLASS'))

    def test_member_exists(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[True])
        self.assertEqual(True, member.member_exists(cur, 'MEMBER_CODE'))
        cur.execute.assert_called_with(
            "\n            select exists(\n                select * from security_server_clients\n"
            "                    where type='XRoadMember' and member_code=%(str)s\n            )\n"
            "        ", {'str': 'MEMBER_CODE'})
        cur.fetchone.assert_called_once()

    def test_get_utc_time(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=['TIME'])
        self.assertEqual('TIME', member.get_utc_time(cur))
        cur.execute.assert_called_with("select current_timestamp at time zone 'UTC'")
        cur.fetchone.assert_called_once()

    def test_add_identifier(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[12345])
        self.assertEqual(12345, member.add_identifier(cur, 'MEMBER_CLASS', 'MEMBER_CODE', 'TIME'))
        cur.execute.assert_called_with(
            "\n            insert into identifiers (\n                object_type, "
            "xroad_instance, member_class, member_code, type, created_at,\n                "
            "updated_at\n            ) values (\n                'MEMBER', "
            "(select value from system_parameters where key='instanceIdentifier'),\n"
            "                %(class)s, %(code)s, 'ClientId', %(time)s, %(time)s\n            ) "
            "returning id\n        ", {
                'class': 'MEMBER_CLASS', 'code': 'MEMBER_CODE', 'time': 'TIME'})
        cur.fetchone.assert_called_once()

    def test_add_client(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        self.assertEqual(None, member.add_client(
            cur, 'MEMBER_CODE', 'MEMBER_NAME', 'CLASS_ID', 'IDENT_ID', 'TIME'))
        cur.execute.assert_called_with(
            "\n            insert into security_server_clients (\n                member_code, "
            "name, member_class_id, server_client_id, type, created_at, updated_at\n            ) "
            "values (\n                %(code)s, %(name)s, %(class_id)s, %(identifier_id)s, "
            "'XRoadMember', %(time)s,\n                %(time)s\n            )\n        ", {
                'code': 'MEMBER_CODE', 'name': 'MEMBER_NAME', 'class_id': 'CLASS_ID',
                'identifier_id': 'IDENT_ID', 'time': 'TIME'})

    def test_add_client_name(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        self.assertEqual(None, member.add_client_name(
            cur, 'MEMBER_NAME', 'IDENT_ID', 'TIME'))
        cur.execute.assert_called_with(
            '\n            insert into security_server_client_names (\n                name, '
            'client_identifier_id, created_at, updated_at\n            ) values (\n'
            '                %(name)s, %(identifier_id)s, %(time)s, %(time)s\n            )\n'
            '        ', {'name': 'MEMBER_NAME', 'identifier_id': 'IDENT_ID', 'time': 'TIME'})

    @patch('member.get_db_connection')
    @patch('member.get_db_conf', return_value={
            'database': '',
            'password': 'centerui_pass',
            'username': 'centerui_user'})
    def test_add_member_no_database(self, mock_get_db_conf, mock_get_db_connection):
        with self.assertLogs(member.logger, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'DB_CONF_ERROR', 'http_status': 500,
                    'msg': 'Cannot access database configuration'},
                member.add_member('MEMBER_CODE', 'MEMBER_NAME', 'MEMBER_CLASS', 'JSON_DATA'))
            self.assertEqual(
                ['ERROR:member:DB_CONF_ERROR: Cannot access database configuration'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_not_called()

    @patch('member.get_db_connection')
    @patch('member.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': '',
            'username': 'centerui_user'})
    def test_add_member_no_password(self, mock_get_db_conf, mock_get_db_connection):
        with self.assertLogs(member.logger, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'DB_CONF_ERROR', 'http_status': 500,
                    'msg': 'Cannot access database configuration'},
                member.add_member('MEMBER_CODE', 'MEMBER_NAME', 'MEMBER_CLASS', 'JSON_DATA'))
            self.assertEqual(
                ['ERROR:member:DB_CONF_ERROR: Cannot access database configuration'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_not_called()

    @patch('member.get_db_connection')
    @patch('member.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': ''})
    def test_add_member_no_username(self, mock_get_db_conf, mock_get_db_connection):
        with self.assertLogs(member.logger, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'DB_CONF_ERROR', 'http_status': 500,
                    'msg': 'Cannot access database configuration'},
                member.add_member('MEMBER_CODE', 'MEMBER_NAME', 'MEMBER_CLASS', 'JSON_DATA'))
            self.assertEqual(
                ['ERROR:member:DB_CONF_ERROR: Cannot access database configuration'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_not_called()

    @patch('member.get_member_class_id', return_value=None)
    @patch('member.get_db_connection')
    @patch('member.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': 'centerui_user'})
    def test_add_member_no_class(
            self, mock_get_db_conf, mock_get_db_connection, mock_get_member_class_id):
        with self.assertLogs(member.logger, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'INVALID_MEMBER_CLASS', 'http_status': 400,
                    'msg': 'Provided Member Class does not exist'},
                member.add_member('MEMBER_CODE', 'MEMBER_NAME', 'MEMBER_CLASS', 'JSON_DATA'))
            self.assertEqual([
                'WARNING:member:INVALID_MEMBER_CLASS: Provided Member Class does not exist '
                '(Request: JSON_DATA)'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_called_with({
                'database': 'centerui_production', 'password': 'centerui_pass',
                'username': 'centerui_user'})
            mock_get_member_class_id.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 'MEMBER_CLASS')

    @patch('member.get_member_class_id', return_value=12345)
    @patch('member.get_db_connection')
    @patch('member.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': 'centerui_user'})
    def test_add_member_member_exists(
            self, mock_get_db_conf, mock_get_db_connection, mock_get_member_class_id):
        with self.assertLogs(member.logger, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'MEMBER_EXISTS', 'http_status': 409,
                    'msg': 'Provided Member already exists'},
                member.add_member('MEMBER_CODE', 'MEMBER_NAME', 'MEMBER_CLASS', 'JSON_DATA'))
            self.assertEqual([
                'WARNING:member:MEMBER_EXISTS: Provided Member already exists (Request: '
                'JSON_DATA)'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_called_with({
                'database': 'centerui_production', 'password': 'centerui_pass',
                'username': 'centerui_user'})
            mock_get_member_class_id.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 'MEMBER_CLASS')

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
                self.assertEqual([
                    "INFO:member:Response: {'http_status': 200, 'code': 'OK', "
                    "'msg': 'All Correct'}"], cm.output)

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
