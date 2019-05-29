#!/usr/bin/env python3

import psycopg2
import re

# Input
MEMBER_CODE = 'XX000001'
MEMBER_NAME = 'XX test'
MEMBER_CLASS = 'GOV'

conf = {
    'username': '',
    'password': '',
    'database': ''
}

with open('/etc/xroad/db.properties', 'r') as dbConf:
    for line in dbConf:
        # Example:
        # username=centerui
        # password=centerui
        # database=centerui_production
        m = re.match('^username\\s*=\\s*(.+)$', line)
        if m:
            conf['username'] = m.group(1)

        m = re.match('^password\\s*=\\s*(.+)$', line)
        if m:
            conf['password'] = m.group(1)

        m = re.match('^database\\s*=\\s*(.+)$', line)
        if m:
            conf['database'] = m.group(1)

if not conf['username'] or not conf['password'] or not conf['database']:
    print('Cannot access password file')
    exit(1)

conn = psycopg2.connect(
    'host={} port={} dbname={} user={} password={}'.format(
        'localhost', '5432', conf['database'], conf['username'], conf['password']))
cur = conn.cursor()

cur.execute("""select exists(select * from security_server_clients where type='XRoadMember' \
    and member_code=%(str)s)""", {'str': MEMBER_CODE})
rec = cur.fetchone()
if rec[0] is True:
    print('Member exists')
    exit(1)

cur.execute("""select id from member_classes where code=%(str)s""", {'str': MEMBER_CLASS})
rec = cur.fetchone()
class_id = None
if rec and len(rec)>0:
    class_id = rec[0]
else:
    print('Member Class ({}) does not exist'.format(MEMBER_CLASS))
    exit(1)

cur.execute("""select current_timestamp at time zone 'UTC'""")
utc_time = cur.fetchone()[0]

cur.execute(
    """insert into identifiers(object_type, xroad_instance, member_class, member_code, type, """
    """created_at, updated_at) """
    """values('MEMBER', (select value from system_parameters where key='instanceIdentifier'), """
    """%(class)s, %(code)s, 'ClientId', %(time)s, %(time)s) returning id""",
    {'class': MEMBER_CLASS, 'code': MEMBER_CODE, 'time': utc_time}
)
identifier_id = cur.fetchone()[0]

cur.execute(
    """insert into security_server_clients"""
    """(member_code, name, member_class_id, server_client_id, type, created_at, updated_at) """
    """values"""
    """(%(code)s, %(name)s, %(class_id)s, %(identifier_id)s, 'XRoadMember', %(time)s, %(time)s)""",
    {
        'code': MEMBER_CODE, 'name': MEMBER_NAME, 'class_id': class_id,
        'identifier_id': identifier_id, 'time': utc_time
    }
)

cur.execute(
    """insert into security_server_client_names(name, client_identifier_id, created_at, """
    """updated_at) values(%(name)s, %(identifier_id)s, %(time)s, %(time)s)""",
    {'name': MEMBER_NAME, 'identifier_id': identifier_id, 'time': utc_time}
)

cur.close()
conn.commit()
conn.close()

print('All done!')
