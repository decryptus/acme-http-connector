# Copyright 2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the real HTTP client; payloads and credentials are synthetic."""
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from requests import HTTPError
from acme_http_connector import HTTPConnector


class RedirectTests(unittest.TestCase):
    def server(self, status, location=None):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def handle_request(self):
                received.append((self.path, self.rfile.read(
                    int(self.headers.get('Content-Length', 0)))))
                self.send_response(status)
                if location:
                    self.send_header('Location', location)
                self.send_header('Content-Length', '0')
                self.end_headers()

            do_POST = do_PUT = do_PATCH = do_DELETE = do_GET = handle_request

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def close():
            server.shutdown()
            thread.join(2)
            server.server_close()

        self.addCleanup(close)
        return 'http://127.0.0.1:%s' % server.server_port, received

    def test_all_phases_reject_redirects_without_forwarding(self):
        target, forwarded = self.server(200)
        # Includes a redirect without Location and one with a different origin.
        for code in (300, 301, 302, 303, 304, 307, 308):
            source, received = self.server(code, None if code == 304 else target)
            connector = HTTPConnector({phase: {'uri': source, 'timeout': 2}
                                       for phase in ('perform', 'cleanup', 'deploy')})
            for operation, args in ((connector.publish, ('/challenge', 'AUTHORIZATION')),
                                    (connector.cleanup, ('/challenge',)),
                                    (connector.deploy, ('example.invalid', 'CERT', 'DUMMY-KEY'))):
                with self.subTest(code=code, phase=operation.__name__):
                    with self.assertRaises(HTTPError) as caught:
                        operation(*args)
                    self.assertNotIn('DUMMY-KEY', str(caught.exception))
                    self.assertNotIn(target, str(caught.exception))
            self.assertEqual(len(received), 3)
        self.assertEqual(forwarded, [])

    def test_direct_success_and_http_failure(self):
        for code in (200, 201, 204, 400, 500):
            source, received = self.server(code)
            connector = HTTPConnector({'deploy': {'uri': source, 'timeout': 2}})
            with self.subTest(code=code):
                if code >= 400:
                    with self.assertRaises(HTTPError):
                        connector.deploy('example.invalid', 'CERT', 'DUMMY-KEY')
                else:
                    connector.deploy('example.invalid', 'CERT', 'DUMMY-KEY')
                self.assertEqual(len(received), 1)
