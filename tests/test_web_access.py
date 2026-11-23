"""Hosted authentication must protect the full studio, including proxy-local clients."""
import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import phone


class HostedAccess(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'FASTCLIPPING_WEB': '1',
            'FASTCLIPPING_WEB_USERNAME': 'studio',
            'FASTCLIPPING_WEB_PASSWORD': 'a-long-test-password:with-colon',
            'NEONCLIPPING_LAN': '0',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        app = FastAPI()

        @app.get('/')
        @app.get('/queue')
        @app.get('/assets/app.js')
        @app.get('/media/example')
        @app.post('/upload')
        def protected():
            return {'studio': True}

        phone.attach(app, self.tmp.name, Path(__file__).resolve().parent.parent)
        self.app = app
        self.remote = TestClient(app, client=('203.0.113.10', 40000))
        self.auth = ('studio', 'a-long-test-password:with-colon')

    def test_full_studio_opens_after_sign_in_without_phone_mode(self):
        for path in ('/', '/queue', '/assets/app.js', '/media/example'):
            self.assertEqual(self.remote.get(path).status_code, 401, path)
            self.assertEqual(self.remote.get(path, auth=self.auth).status_code, 200, path)
        self.assertEqual(self.remote.post('/upload').status_code, 401)
        self.assertEqual(self.remote.post('/upload', auth=self.auth).status_code, 200)

    def test_local_reverse_proxy_does_not_bypass_authentication(self):
        for host in ('127.0.0.1', '::1'):
            local = TestClient(self.app, client=(host, 40001))
            self.assertEqual(local.get('/').status_code, 401)
            self.assertEqual(local.get('/', auth=self.auth).status_code, 200)

    def test_invalid_or_malformed_credentials_return_browser_challenge(self):
        malformed = base64.b64encode(b'no-colon').decode()
        invalid_utf8 = base64.b64encode(b'\xff:password').decode()
        for header in ('', 'Bearer token', 'Basic ???', 'Basic '+malformed, 'Basic '+invalid_utf8):
            response = self.remote.get('/', headers={'Authorization': header})
            self.assertEqual(response.status_code, 401)
            self.assertIn('Basic realm="fastclipping"', response.headers['www-authenticate'])
        for auth in (('wrong', self.auth[1]), ('studio', 'wrong'), ('wrong', 'wrong')):
            self.assertEqual(self.remote.get('/', auth=auth).status_code, 401)

    def test_missing_or_weak_configuration_fails_closed_even_on_loopback(self):
        local = TestClient(self.app, client=('127.0.0.1', 40001))
        for change in ({'FASTCLIPPING_WEB_USERNAME': ''}, {'FASTCLIPPING_WEB_PASSWORD': ''},
                       {'FASTCLIPPING_WEB_PASSWORD': 'short'}, {'FASTCLIPPING_WEB_USERNAME': 'bad:name'}):
            with patch.dict(os.environ, change):
                self.assertEqual(self.remote.get('/', auth=self.auth).status_code, 503)
                self.assertEqual(local.get('/').status_code, 503)

    def test_health_probe_has_no_studio_details(self):
        response = self.remote.get('/healthz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True})
        self.assertEqual(self.remote.get('/readiness').status_code, 401)
        self.assertEqual(self.remote.post('/healthz').status_code, 401)

    def test_phone_pin_cannot_replace_hosted_credentials(self):
        self.remote.cookies.set(phone.COOKIE, 'fake-pin-session')
        self.assertEqual(self.remote.get('/queue').status_code, 401)
        self.assertEqual(self.remote.post('/m/login', json={'pin': '123456'}).status_code, 401)

    def test_hosted_mode_does_not_expose_phone_management_to_remote_clients(self):
        self.assertEqual(self.remote.get('/phone/status', auth=self.auth).status_code, 403)
        self.assertEqual(self.remote.post('/phone/newpin', auth=self.auth).status_code, 403)


if __name__ == '__main__':
    unittest.main()
