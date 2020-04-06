""" CityTest module"""
#pylint: disable=too-few-public-methods
import os
import base64
import sys
import string
import re
import json
import random
import time
import falcon
import jsend
import sentry_sdk
import pygsheets
import redis


class CityTest():
    """CityTest class"""

    def on_post_grant(self, req, resp, data_id):
        #pylint: disable=no-self-use
        """
        on POST grant request
        """
        log_msg = "Unauthorized"
        log_type = "error"
        resp.body = json.dumps(jsend.fail({"message": "Unauthorized"}))
        resp.status = falcon.HTTP_401

        if req.content_length:
            data_json = json.loads(req.stream.read(sys.maxsize))
            verify_response = self.verify(data_id, data_json)
            if verify_response:
                resp.body = json.dumps(jsend.success(verify_response))
                resp.status = falcon.HTTP_200
                log_msg = "Grant "+data_id
                log_type = "info"

        with sentry_sdk.configure_scope() as scope:
            scope.set_extra('data_id', data_id)

        with sentry_sdk.configure_scope() as scope:
            scope.set_extra('response', resp.body)
        sentry_sdk.capture_message(log_msg, log_type)

    def verify(self, data_id, data_json):
        """ verify method """
        if self.is_verified(data_id, data_json):
            payload = json.loads(
                base64.b64decode(os.environ.get('CITYTEST_PAYLOAD_64')).decode('ascii'))
            payload["time"] = time.time()
            token = self.token_create(payload)
            response = {"token": token}
            return response
        return False

    @staticmethod
    def is_verified(data_id, data_json):
        """ is_verified method """
        if data_id and data_json:
            if len(data_id) == 6 and "firstName" in data_json and "lastName" in data_json:

                cred = base64.b64decode(os.environ.get('CITYTEST_SHEET_API_64')).decode('ascii')
                os.environ['CITYTEST_SHEET_API'] = cred

                client = pygsheets.authorize(service_account_env_var='CITYTEST_SHEET_API')

                sheet = client.open_by_key(os.environ['CITYTEST_SHEET'])
                google_sheet = os.environ['CITYTEST_LIST']
                worksheet = sheet.worksheet('title', google_sheet)
                found = worksheet.find(data_id, cols=(1, 1), forceFetch=True)
                if len(found) > 0:
                    pattern = re.compile('[^a-zA-Z]+')
                    row = worksheet.get_row(found[0].row, include_tailing_empty=False)
                    if(pattern.sub('', row[1]).upper() ==
                       pattern.sub('', data_json["firstName"]).upper() and
                       pattern.sub('', row[2]).upper() ==
                       pattern.sub('', data_json["lastName"]).upper()
                       ):
                        return True

                return False
            with sentry_sdk.configure_scope() as scope:
                scope.set_extra('data_json', data_json)
        return False

    @staticmethod
    def token_create(payload=None):
        """ token_create method """
        seq = string.ascii_letters + string.digits
        length = 63
        token = ''.join(random.choice(seq) for i in range(length))
        if token and payload:
            storage = redis.from_url(os.environ.get("REDIS_URL"))
            storage.set('citytest.'+token, json.dumps(payload))
        return token

    def on_post_access(self, _req, resp):
        #pylint: disable=no-self-use
        """
        on POST access request
        """
        resp.body = json.dumps(jsend.fail("Unauthorized"))
        resp.status = falcon.HTTP_401
