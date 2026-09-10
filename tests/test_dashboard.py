from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dashboard import create_app
import scheduler


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'journal.sqlite3'
        self.app = create_app({'TESTING': True, 'PASSWORD': 'test-password',
                               'SECRET_KEY': 'test-secret', 'DB_PATH': self.path})
        self.client = self.app.test_client()
        self.auth = {}
        self.client.get('/api/session')
        with self.client.session_transaction() as session:
            csrf = session['csrf']
        self.client.post('/api/login', data={'username': 'admin', 'password': 'test-password', 'csrf': csrf})
        with self.client.session_transaction() as session:
            self.csrf = session['csrf']
        self.db = scheduler.connect(self.path)
        with self.db:
            self.db.execute("INSERT INTO notes(body) VALUES ('Learning about rewards')")
        self.post = scheduler.draft(self.db, '2026-09-10', lambda _: {
            'body': 'I am learning how rewards influence an agent.', 'summary': 'Studying rewards.'})

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def action(self, action, revision=1):
        return self.client.post('/api/posts/2026-09-10/' + action, headers=self.auth,
                                data={'csrf': self.csrf, 'revision': revision})

    def status(self):
        return self.db.execute('SELECT status FROM posts').fetchone()[0]

    def test_auth_and_csrf_required(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get('/api/dashboard').status_code, 401)
        self.assertEqual(self.client.post('/api/posts/2026-09-10/approve', headers=self.auth).status_code, 403)
        self.assertEqual(self.status(), 'draft')

    def test_login_rejects_bad_password_and_requires_csrf(self):
        client = self.app.test_client()
        self.assertEqual(client.get('/api/session').status_code, 200)
        with client.session_transaction() as session:
            csrf = session['csrf']
        self.assertEqual(client.post('/api/login', data={'username': 'admin', 'password': 'test-password'}).status_code, 403)
        response = client.post('/api/login', data={'username': 'admin', 'password': 'wrong', 'csrf': csrf})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn('WWW-Authenticate', response.headers)
        self.assertIn(b'Incorrect username or password', response.data)
        self.assertEqual(client.get('/api/dashboard').status_code, 401)

    def test_logout_requires_post_and_clears_session(self):
        self.assertEqual(self.client.get('/api/logout').status_code, 405)
        self.assertEqual(self.client.post('/api/logout').status_code, 403)
        self.assertEqual(self.client.post('/api/logout', data={'csrf': self.csrf}).status_code, 200)
        self.assertEqual(self.client.get('/api/dashboard').status_code, 401)
        self.assertEqual(self.action('approve').status_code, 401)
        self.assertEqual(self.status(), 'draft')

    def test_static_frontend_and_private_json(self):
        with self.db:
            self.db.execute('UPDATE posts SET body=?', ('<script>alert(1)</script>',))
        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertNotIn(b'{{', page.data)
        self.assertIn(b'/static/app.js', page.data)
        self.assertNotIn(b'alert(1)', page.data)
        data = self.client.get('/api/dashboard').get_json()
        self.assertEqual(data['posts'][0]['body'], '<script>alert(1)</script>')
        script = self.client.get('/static/app.js')
        self.assertIn(b'textContent', script.data)
        self.assertNotIn(b'innerHTML', script.data)
        with self.app.test_client().get('/static/login.css') as css:
            self.assertEqual(css.status_code, 200)
        page.close()
        script.close()

    def test_unapproved_post_cannot_publish(self):
        with self.assertRaises(RuntimeError):
            scheduler.publish(self.db, self.post, sender=lambda _: self.fail())

    def test_schedule_never_publishes(self):
        with patch('scheduler.publish') as publish:
            scheduler.run_day(self.db, '2026-09-10', True)
            publish.assert_not_called()

    def test_approval_publishes_once(self):
        with patch.dict('os.environ', {'LINKEDIN_PERSON_URN': 'urn:li:person:123'}), patch(
                'dashboard.access_token', return_value='token'), patch('scheduler._send_linkedin', return_value='urn:li:share:123') as send, patch(
                'scheduler.access_token', return_value='token'):
            self.assertEqual(self.action('approve').status_code, 200)
            self.assertEqual(self.status(), 'published')
            self.assertEqual(self.action('approve').status_code, 409)
            send.assert_called_once()

    def test_decline_never_publishes_or_consumes_notes(self):
        with patch('scheduler.publish') as publish:
            self.action('decline')
            publish.assert_not_called()
        self.assertEqual(self.status(), 'declined')
        self.assertEqual(self.db.execute('SELECT used FROM notes').fetchone()[0], 0)
        self.assertEqual(self.action('approve', 2).status_code, 409)

    def test_regenerate_invalidates_old_approval(self):
        def writer(ctx):
            self.assertIn(self.post['body'], ctx['discarded_drafts'])
            return {'body': 'A reward can point an agent toward an unexpected shortcut.', 'summary': 'Reward shortcuts.'}
        original = scheduler.draft
        with patch('scheduler.draft', side_effect=lambda db, day, **kw: original(db, day, writer=writer, **kw)):
            self.assertEqual(self.action('regenerate').status_code, 200)
        self.assertEqual(self.db.execute('SELECT revision FROM posts').fetchone()[0], 2)
        self.assertEqual(self.action('approve', 1).status_code, 409)
        self.assertEqual(self.status(), 'draft')

    def test_failed_regeneration_preserves_draft(self):
        def fail(_):
            raise RuntimeError('Generation failed')
        with self.assertRaises(RuntimeError):
            scheduler.draft(self.db, '2026-09-10', writer=fail, regenerate=True)
        current = self.db.execute('SELECT * FROM posts').fetchone()
        self.assertEqual(current['body'], self.post['body'])
        self.assertEqual(current['revision'], 1)

    def test_pending_draft_carries_over(self):
        post = scheduler.draft(self.db, '2026-09-11', writer=lambda _: self.fail())
        self.assertEqual(post['day'], '2026-09-10')
