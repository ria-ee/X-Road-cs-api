#!/usr/bin/env python3

import logging
import psycopg2
import re
from flask import request, jsonify
from flask_restful import Resource

logger = logging.getLogger('member')


def get_db_conf():
    conf = {
        'database': '',
        'username': '',
        'password': ''
    }

    # Getting database credentials from X-Road configuration
    try:
        with open('/etc/xroad/db.properties', 'r') as dbConf:
            for line in dbConf:
                m = re.match('^database\\s*=\\s*(.+)$', line)
                if m:
                    conf['database'] = m.group(1)

                m = re.match('^username\\s*=\\s*(.+)$', line)
                if m:
                    conf['username'] = m.group(1)

                m = re.match('^password\\s*=\\s*(.+)$', line)
                if m:
                    conf['password'] = m.group(1)
    except IOError:
        pass

    return conf


def get_db_connection(conf):
    return psycopg2.connect(
        'host={} port={} dbname={} user={} password={}'.format(
            'localhost', '5432', conf['database'], conf['username'], conf['password']))


def get_member_class_id(cur, member_class):
    cur.execute("""select id from member_classes where code=%(str)s""", {'str': member_class})
    rec = cur.fetchone()
    if rec and len(rec) > 0:
        return rec[0]
    else:
        return


def member_exists(cur, member_code):
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
    cur.execute("""select current_timestamp at time zone 'UTC'""")
    return cur.fetchone()[0]


def add_identifier(cur, member_class, member_code, utc_time):
    cur.execute(
        """
            insert into identifiers (
                object_type, xroad_instance, member_class, member_code, type, created_at,
                updated_at
            ) values (
                'MEMBER', (select value from system_parameters where key='instanceIdentifier'),
                %(class)s, %(code)s, 'ClientId', %(time)s, %(time)s
            ) returning id
        """, {'class': member_class, 'code': member_code, 'time': utc_time}
    )
    return cur.fetchone()[0]


def add_client(cur, member_code, member_name, class_id, identifier_id, utc_time):
    cur.execute(
        """
            insert into security_server_clients (
                member_code, name, member_class_id, server_client_id, type, created_at, updated_at
            ) values (
                %(code)s, %(name)s, %(class_id)s, %(identifier_id)s, 'XRoadMember', %(time)s,
                %(time)s
            )
        """, {
            'code': member_code, 'name': member_name, 'class_id': class_id,
            'identifier_id': identifier_id, 'time': utc_time
        }
    )


def add_client_name(cur, member_name, identifier_id, utc_time):
    cur.execute(
        """
            insert into security_server_client_names (
                name, client_identifier_id, created_at, updated_at
            ) values (
                %(name)s, %(identifier_id)s, %(time)s, %(time)s
            )
        """, {'name': member_name, 'identifier_id': identifier_id, 'time': utc_time}
    )


def add_member(member_code, member_name, member_class, json_data):
    # Getting database configuration
    conf = get_db_conf()
    if not conf['username'] or not conf['password'] or not conf['database']:
        logger.error('DB_CONF_ERROR: Cannot access database configuration')
        return {
            'http_status': 500, 'code': 'DB_CONF_ERROR',
            'msg': 'Cannot access database configuration'}

    with get_db_connection(conf) as conn:
        with conn.cursor() as cur:
            class_id = get_member_class_id(cur, member_class)
            if class_id is None:
                logger.warning(
                    'INVALID_MEMBER_CLASS: Provided Member Class does not exist (Request: {})'.format(
                        json_data))
                return {
                    'http_status': 400, 'code': 'INVALID_MEMBER_CLASS',
                    'msg': 'Provided Member Class does not exist'}

            if member_exists(cur, member_code):
                logger.warning(
                    'MEMBER_EXISTS: Provided Member already exists (Request: {})'.format(json_data))
                return {
                    'http_status': 409, 'code': 'MEMBER_EXISTS',
                    'msg': 'Provided Member already exists'}

            # Timestamps must be in UTC timezone
            utc_time = get_utc_time(cur)

            identifier_id = add_identifier(cur, member_class, member_code, utc_time)

            add_client(cur, member_code, member_name, class_id, identifier_id, utc_time)

            add_client_name(cur, member_name, identifier_id, utc_time)

        conn.commit()

    logger.info('Added new member: member_code={}, member_name={}, member_class={}'.format(
        member_code, member_name, member_class))

    return {'http_status': 201, 'code': 'CREATED', 'msg': 'New member added'}


def make_response(data):
    response = jsonify({'code': data['code'], 'msg': data['msg']})
    response.status_code = data['http_status']
    logger.info('Response: {}'.format(data))
    return response


def get_input(json_data, param_name):
    try:
        param = json_data[param_name]
    except KeyError:
        logger.warning(
            'MISSING_PARAMETER: Request parameter {} is missing '
            '(Request: {})'.format(param_name, json_data))
        return None, make_response({
            'http_status': 400, 'code': 'MISSING_PARAMETER',
            'msg': 'Request parameter {} is missing'.format(param_name)})

    return param, None


class MemberApi(Resource):
    @staticmethod
    def post():
        json_data = request.get_json(force=True)

        logger.info('Incoming request: {}'.format(json_data))

        (member_code, fault_response) = get_input(json_data, 'member_code')
        if member_code is None:
            return fault_response

        (member_name, fault_response) = get_input(json_data, 'member_name')
        if member_name is None:
            return fault_response

        (member_class, fault_response) = get_input(json_data, 'member_class')
        if member_class is None:
            return fault_response

        try:
            response = add_member(member_code, member_name, member_class, json_data)
        except psycopg2.Error:
            logger.error('DB_ERROR: Unclassified database error')
            response = {
                'http_status': 500, 'code': 'DB_ERROR',
                'msg': 'Unclassified database error'}

        return make_response(response)
