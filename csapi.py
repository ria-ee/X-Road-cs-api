#!/usr/bin/env python3

"""This is a module for X-Road Central Server API.

This module allows:
    * adding new members to the X-Road Central Server.
"""

import logging
import re
import psycopg2
from flask import request, jsonify
from flask_restful import Resource

DB_CONF_FILE = '/etc/xroad/db.properties'
LOGGER = logging.getLogger('csapi')


def get_db_conf():
    """Get Central Server database configuration parameters"""
    conf = {
        'database': '',
        'username': '',
        'password': ''
    }

    # Getting database credentials from X-Road configuration
    try:
        with open(DB_CONF_FILE, 'r') as db_conf:
            for line in db_conf:
                match_res = re.match('^database\\s*=\\s*(.+)$', line)
                if match_res:
                    conf['database'] = match_res.group(1)

                match_res = re.match('^username\\s*=\\s*(.+)$', line)
                if match_res:
                    conf['username'] = match_res.group(1)

                match_res = re.match('^password\\s*=\\s*(.+)$', line)
                if match_res:
                    conf['password'] = match_res.group(1)
    except IOError:
        pass

    return conf


def get_db_connection(conf):
    """Get connection object for Central Server database"""
    return psycopg2.connect(
        'host={} port={} dbname={} user={} password={}'.format(
            'localhost', '5432', conf['database'], conf['username'], conf['password']))


def get_member_class_id(cur, member_class):
    """Get ID of member class from Central Server"""
    cur.execute("""select id from member_classes where code=%(str)s""", {'str': member_class})
    rec = cur.fetchone()
    if rec:
        return rec[0]
    return None


def member_exists(cur, member_code):
    """Check if member exists in Central Server"""
    cur.execute(
        """
            select exists(
                select * from security_server_clients
                    where type='XRoadMember' and member_code=%(str)s
            )
        """, {'str': member_code})
    rec = cur.fetchone()
    return rec[0]


def get_utc_time(cur):
    """Get current time in UTC timezone from Central Server database"""
    cur.execute("""select current_timestamp at time zone 'UTC'""")
    return cur.fetchone()[0]


def add_identifier(cur, **kwargs):
    """Add new X-Road identifier to Central Server

    Required keyword arguments:
    member_class, member_code, utc_time
    """
    cur.execute(
        """
            insert into identifiers (
                object_type, xroad_instance, member_class, member_code, type, created_at,
                updated_at
            ) values (
                'MEMBER', (select value from system_parameters where key='instanceIdentifier'),
                %(class)s, %(code)s, 'ClientId', %(time)s, %(time)s
            ) returning id
        """, {
            'class': kwargs['member_class'], 'code': kwargs['member_code'],
            'time': kwargs['utc_time']}
    )
    return cur.fetchone()[0]


def add_client(cur, **kwargs):
    """Add new X-Road client to Central Server

    Required keyword arguments:
    member_code, member_name, class_id, identifier_id, utc_time
    """
    cur.execute(
        """
            insert into security_server_clients (
                member_code, name, member_class_id, server_client_id, type, created_at, updated_at
            ) values (
                %(code)s, %(name)s, %(class_id)s, %(identifier_id)s, 'XRoadMember', %(time)s,
                %(time)s
            )
        """, {
            'code': kwargs['member_code'], 'name': kwargs['member_name'],
            'class_id': kwargs['class_id'], 'identifier_id': kwargs['identifier_id'],
            'time': kwargs['utc_time']
        }
    )


def add_client_name(cur, **kwargs):
    """Add new X-Road client name to Central Server

    Required keyword arguments:
    member_name, identifier_id, utc_time
    """
    cur.execute(
        """
            insert into security_server_client_names (
                name, client_identifier_id, created_at, updated_at
            ) values (
                %(name)s, %(identifier_id)s, %(time)s, %(time)s
            )
        """, {
            'name': kwargs['member_name'], 'identifier_id': kwargs['identifier_id'],
            'time': kwargs['utc_time']}
    )


def add_member(member_code, member_name, member_class, json_data):
    """Add new X-Road member to Central Server"""
    conf = get_db_conf()
    if not conf['username'] or not conf['password'] or not conf['database']:
        LOGGER.error('DB_CONF_ERROR: Cannot access database configuration')
        return {
            'http_status': 500, 'code': 'DB_CONF_ERROR',
            'msg': 'Cannot access database configuration'}

    with get_db_connection(conf) as conn:
        with conn.cursor() as cur:
            class_id = get_member_class_id(cur, member_class)
            if class_id is None:
                LOGGER.warning(
                    'INVALID_MEMBER_CLASS: Provided Member Class does not exist '
                    '(Request: %s)', json_data)
                return {
                    'http_status': 400, 'code': 'INVALID_MEMBER_CLASS',
                    'msg': 'Provided Member Class does not exist'}

            if member_exists(cur, member_code):
                LOGGER.warning(
                    'MEMBER_EXISTS: Provided Member already exists '
                    '(Request: %s)', json_data)
                return {
                    'http_status': 409, 'code': 'MEMBER_EXISTS',
                    'msg': 'Provided Member already exists'}

            # Timestamps must be in UTC timezone
            utc_time = get_utc_time(cur)

            identifier_id = add_identifier(
                cur, member_class=member_class, member_code=member_code, utc_time=utc_time)

            add_client(
                cur, member_code=member_code, member_name=member_name, class_id=class_id,
                identifier_id=identifier_id, utc_time=utc_time)

            add_client_name(
                cur, member_name=member_name, identifier_id=identifier_id, utc_time=utc_time)

        conn.commit()

    LOGGER.info(
        'Added new member: member_code=%s, member_name=%s, member_class=%s',
        member_code, member_name, member_class)

    return {'http_status': 201, 'code': 'CREATED', 'msg': 'New member added'}


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
            'msg': 'Request parameter {} is missing'.format(param_name)}

    return param, None


class MemberApi(Resource):
    """Member API class for Flask"""
    @staticmethod
    def post():
        """POST method"""
        json_data = request.get_json(force=True)

        LOGGER.info('Incoming request: %s', json_data)

        (member_code, fault_response) = get_input(json_data, 'member_code')
        if member_code is None:
            return make_response(fault_response)

        (member_name, fault_response) = get_input(json_data, 'member_name')
        if member_name is None:
            return make_response(fault_response)

        (member_class, fault_response) = get_input(json_data, 'member_class')
        if member_class is None:
            return make_response(fault_response)

        try:
            response = add_member(member_code, member_name, member_class, json_data)
        except psycopg2.Error:
            LOGGER.error('DB_ERROR: Unclassified database error')
            response = {
                'http_status': 500, 'code': 'DB_ERROR',
                'msg': 'Unclassified database error'}

        return make_response(response)
