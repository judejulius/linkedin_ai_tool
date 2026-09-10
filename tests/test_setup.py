from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.setup import initialize
import scheduler


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'examples').mkdir()
        (self.root / 'examples/profile.md').write_text('Generic example profile')
        (self.root / '.env.example').write_text('DASHBOARD_PASSWORD=\nDASHBOARD_SECRET_KEY=\n')

    def tearDown(self):
        self.temp.cleanup()

    def test_new_install_generates_private_config(self):
        initialize(self.root)
        env = (self.root / '.env').read_text()
        self.assertNotIn('DASHBOARD_PASSWORD=\n', env)
        self.assertNotIn('DASHBOARD_SECRET_KEY=\n', env)
        self.assertEqual((self.root / '.env').stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.root / 'data/profile.md').read_text(), 'Generic example profile')
        self.assertFalse((self.root / 'data/previous_post.md').exists())

    def test_migrate_preserves_existing_values_and_history(self):
        (self.root / 'profile.md').write_text('My actual profile')
        (self.root / 'previous_post.md').write_text('My actual post')
        (self.root / '.env').write_text('KEEP_ME=original\n')
        initialize(self.root)
        (self.root / 'profile.md').write_text('Changed legacy profile')
        initialize(self.root)
        self.assertEqual((self.root / '.env').read_text(), 'KEEP_ME=original\n')
        self.assertEqual((self.root / 'data/profile.md').read_text(), 'My actual profile')
        self.assertEqual((self.root / 'data/previous_post.md').read_text(), 'My actual post')

    def test_clean_install_does_not_inherit_personal_background(self):
        with patch('scheduler.ROOT', self.root), patch('scheduler.data_dir', return_value=self.root / 'data'):
            self.assertEqual(scheduler.profile_text(), 'Generic example profile')
            self.assertEqual(scheduler.previous_post(), '')
