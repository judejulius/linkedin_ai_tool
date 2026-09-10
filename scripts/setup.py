"""Create private local configuration without overwriting existing files."""
from pathlib import Path
import os
import secrets

ROOT = Path(__file__).resolve().parents[1]


def initialize(root=ROOT):
    data = root / 'data'
    data.mkdir(exist_ok=True, mode=0o700)
    env = root / '.env'
    if not env.exists():
        content = (root / '.env.example').read_text()
        content = content.replace('DASHBOARD_SECRET_KEY=\n', f'DASHBOARD_SECRET_KEY={secrets.token_hex(32)}\n')
        content = content.replace('DASHBOARD_PASSWORD=\n', f'DASHBOARD_PASSWORD={secrets.token_urlsafe(24)}\n')
        with env.open('x') as handle:
            os.chmod(env, 0o600)
            handle.write(content)
    for name in ('profile.md', 'previous_post.md'):
        destination = data / name
        if destination.exists():
            continue
        legacy = root / name
        source = legacy if legacy.exists() else root / 'examples' / name
        if source.exists():
            with destination.open('x') as handle:
                os.chmod(destination, 0o600)
                handle.write(source.read_text())
    print('Local configuration ready. Existing files were preserved.')
    print('Set API credentials in .env. Your dashboard password is stored there.')
    print('Personalize data/profile.md once; daily notes are not required.')


if __name__ == '__main__':
    initialize()
