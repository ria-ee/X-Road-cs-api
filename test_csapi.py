import io
import json
import unittest
import csapi
import psycopg2
from flask import Flask, jsonify
from flask_restful import Api
from unittest.mock import patch, MagicMock


class MainTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.client = self.app.test_client()
        self.api = Api(self.app)
        self.api.add_resource(csapi.MemberApi, '/member', resource_class_kwargs={
            'config': {'allow_all': True}})
        self.api.add_resource(csapi.SubsystemApi, '/subsystem', resource_class_kwargs={
            'config': {'allow_all': True}})

    @patch('builtins.open', return_value=io.StringIO('''adapter=postgresql
encoding=utf8
username =centerui_user
password = centerui_pass
database= centerui_production
reconnect=true
'''))
    def test_get_db_conf(self, mock_open):
        response = csapi.get_db_conf()
        self.assertEqual({
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': 'centerui_user'}, response)
        mock_open.assert_called_with('/etc/xroad/db.properties', 'r')

    @patch('builtins.open', side_effect=IOError)
    def test_get_db_conf_ioerr(self, mock_open):
        response = csapi.get_db_conf()
        self.assertEqual({'database': '', 'password': '', 'username': ''}, response)
        mock_open.assert_called_with('/etc/xroad/db.properties', 'r')

    @patch('psycopg2.connect')
    def test_get_db_connection(self, mock_pg_connect):
        csapi.get_db_connection({
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
        self.assertEqual(12345, csapi.get_member_class_id(cur, 'MEMBER_CLASS'))
        cur.execute.assert_called_with(
            'select id from member_classes where code=%(str)s', {'str': 'MEMBER_CLASS'})
        cur.fetchone.assert_called_once()

    def test_get_member_class_id_empty(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[])
        self.assertEqual(None, csapi.get_member_class_id(cur, 'MEMBER_CLASS'))

    def test_get_member_class_id_none(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=None)
        self.assertEqual(None, csapi.get_member_class_id(cur, 'MEMBER_CLASS'))

    def test_subsystem_exists(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[True])
        self.assertEqual(True, csapi.subsystem_exists(cur, 123, 'SUBSYSTEM_CODE'))
        cur.execute.assert_called_with(
            "\n            select exists(\n                select * from security_server_clients\n"
            "                where type='Subsystem' and xroad_member_id=%(member_id)s\n"
            "                    and subsystem_code=%(subsystem_code)s\n"
            "            )\n        ", {'member_id': 123, 'subsystem_code': 'SUBSYSTEM_CODE'})
        cur.fetchone.assert_called_once()

    def test_get_member_data(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[1234, 'M_NAME'])
        self.assertEqual(
            {'id': 1234, 'name': 'M_NAME'}, csapi.get_member_data(cur, 123, 'MEMBER_CODE'))
        cur.execute.assert_called_with(
            "\n            select id, name\n            from security_server_clients\n"
            "            where type='XRoadMember' and member_class_id=%(class_id)s\n"
            "                and member_code=%(member_code)s\n"
            "        ", {'class_id': 123, 'member_code': 'MEMBER_CODE'})
        cur.fetchone.assert_called_once()

    def test_get_member_data_no_member(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=None)
        self.assertEqual(None, csapi.get_member_data(cur, 123, 'MEMBER_CODE'))
        cur.execute.assert_called_with(
            "\n            select id, name\n            from security_server_clients\n"
            "            where type='XRoadMember' and member_class_id=%(class_id)s\n"
            "                and member_code=%(member_code)s\n"
            "        ", {'class_id': 123, 'member_code': 'MEMBER_CODE'})
        cur.fetchone.assert_called_once()

    def test_get_utc_time(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=['TIME'])
        self.assertEqual('TIME', csapi.get_utc_time(cur))
        cur.execute.assert_called_with("select current_timestamp at time zone 'UTC'")
        cur.fetchone.assert_called_once()

    def test_add_member_identifier(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[12345])
        self.assertEqual(12345, csapi.add_member_identifier(
            cur, member_class='MEMBER_CLASS', member_code='MEMBER_CODE', utc_time='TIME'))
        cur.execute.assert_called_with(
            "\n            insert into identifiers (\n                object_type, "
            "xroad_instance, member_class, member_code, type, created_at,\n                "
            "updated_at\n            ) values (\n                'MEMBER', "
            "(select value from system_parameters where key='instanceIdentifier'),\n"
            "                %(class)s, %(code)s, 'ClientId', %(time)s, %(time)s\n            ) "
            "returning id\n        ", {
                'class': 'MEMBER_CLASS', 'code': 'MEMBER_CODE', 'time': 'TIME'})
        cur.fetchone.assert_called_once()

    def test_add_subsystem_identifier(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        cur.fetchone = MagicMock(return_value=[12345])
        self.assertEqual(12345, csapi.add_subsystem_identifier(
            cur, member_class='MEMBER_CLASS', member_code='MEMBER_CODE',
            subsystem_code='SUBSYSTEM_CODE', utc_time='TIME'))
        cur.execute.assert_called_with(
            "\n            insert into identifiers (\n                object_type, "
            "xroad_instance, member_class, member_code, subsystem_code, type,\n"
            "                created_at, updated_at\n            ) values (\n"
            "                'SUBSYSTEM', "
            "(select value from system_parameters where key='instanceIdentifier'),\n"
            "                %(class)s, %(member_code)s, %(subsystem_code)s, 'ClientId', %(time)s,"
            " %(time)s\n            ) returning id\n        ", {
                'class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                'subsystem_code': 'SUBSYSTEM_CODE', 'time': 'TIME'})
        cur.fetchone.assert_called_once()

    def test_add_member_client(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        self.assertEqual(None, csapi.add_member_client(
            cur, member_code='MEMBER_CODE', member_name='MEMBER_NAME', class_id='CLASS_ID',
            identifier_id='IDENT_ID', utc_time='TIME'))
        cur.execute.assert_called_with(
            "\n            insert into security_server_clients (\n                member_code, "
            "name, member_class_id, server_client_id, type, created_at, updated_at\n            ) "
            "values (\n                %(code)s, %(name)s, %(class_id)s, %(identifier_id)s, "
            "'XRoadMember', %(time)s,\n                %(time)s\n            )\n        ", {
                'code': 'MEMBER_CODE', 'name': 'MEMBER_NAME', 'class_id': 'CLASS_ID',
                'identifier_id': 'IDENT_ID', 'time': 'TIME'})

    def test_add_subsystem_client(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        self.assertEqual(None, csapi.add_subsystem_client(
            cur, subsystem_code='SUBSYSTEM_CODE', member_id='MEMBER_ID', identifier_id='IDENT_ID',
            utc_time='TIME'))
        cur.execute.assert_called_with(
            "\n            insert into security_server_clients (\n                subsystem_code, "
            "xroad_member_id, server_client_id, type, created_at, updated_at\n            ) "
            "values (\n                %(subsystem_code)s, %(member_id)s, %(identifier_id)s, "
            "'Subsystem', %(time)s,\n                %(time)s\n            )\n        ", {
                'subsystem_code': 'SUBSYSTEM_CODE', 'member_id': 'MEMBER_ID',
                'identifier_id': 'IDENT_ID', 'time': 'TIME'})

    def test_add_client_name(self):
        cur = MagicMock()
        cur.execute = MagicMock()
        self.assertEqual(None, csapi.add_client_name(
            cur, member_name='MEMBER_NAME', identifier_id='IDENT_ID', utc_time='TIME'))
        cur.execute.assert_called_with(
            '\n            insert into security_server_client_names (\n                name, '
            'client_identifier_id, created_at, updated_at\n            ) values (\n'
            '                %(name)s, %(identifier_id)s, %(time)s, %(time)s\n            )\n'
            '        ', {'name': 'MEMBER_NAME', 'identifier_id': 'IDENT_ID', 'time': 'TIME'})

    @patch('csapi.get_db_connection')
    @patch('csapi.get_db_conf', return_value={
            'database': '',
            'password': 'centerui_pass',
            'username': 'centerui_user'})
    def test_add_member_no_database(self, mock_get_db_conf, mock_get_db_connection):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'DB_CONF_ERROR', 'http_status': 500,
                    'msg': 'Cannot access database configuration'},
                csapi.add_member('MEMBER_CLASS', 'MEMBER_CODE', 'MEMBER_NAME', 'JSON_DATA'))
            self.assertEqual(
                ['ERROR:csapi:DB_CONF_ERROR: Cannot access database configuration'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_not_called()

    @patch('csapi.get_db_connection')
    @patch('csapi.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': '',
            'username': 'centerui_user'})
    def test_add_member_no_password(self, mock_get_db_conf, mock_get_db_connection):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'DB_CONF_ERROR', 'http_status': 500,
                    'msg': 'Cannot access database configuration'},
                csapi.add_member('MEMBER_CLASS', 'MEMBER_CODE', 'MEMBER_NAME', 'JSON_DATA'))
            self.assertEqual(
                ['ERROR:csapi:DB_CONF_ERROR: Cannot access database configuration'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_not_called()

    @patch('csapi.get_db_connection')
    @patch('csapi.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': ''})
    def test_add_member_no_username(self, mock_get_db_conf, mock_get_db_connection):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'DB_CONF_ERROR', 'http_status': 500,
                    'msg': 'Cannot access database configuration'},
                csapi.add_member('MEMBER_CLASS', 'MEMBER_CODE', 'MEMBER_NAME', 'JSON_DATA'))
            self.assertEqual(
                ['ERROR:csapi:DB_CONF_ERROR: Cannot access database configuration'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_not_called()

    @patch('csapi.get_member_class_id', return_value=None)
    @patch('csapi.get_db_connection')
    @patch('csapi.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': 'centerui_user'})
    def test_add_member_no_class(
            self, mock_get_db_conf, mock_get_db_connection, mock_get_member_class_id):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'INVALID_MEMBER_CLASS', 'http_status': 400,
                    'msg': 'Provided Member Class does not exist'},
                csapi.add_member('MEMBER_CLASS', 'MEMBER_CODE', 'MEMBER_NAME', 'JSON_DATA'))
            self.assertEqual([
                'WARNING:csapi:INVALID_MEMBER_CLASS: Provided Member Class does not exist '
                '(Request: JSON_DATA)'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_called_with({
                'database': 'centerui_production', 'password': 'centerui_pass',
                'username': 'centerui_user'})
            mock_get_member_class_id.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 'MEMBER_CLASS')

    @patch('csapi.get_member_data', return_value={'id': 111, 'name': 'M_NAME'})
    @patch('csapi.get_member_class_id', return_value=12345)
    @patch('csapi.get_db_connection')
    @patch('csapi.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': 'centerui_user'})
    def test_add_member_member_exists(
            self, mock_get_db_conf, mock_get_db_connection, mock_get_member_class_id,
            mock_get_member_data):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'MEMBER_EXISTS', 'http_status': 409,
                    'msg': 'Provided Member already exists'},
                csapi.add_member('MEMBER_CLASS', 'MEMBER_CODE', 'MEMBER_NAME', 'JSON_DATA'))
            self.assertEqual([
                'WARNING:csapi:MEMBER_EXISTS: Provided Member already exists (Request: '
                'JSON_DATA)'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_called_with({
                'database': 'centerui_production', 'password': 'centerui_pass',
                'username': 'centerui_user'})
            mock_get_member_class_id.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 'MEMBER_CLASS')
            mock_get_member_data.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 12345, 'MEMBER_CODE')

    @patch('csapi.add_client_name')
    @patch('csapi.add_member_client')
    @patch('csapi.add_member_identifier', return_value=123456)
    @patch('csapi.get_utc_time', return_value='TIME')
    @patch('csapi.get_member_data', return_value=None)
    @patch('csapi.get_member_class_id', return_value=12345)
    @patch('csapi.get_db_connection')
    @patch('csapi.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': 'centerui_user'})
    def test_add_member_ok(
            self, mock_get_db_conf, mock_get_db_connection, mock_get_member_class_id,
            mock_get_member_data, mock_get_utc_time, mock_add_member_identifier,
            mock_add_member_client, mock_add_client_name):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'CREATED', 'http_status': 201,
                    'msg': 'New Member added'},
                csapi.add_member('MEMBER_CLASS', 'MEMBER_CODE', 'MEMBER_NAME', 'JSON_DATA'))
            self.assertEqual([
                'INFO:csapi:Added new Member: member_code=MEMBER_CODE, '
                'member_name=MEMBER_NAME, member_class=MEMBER_CLASS'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_called_with({
                'database': 'centerui_production', 'password': 'centerui_pass',
                'username': 'centerui_user'})
            mock_get_member_class_id.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 'MEMBER_CLASS')
            mock_get_member_data.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 12345, 'MEMBER_CODE')
            mock_get_utc_time.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__())
            mock_add_member_identifier.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(),
                member_class='MEMBER_CLASS', member_code='MEMBER_CODE', utc_time='TIME')
            mock_add_member_client.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(),
                member_code='MEMBER_CODE', member_name='MEMBER_NAME', class_id=12345,
                identifier_id=123456, utc_time='TIME')
            mock_add_client_name.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(),
                member_name='MEMBER_NAME', identifier_id=123456, utc_time='TIME')

    @patch('csapi.get_db_connection')
    @patch('csapi.get_db_conf', return_value={
            'database': '',
            'password': 'centerui_pass',
            'username': 'centerui_user'})
    def test_add_subsystem_no_database(self, mock_get_db_conf, mock_get_db_connection):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'DB_CONF_ERROR', 'http_status': 500,
                    'msg': 'Cannot access database configuration'},
                csapi.add_subsystem('MEMBER_CLASS', 'MEMBER_CODE', 'SUBSYSTEM_CODE', 'JSON_DATA'))
            self.assertEqual(
                ['ERROR:csapi:DB_CONF_ERROR: Cannot access database configuration'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_not_called()

    @patch('csapi.get_db_connection')
    @patch('csapi.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': '',
            'username': 'centerui_user'})
    def test_add_subsystem_no_password(self, mock_get_db_conf, mock_get_db_connection):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'DB_CONF_ERROR', 'http_status': 500,
                    'msg': 'Cannot access database configuration'},
                csapi.add_subsystem('MEMBER_CLASS', 'MEMBER_CODE', 'SUBSYSTEM_CODE', 'JSON_DATA'))
            self.assertEqual(
                ['ERROR:csapi:DB_CONF_ERROR: Cannot access database configuration'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_not_called()

    @patch('csapi.get_db_connection')
    @patch('csapi.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': ''})
    def test_add_subsystem_no_username(self, mock_get_db_conf, mock_get_db_connection):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'DB_CONF_ERROR', 'http_status': 500,
                    'msg': 'Cannot access database configuration'},
                csapi.add_subsystem('MEMBER_CLASS', 'MEMBER_CODE', 'SUBSYSTEM_CODE', 'JSON_DATA'))
            self.assertEqual(
                ['ERROR:csapi:DB_CONF_ERROR: Cannot access database configuration'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_not_called()

    @patch('csapi.get_member_class_id', return_value=None)
    @patch('csapi.get_db_connection')
    @patch('csapi.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': 'centerui_user'})
    def test_add_subsystem_no_class(
            self, mock_get_db_conf, mock_get_db_connection, mock_get_member_class_id):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'INVALID_MEMBER_CLASS', 'http_status': 400,
                    'msg': 'Provided Member Class does not exist'},
                csapi.add_subsystem('MEMBER_CLASS', 'MEMBER_CODE', 'SUBSYSTEM_CODE', 'JSON_DATA'))
            self.assertEqual([
                'WARNING:csapi:INVALID_MEMBER_CLASS: Provided Member Class does not exist '
                '(Request: JSON_DATA)'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_called_with({
                'database': 'centerui_production', 'password': 'centerui_pass',
                'username': 'centerui_user'})
            mock_get_member_class_id.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 'MEMBER_CLASS')

    @patch('csapi.get_member_data', return_value=None)
    @patch('csapi.get_member_class_id', return_value=12345)
    @patch('csapi.get_db_connection')
    @patch('csapi.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': 'centerui_user'})
    def test_add_subsystem_member_does_not_exist(
            self, mock_get_db_conf, mock_get_db_connection, mock_get_member_class_id,
            mock_get_member_data):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'INVALID_MEMBER', 'http_status': 400,
                    'msg': 'Provided Member does not exist'},
                csapi.add_subsystem('MEMBER_CLASS', 'MEMBER_CODE', 'SUBSYSTEM_CODE', 'JSON_DATA'))
            self.assertEqual([
                'WARNING:csapi:INVALID_MEMBER: Provided Member does not exist (Request: '
                'JSON_DATA)'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_called_with({
                'database': 'centerui_production', 'password': 'centerui_pass',
                'username': 'centerui_user'})
            mock_get_member_class_id.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 'MEMBER_CLASS')
            mock_get_member_data.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 12345, 'MEMBER_CODE')

    @patch('csapi.subsystem_exists', return_value=True)
    @patch('csapi.get_member_data', return_value={'id': 111, 'name': 'M_NAME'})
    @patch('csapi.get_member_class_id', return_value=12345)
    @patch('csapi.get_db_connection')
    @patch('csapi.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': 'centerui_user'})
    def test_add_member_subsystem_exists(
            self, mock_get_db_conf, mock_get_db_connection, mock_get_member_class_id,
            mock_get_member_data, mock_subsystem_exists):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'SUBSYSTEM_EXISTS', 'http_status': 409,
                    'msg': 'Provided Subsystem already exists'},
                csapi.add_subsystem('MEMBER_CLASS', 'MEMBER_CODE', 'SUBSYSTEM_CODE', 'JSON_DATA'))
            self.assertEqual([
                'WARNING:csapi:SUBSYSTEM_EXISTS: Provided Subsystem already exists (Request: '
                'JSON_DATA)'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_called_with({
                'database': 'centerui_production', 'password': 'centerui_pass',
                'username': 'centerui_user'})
            mock_get_member_class_id.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 'MEMBER_CLASS')
            mock_get_member_data.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 12345, 'MEMBER_CODE')
            mock_subsystem_exists.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 111, 'SUBSYSTEM_CODE')

    @patch('csapi.add_client_name')
    @patch('csapi.add_subsystem_client')
    @patch('csapi.add_subsystem_identifier', return_value=123456)
    @patch('csapi.get_utc_time', return_value='TIME')
    @patch('csapi.subsystem_exists', return_value=False)
    @patch('csapi.get_member_data', return_value={'id': 111, 'name': 'M_NAME'})
    @patch('csapi.get_member_class_id', return_value=12345)
    @patch('csapi.get_db_connection')
    @patch('csapi.get_db_conf', return_value={
            'database': 'centerui_production',
            'password': 'centerui_pass',
            'username': 'centerui_user'})
    def test_add_subsystem_ok(
            self, mock_get_db_conf, mock_get_db_connection, mock_get_member_class_id,
            mock_get_member_data, mock_subsystem_exists, mock_get_utc_time,
            mock_add_subsystem_identifier, mock_add_subsystem_client, mock_add_client_name):
        with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
            self.assertEqual(
                {
                    'code': 'CREATED', 'http_status': 201,
                    'msg': 'New Subsystem added'},
                csapi.add_subsystem('MEMBER_CLASS', 'MEMBER_CODE', 'SUBSYSTEM_CODE', 'JSON_DATA'))
            self.assertEqual([
                'INFO:csapi:Added new Subsystem: member_class=MEMBER_CLASS, '
                'member_code=MEMBER_CODE, subsystem_code=SUBSYSTEM_CODE'], cm.output)
            mock_get_db_conf.assert_called_with()
            mock_get_db_connection.assert_called_with({
                'database': 'centerui_production', 'password': 'centerui_pass',
                'username': 'centerui_user'})
            mock_get_member_class_id.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 'MEMBER_CLASS')
            mock_get_member_data.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 12345, 'MEMBER_CODE')
            mock_subsystem_exists.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(), 111, 'SUBSYSTEM_CODE')
            mock_get_utc_time.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__())
            mock_add_subsystem_identifier.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(),
                member_class='MEMBER_CLASS', member_code='MEMBER_CODE',
                subsystem_code='SUBSYSTEM_CODE', utc_time='TIME')
            mock_add_subsystem_client.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(),
                identifier_id=123456, member_id=111, subsystem_code='SUBSYSTEM_CODE',
                utc_time='TIME')
            mock_add_client_name.assert_called_with(
                mock_get_db_connection().__enter__().cursor().__enter__(),
                member_name='M_NAME', identifier_id=123456, utc_time='TIME')

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

    @patch('csapi.add_member', side_effect=psycopg2.Error('DB_ERROR_MSG'))
    def test_member_db_error_handled(self, mock_add_member):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.post('/member', data=json.dumps({
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                    'member_name': 'MEMBER_NAME'}))
                self.assertEqual(response.status_code, 500)
                self.assertEqual(
                    jsonify({
                        'code': 'DB_ERROR',
                        'msg': 'Unclassified database error'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Incoming request: {'member_class': 'MEMBER_CLASS', "
                    "'member_code': 'MEMBER_CODE', 'member_name': 'MEMBER_NAME'}",
                    'INFO:csapi:Client DN: None',
                    'ERROR:csapi:DB_ERROR: Unclassified database error: DB_ERROR_MSG',
                    "INFO:csapi:Response: {'http_status': 500, 'code': 'DB_ERROR', 'msg': "
                    "'Unclassified database error'}"], cm.output)
                mock_add_member.assert_called_with('MEMBER_CLASS', 'MEMBER_CODE', 'MEMBER_NAME', {
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                    'member_name': 'MEMBER_NAME'})

    @patch('csapi.add_member', return_value={
        'http_status': 200, 'code': 'OK', 'msg': 'All Correct'})
    def test_member_ok_query(self, mock_add_member):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.post('/member', data=json.dumps({
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                    'member_name': 'MEMBER_NAME'}))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    jsonify({
                        'code': 'OK',
                        'msg': 'All Correct'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Incoming request: {'member_class': 'MEMBER_CLASS', "
                    "'member_code': 'MEMBER_CODE', 'member_name': 'MEMBER_NAME'}",
                    'INFO:csapi:Client DN: None',
                    "INFO:csapi:Response: {'http_status': 200, 'code': 'OK', 'msg': 'All "
                    "Correct'}"], cm.output)
                mock_add_member.assert_called_with('MEMBER_CLASS', 'MEMBER_CODE', 'MEMBER_NAME', {
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                    'member_name': 'MEMBER_NAME'})

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

    @patch('csapi.add_subsystem', side_effect=psycopg2.Error('DB_ERROR_MSG'))
    def test_subsystem_db_error_handled(self, mock_add_member):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.post('/subsystem', data=json.dumps({
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                    'subsystem_code': 'SUBSYSTEM_CODE'}))
                self.assertEqual(response.status_code, 500)
                self.assertEqual(
                    jsonify({
                        'code': 'DB_ERROR',
                        'msg': 'Unclassified database error'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Incoming request: {'member_class': 'MEMBER_CLASS', "
                    "'member_code': 'MEMBER_CODE', 'subsystem_code': 'SUBSYSTEM_CODE'}",
                    'INFO:csapi:Client DN: None',
                    'ERROR:csapi:DB_ERROR: Unclassified database error: DB_ERROR_MSG',
                    "INFO:csapi:Response: {'http_status': 500, 'code': 'DB_ERROR', 'msg': "
                    "'Unclassified database error'}"], cm.output)
                mock_add_member.assert_called_with(
                    'MEMBER_CLASS', 'MEMBER_CODE', 'SUBSYSTEM_CODE', {
                        'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                        'subsystem_code': 'SUBSYSTEM_CODE'})

    @patch('csapi.add_subsystem', return_value={
        'http_status': 200, 'code': 'OK', 'msg': 'All Correct'})
    def test_subsystem_ok_query(self, mock_add_subsystem):
        with self.app.app_context():
            with self.assertLogs(csapi.LOGGER, level='INFO') as cm:
                response = self.client.post('/subsystem', data=json.dumps({
                    'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                    'subsystem_code': 'SUBSYSTEM_CODE'}))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    jsonify({
                        'code': 'OK',
                        'msg': 'All Correct'}).json,
                    response.json
                )
                self.assertEqual([
                    "INFO:csapi:Incoming request: {'member_class': 'MEMBER_CLASS', "
                    "'member_code': 'MEMBER_CODE', 'subsystem_code': 'SUBSYSTEM_CODE'}",
                    'INFO:csapi:Client DN: None',
                    "INFO:csapi:Response: {'http_status': 200, 'code': 'OK', 'msg': 'All "
                    "Correct'}"], cm.output)
                mock_add_subsystem.assert_called_with(
                    'MEMBER_CLASS', 'MEMBER_CODE','SUBSYSTEM_CODE', {
                        'member_class': 'MEMBER_CLASS', 'member_code': 'MEMBER_CODE',
                        'subsystem_code': 'SUBSYSTEM_CODE'})


if __name__ == '__main__':
    unittest.main()
