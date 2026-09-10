import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from urllib.error import HTTPError

from scheduler import connect, draft, publish, finalize, similar
from linkedin_auth import AuthenticationError


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = connect(Path(self.tmp.name) / 'journal.db')
        with self.db:
            self.db.execute("INSERT INTO notes(body) VALUES ('Studied reward shaping.')")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def make_post(self):
        post = draft(self.db, '2026-09-10', lambda ctx: {
            'body': 'Reward shaping is the next concept I am exploring.',
            'summary': 'Exploring reward shaping; no experiments claimed.'})
        with self.db:
            self.db.execute("UPDATE posts SET status='approved' WHERE day=?", (post['day'],))
        return self.db.execute('SELECT * FROM posts WHERE day=?', (post['day'],)).fetchone()

    def test_daily_idempotency_and_notes_consumed_only_on_success(self):
        post = self.make_post()
        self.assertEqual(self.db.execute('SELECT used FROM notes').fetchone()[0], 0)
        self.assertEqual(draft(self.db, post['day'], lambda _: self.fail()), post)
        calls = []
        publish(self.db, post, lambda body: calls.append(body) or 'urn:li:share:123')
        post = self.db.execute('SELECT * FROM posts').fetchone()
        publish(self.db, post, lambda _: self.fail())
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.db.execute('SELECT used FROM notes').fetchone()[0], 1)
        def automatic_writer(ctx):
            self.assertEqual(ctx['notes'], [])
            self.assertFalse(ctx['first_return_post'])
            return {'body': 'An evaluation policy can behave differently from a training policy.',
                    'summary': 'Discussed policy evaluation after reward shaping.'}
        self.assertIsNotNone(draft(self.db, '2026-09-11', automatic_writer))

    def test_first_post_uses_ppo_background_without_notes(self):
        with self.db:
            self.db.execute('DELETE FROM notes')
        def writer(ctx):
            self.assertTrue(ctx['first_return_post'])
            self.assertIn('Proximal Policy Optimization', ctx['previous_post'])
            self.assertEqual(ctx['notes'], [])
            return {'body': 'I haven’t posted in a while. Returning to PPO raises a question about reward design.',
                    'summary': 'Returned to posting, introduced reward design.'}
        with patch('scheduler.previous_post', return_value='Proximal Policy Optimization was the topic of my last post.'):
            post = draft(self.db, '2026-09-10', writer)
        self.assertEqual(post['status'], 'draft')
        self.assertEqual(post['note_ids'], '[]')

    def test_ambiguous_send_never_retries(self):
        post = self.make_post()
        def timeout(_):
            raise TimeoutError()
        with self.assertRaises(TimeoutError):
            publish(self.db, post, timeout)
        uncertain = self.db.execute('SELECT * FROM posts').fetchone()
        self.assertEqual(uncertain['status'], 'sending')
        with self.assertRaises(RuntimeError):
            publish(self.db, uncertain, lambda _: self.fail())
        self.assertEqual(self.db.execute('SELECT used FROM notes').fetchone()[0], 0)

    def test_rejected_credentials_leave_draft(self):
        def reject(_):
            raise HTTPError('https://api.linkedin.com', 401, 'Unauthorized', {}, None)
        with self.assertRaises(RuntimeError):
            publish(self.db, self.make_post(), reject)
        self.assertEqual(self.db.execute('SELECT status FROM posts').fetchone()[0], 'draft')

    def test_failed_refresh_leaves_draft(self):
        def reject(_):
            raise AuthenticationError('Refresh failed')
        with self.assertRaises(AuthenticationError):
            publish(self.db, self.make_post(), reject)
        self.assertEqual(self.db.execute('SELECT status FROM posts').fetchone()[0], 'draft')

    def test_memory_and_history_feed_next_draft(self):
        post = self.make_post()
        finalize(self.db, post, '123')
        with self.db:
            self.db.execute("INSERT INTO notes(body) VALUES ('Compared exploration strategies.')")
        def writer(ctx):
            self.assertEqual(ctx['memory'], post['summary'])
            self.assertEqual(ctx['recent_posts'], [post['body']])
            self.assertEqual(len(ctx['notes']), 1)
            return {'body': 'Today I compared different approaches to exploration.', 'summary': 'New memory'}
        self.assertIsNotNone(draft(self.db, '2026-09-11', writer))

    def test_duplicate_rejected(self):
        post = self.make_post()
        finalize(self.db, post, '123')
        with self.db:
            self.db.execute("INSERT INTO notes(body) VALUES ('More reward shaping.')")
        with self.assertRaises(RuntimeError):
            draft(self.db, '2026-09-11', lambda _: dict(post))
        self.assertTrue(similar('Hello, WORLD!', 'hello world'))


if __name__ == '__main__':
    unittest.main()
