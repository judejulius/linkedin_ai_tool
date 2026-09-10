"""LinkedIn refresh-token exchange; caller holds the scheduler process lock."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from urllib import request, error, parse


class AuthenticationError(RuntimeError):
    """Authentication failed before a post could be accepted."""


def access_token(force=False, cache_path=None):
    path = cache_path or Path(os.getenv('DATA_DIR', str(Path(__file__).resolve().parent / 'data'))) / 'linkedin_tokens.json'
    refresh = os.getenv('LINKEDIN_REFRESH_TOKEN') or os.getenv('REFRESH_TOKEN', '')
    initial = os.getenv('LINKEDIN_ACCESS_TOKEN', '')
    client_id = os.getenv('LINKEDIN_CLIENT_ID', '')
    secret = os.getenv('LINKEDIN_CLIENT_SECRET', '')
    fingerprint = hashlib.sha256(json.dumps([initial, refresh, client_id, secret]).encode()).hexdigest()
    state = {}
    try:
        if path.exists():
            state = json.loads(path.read_text())
            if state.get('source') != fingerprint:
                state = {}
        now = time.time()
        if not force and state.get('access_token') and state.get('expires_at', 0) > now + 300:
            return state['access_token']
        if not refresh:
            if initial and not force:
                return initial
            raise AuthenticationError('LinkedIn access token rejected or missing; configure a refresh token or reauthorize.')
        if not client_id or not secret:
            raise AuthenticationError('Refresh requires LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET from the issuing app.')
        if state.get('refresh_expires_at', float('inf')) <= now:
            raise AuthenticationError('LinkedIn refresh token expired; reauthorize and replace the tokens in .env.')
        refresh = state.get('refresh_token') or refresh
        req = request.Request('https://www.linkedin.com/oauth/v2/accessToken',
            data=parse.urlencode({'grant_type': 'refresh_token', 'refresh_token': refresh,
                                 'client_id': client_id, 'client_secret': secret}).encode(),
            headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
        with request.urlopen(req, timeout=30) as response:
            result = json.load(response)
        token = result.get('access_token')
        ttl = int(result.get('expires_in', 0))
        if not isinstance(token, str) or not token or ttl <= 0:
            raise AuthenticationError('LinkedIn returned an invalid token response.')
        new_state = {'source': fingerprint, 'access_token': token,
                     'expires_at': now + ttl,
                     'refresh_token': result.get('refresh_token') or refresh}
        if 'refresh_token_expires_in' in result:
            new_state['refresh_expires_at'] = now + int(result['refresh_token_expires_in'])
        elif 'refresh_expires_at' in state:
            new_state['refresh_expires_at'] = state['refresh_expires_at']
        path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replacement, with owner-only permissions from mkstemp.
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.tokens-')
        try:
            with os.fdopen(fd, 'w') as handle:
                json.dump(new_state, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return token
    except AuthenticationError:
        raise
    except error.HTTPError as exc:
        raise AuthenticationError(f'LinkedIn token refresh HTTP {exc.code}; check app credentials or reauthorize.') from None
    except Exception:
        raise AuthenticationError('LinkedIn token refresh or cache update failed; no post was sent. Retry after checking connectivity and cache permissions.') from None
