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
from io import StringIO
import csv
import requests
import falcon
import jsend
import sentry_sdk
import pygsheets
import redis
from cryptography.fernet import Fernet


class CityTest():
    """CityTest class"""
    TOKEN_LENGTH = 63

    def on_post_grant(self, req, resp, data_id):
        #pylint: disable=no-self-use
        """
        on POST grant request
        """
        log_msg = "Grant Unauthorized"
        log_type = "error"
        #pylint: disable=line-too-long
        resp.body = json.dumps(jsend.fail({"message": "You are not eligible for a test now. Contact your supervisor to check on your eligibility."}))
        resp.status = falcon.HTTP_401

        if req.content_length:
            data_json = json.loads(req.stream.read(sys.maxsize))

            if "workForCity" in data_json and data_json["workForCity"] == "no" and "employer" in data_json and data_json["employer"]:
                payload_response = self.token_payload_create()
                if payload_response:
                    employer = data_json.get("employer", "N/A")
                    resp.body = json.dumps(jsend.success(payload_response))
                    resp.status = falcon.HTTP_200
                    log_msg = "Grant "+employer
                    log_type = "info"

            elif data_id and "firstName" in data_json and "lastName" in data_json:
                if data_json["firstName"] and data_json["lastName"]:
                    resp.body = json.dumps(jsend.fail({"message": "You are not eligible for a test now. You told us your name is "+data_json["firstName"]+" "+data_json["lastName"]+", and your DSW number is "+data_id+". If this information is wrong, go back and enter your info again. Contact your supervisor to check your eligibility."}))

                    if req.get_param("verify_only") == "true":
                        if self.is_verified(data_id, data_json):
                            resp.body = json.dumps(jsend.success({"message": "You are eligible for a test now."}))
                            resp.status = falcon.HTTP_200
                            log_msg = "Verified "+data_id
                            log_type = "info"
                        else:
                            log_msg = "Verification failed"
                            log_type = "error"
                    else:
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
            response = self.token_payload_create()
            return response
        return False

    #pylint: disable=too-many-locals
    def is_verified(self, data_id, data_json):
        """ is_verified method """
        if data_id and data_json:
            if len(data_id) <= 6 and "firstName" in data_json and "lastName" in data_json:
                data_id = data_id.rjust(6, '0')

                return self.verify_via_file(data_id, data_json)

            with sentry_sdk.configure_scope() as scope:
                scope.set_extra('data_json', data_json)
        return False

    def verify_via_google(self, data_id, data_json):
        """ verify_via_google """
        cred = base64.b64decode(os.environ.get('CITYTEST_SHEET_API_64')).decode('ascii')
        os.environ['CITYTEST_SHEET_API'] = cred

        client = pygsheets.authorize(service_account_env_var='CITYTEST_SHEET_API')

        sheet = client.open_by_key(os.environ['CITYTEST_SHEET'])
        google_sheet = os.environ['CITYTEST_LIST']
        worksheet = sheet.worksheet('title', google_sheet)

        row_header = worksheet.get_row(1)
        fn_index = row_header.index('FIRSTNAME')
        ln_index = row_header.index('LASTNAME')
        cols = worksheet.get_col(1)
        indices = [i for i, x in enumerate(cols) if x.rjust(6, '0') == data_id]

        for index in indices:
            row = worksheet.get_row(index+1, include_tailing_empty=False)
            if len(row) > 2 and self.match_row(data_json, row[fn_index], row[ln_index]):
                return True
        return False

    def verify_via_file(self, data_id, data_json):
        """ verify_via_file """
        url = os.environ['CITYTEST_FILE_URL']
        token = os.environ['CITYTEST_FILE_TOKEN']
        req = requests.get(url)
        content = req.content
        fernet = Fernet(token)
        data = fernet.decrypt(content)
        data_csv = data.decode('utf-8-sig')
        csv_reader = csv.reader(StringIO(data_csv), delimiter=',')
        ln_index = 1
        fn_index = 2
        for row in csv_reader:
            if row[0].rjust(6, '0') == data_id:
                if len(row) > 2 and self.match_row(data_json, row[fn_index], row[ln_index]):
                    return True
        return False

    @staticmethod
    def match_row(data_json, fname, lname):
        """ match_row method """
        pattern = re.compile('[^a-zA-Z]+')
        if(pattern.sub('', fname.upper()) ==
           pattern.sub('', data_json["firstName"]).upper() and
           pattern.sub('', lname.upper()) ==
           pattern.sub('', data_json["lastName"]).upper()
           ):
            return True
        return False

    def token_payload_create(self):
        """ token_payload_create """
        payload = json.loads(
            base64.b64decode(os.environ.get('CITYTEST_PAYLOAD_64')).decode('ascii'))
        payload["time"] = time.time()
        token = self.token_create(payload)
        response = {"token": token}
        return response

    def token_create(self, payload=None):
        """ token_create method """
        seq = string.ascii_letters + string.digits
        length = self.TOKEN_LENGTH
        token = ''.join(random.choice(seq) for i in range(length))
        if token and payload:
            storage = redis.from_url(os.environ.get("REDIS_URL"))
            storage.set('citytest.'+token, json.dumps(payload))
        return token

    def token_verify(self, token):
        """ token_create method """
        payload = None
        if token and len(token) == self.TOKEN_LENGTH:
            storage = redis.from_url(os.environ.get("REDIS_URL"))
            payload = storage.get('citytest.'+token)
            if payload:
                payload = json.loads(payload)
                storage.delete('citytest.'+token)
        return payload

    def on_post_access(self, req, resp):
        #pylint: disable=no-self-use
        """
        on POST access request
        """
        log_msg = "Access Unauthorized"
        log_type = "error"
        resp.body = json.dumps(jsend.fail({"message": "Unauthorized"}))
        resp.status = falcon.HTTP_401
        if req.content_length:
            token_json = json.loads(req.stream.read(sys.maxsize))
            if token_json and "token" in token_json:
                payload = self.token_verify(token_json["token"])

                if payload:
                    resp.body = json.dumps(jsend.success(payload))
                    resp.status = falcon.HTTP_200
                    log_msg = "Token Access"
                    log_type = "info"

            with sentry_sdk.configure_scope() as scope:
                scope.set_extra('token_json', token_json)

        with sentry_sdk.configure_scope() as scope:
            scope.set_extra('response', resp.body)
        sentry_sdk.capture_message(log_msg, log_type)
