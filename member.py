#!/usr/bin/env python3

import logging
import psycopg2
import re
from flask import request, jsonify
from flask_restful import Resource

logger = logging.getLogger('member')


def add_member(member_code, member_name, member_class, json_data):
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

    if not conf['username'] or not conf['password'] or not conf['database']:
        logger.error('DB_CONF_ERROR: Cannot access database configuration')
        return {
            'http_status': 500, 'code': 'DB_CONF_ERROR',
            'msg': 'Cannot access database configuration'}

    conn = psycopg2.connect(
        'host={} port={} dbname={} user={} password={}'.format(
            'localhost', '5432', conf['database'], conf['username'], conf['password']))
    cur = conn.cursor()

    # Check if Member Class is valid
    cur.execute("""select id from member_classes where code=%(str)s""", {'str': member_class})
    rec = cur.fetchone()
    if rec and len(rec) > 0:
        class_id = rec[0]
    else:
        logger.warn(
            'INVALID_MEMBER_CLASS: Provided Member Class does not exist (Request: {})'.format(
                json_data))
        return {
            'http_status': 400, 'code': 'INVALID_MEMBER_CLASS',
            'msg': 'Provided Member Class does not exist'}

    # Check if Member (Member Code) already exists
    cur.execute(
        """
            select exists(
                select * from security_server_clients
                    where type='XRoadMember' and member_code=%(str)s
            )
        """, {'str': member_code})
    rec = cur.fetchone()
    if rec[0] is True:
        logger.warn(
            'MEMBER_EXISTS: Provided Member already exists (Request: {})'.format(json_data))
        return {
            'http_status': 409, 'code': 'MEMBER_EXISTS',
            'msg': 'Provided Member already exists'}

    # Timestamps must be in UTC timezone
    cur.execute("""select current_timestamp at time zone 'UTC'""")
    utc_time = cur.fetchone()[0]

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
    identifier_id = cur.fetchone()[0]

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

    cur.execute(
        """
            insert into security_server_client_names (
                name, client_identifier_id, created_at, updated_at
            ) values (
                %(name)s, %(identifier_id)s, %(time)s, %(time)s
            )
        """, {'name': member_name, 'identifier_id': identifier_id, 'time': utc_time}
    )

    cur.close()
    conn.commit()
    conn.close()

    logger.info('Added new member: member_code={}, member_name={}, member_class={}'.format(
        member_code, member_name, member_class))

    return {'http_status': 201, 'code': 'CREATED', 'msg': 'New member added'}


def make_response(data):
    response = jsonify({'code': data['code'], 'msg': data['msg']})
    response.status_code = data['http_status']
    logger.info('Response: {}'.format(data))
    return response


class MemberApi(Resource):
    @staticmethod
    def post():
        json_data = request.get_json(force=True)

        logger.info('Incoming request: {}'.format(json_data))

        try:
            member_code = json_data['member_code']
        except KeyError:
            logger.warn(
                'MISSING_PARAMETER: Request parameter member_code is missing '
                '(Request: {})'.format(json_data))
            return make_response({
                'http_status': 400, 'code': 'MISSING_PARAMETER',
                'msg': 'Request parameter member_code is missing'})

        try:
            member_name = json_data['member_name']
        except KeyError:
            logger.warn(
                'MISSING_PARAMETER: Request parameter member_name is missing '
                '(Request: {})'.format(json_data))
            return make_response({
                'http_status': 400, 'code': 'MISSING_PARAMETER',
                'msg': 'Request parameter member_name is missing'})

        try:
            member_class = json_data['member_class']
        except KeyError:
            logger.warn(
                'MISSING_PARAMETER: Request parameter member_class is missing '
                '(Request: {})'.format(json_data))
            return make_response({
                'http_status': 400, 'code': 'MISSING_PARAMETER',
                'msg': 'Request parameter member_class is missing'})

        try:
            response = add_member(member_code, member_name, member_class, json_data)
        except psycopg2.Error:
            logger.error('DB_ERROR: Unclassified database error')
            response = {
                'http_status': 500, 'code': 'DB_ERROR',
                'msg': 'Unclassified database error'}

        return make_response(response)
