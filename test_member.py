import unittest
import member
from flask import Flask, jsonify


class MemberTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_make_response(self):
        with self.app.app_context():
            with self.assertLogs(member.logger, level='INFO') as cm:
                response = member.make_response(
                    {'http_status': 200, 'code': 'OK', 'msg': 'All Correct'})
                self.assertEqual(
                    jsonify({'code': 'OK', 'msg': 'All Correct'}).json,
                    response.json
                )
                self.assertEqual(200, response.status_code)
                self.assertEqual(cm.output, [
                    "INFO:member:Response: {'http_status': 200, 'code': 'OKXXX', "
                    + "'msg': 'All Correct'}"])


if __name__ == '__main__':
    unittest.main()
