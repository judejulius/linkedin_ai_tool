import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs

from linkedin_auth import access_token, AuthenticationError
from scheduler import send_linkedin


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'tokens.json'
        self.env = patch.dict(os.environ, {'REFRESH_TOKEN': 'original',
            'LINKEDIN_CLIENT_ID': 'client', 'LINKEDIN_CLIENT_SECRET': 'secret'}, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_exchange_cache_rotation_and_expiry(self):
        def response():
            return io.BytesIO(json.dumps({'access_token': 'new', 'expires_in': 3600,
                'refresh_token': 'rotated', 'refresh_token_expires_in': 7200}).encode())
        with patch('linkedin_auth.request.urlopen', side_effect=lambda *a, **k: response()) as http:
            self.assertEqual(access_token(cache_path=self.path), 'new')
            form = parse_qs(http.call_args.args[0].data.decode())
            self.assertEqual(form['grant_type'], ['refresh_token'])
            self.assertEqual(form['refresh_token'], ['original'])
            self.assertEqual(access_token(cache_path=self.path), 'new')
            self.assertEqual(http.call_count, 1)
            state = json.loads(self.path.read_text())
            state['expires_at'] = 0
            self.path.write_text(json.dumps(state))
            access_token(cache_path=self.path)
            self.assertEqual(parse_qs(http.call_args.args[0].data.decode())['refresh_token'], ['rotated'])
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_missing_client_secret_fails_without_network(self):
        os.environ.pop('LINKEDIN_CLIENT_SECRET')
        with patch('linkedin_auth.request.urlopen') as http:
            with self.assertRaisesRegex(AuthenticationError, 'CLIENT_SECRET'):
                access_token(cache_path=self.path)
            http.assert_not_called()

    def test_refresh_error_does_not_expose_response(self):
        with patch('linkedin_auth.request.urlopen', side_effect=HTTPError('url', 400, 'sensitive token', {}, None)):
            with self.assertRaises(AuthenticationError) as raised:
                access_token(cache_path=self.path)
            self.assertNotIn('sensitive', str(raised.exception))

    def test_401_refreshes_and_retries_once(self):
        with patch('scheduler.access_token', side_effect=['old', 'new']) as token, patch(
                'scheduler._send_linkedin', side_effect=[HTTPError('url', 401, '', {}, None), 'id']) as send:
            self.assertEqual(send_linkedin('post'), 'id')
            token.assert_called_with(force=True)
            self.assertEqual(send.call_count, 2)

    def test_timeout_never_retries_post(self):
        with patch('scheduler.access_token', return_value='token'), patch(
                'scheduler._send_linkedin', side_effect=TimeoutError()) as send:
            with self.assertRaises(TimeoutError):
                send_linkedin('post')
            self.assertEqual(send.call_count, 1)
