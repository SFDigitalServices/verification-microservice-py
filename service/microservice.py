"""Main application module"""
import os
import json
import jsend
import sentry_sdk
import falcon
from .components.cors import CORSComponent
from .resources.welcome import Welcome
from .resources.citytest import CityTest

def start_service():
    """Start this service
    set SENTRY_DSN environmental variable to enable logging with Sentry
    """
    # Initialize Sentry
    sentry_sdk.init(
        os.environ.get('SENTRY_DSN'),
        environment=os.environ.get('environment')
    )
    # Initialize Falcon
    api = falcon.API(middleware=[CORSComponent()])
    api.add_route('/welcome', Welcome())
    api.add_route('/citytest/grant/{data_id}', CityTest(), suffix='grant')
    api.add_route('/citytest/access', CityTest(), suffix='access')
    api.add_route('/citytest', CityTest())
    api.add_sink(default_error, '')
    return api

def default_error(_req, resp):
    """Handle default error"""
    resp.status = falcon.HTTP_404
    msg_error = jsend.error('404 - Not Found')

    sentry_sdk.capture_message(msg_error)
    resp.body = json.dumps(msg_error)
