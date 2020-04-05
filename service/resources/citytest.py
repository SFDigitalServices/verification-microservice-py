""" CityTest module"""
#pylint: disable=too-few-public-methods
import sys
import string
import json
import random
import falcon
import jsend
import sentry_sdk

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
            payload = 'test'
            token = self.token_create(payload)
            response = {"token": token}
            return response
        return False

    @staticmethod
    def is_verified(data_id, data_json):
        """ is_verified method """
        if data_id and data_json:
            if len(data_id) == 6:
                return True
        return False

    @staticmethod
    def token_create(payload=None):
        """ token_create method """
        seq = string.ascii_letters + string.digits
        length = 63
        token = ''.join(random.choice(seq) for i in range(length))
        if payload:
            pass
        return token

    def on_post_access(self, _req, resp):
        #pylint: disable=no-self-use
        """
        on POST access request
        """
        resp.body = json.dumps(jsend.fail("Unauthorized"))
        resp.status = falcon.HTTP_401
