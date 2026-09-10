"""Private review dashboard; all mutations share the scheduler's process lock."""
from datetime import datetime, timedelta
import hmac
import os
from pathlib import Path
from contextlib import contextmanager
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, request, session, abort, send_from_directory
import secrets
from linkedin_auth import AuthenticationError, access_token
import scheduler


def create_app(test_config=None):
    load_dotenv(scheduler.ROOT / '.env')
    app = Flask(__name__, static_folder='frontend', static_url_path='/static')
    app.config.update(SECRET_KEY=os.getenv('DASHBOARD_SECRET_KEY'),
        PASSWORD=os.getenv('DASHBOARD_PASSWORD'),
        DB_PATH=Path(os.getenv('DATA_DIR', str(scheduler.DATA))) / 'journal.sqlite3',
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        SESSION_COOKIE_SECURE=os.getenv('DASHBOARD_HTTPS', 'false').lower() == 'true',
        MAX_CONTENT_LENGTH=20000)
    if test_config:
        app.config.update(test_config)
    if not app.config['PASSWORD'] or not app.secret_key:
        raise RuntimeError('Set DASHBOARD_PASSWORD and DASHBOARD_SECRET_KEY in .env before starting.')

    @contextmanager
    def database():
        path = Path(app.config['DB_PATH'])
        with scheduler.locked(path.with_suffix('.lock')):
            db = scheduler.connect(path)
            try:
                yield db
            finally:
                db.close()

    @app.before_request
    def protect():
        if request.endpoint in ('health', 'static', 'index', 'login_page'):
            return
        if request.endpoint not in ('login', 'session_info') and not session.get('authenticated'):
            return {'error': 'Sign in to continue.'}, 401
        if request.method == 'POST':
            if not session.get('csrf') or not hmac.compare_digest(session['csrf'], request.headers.get('X-CSRF-Token', request.form.get('csrf', ''))):
                abort(403)
        session.setdefault('csrf', secrets.token_urlsafe(32))

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; form-action 'self'; frame-ancestors 'none'"
        return response

    @app.get('/healthz')
    def health():
        return {'status': 'ok'}

    @app.get('/login')
    def login_page():
        return send_from_directory(app.static_folder, 'login.html')

    @app.get('/')
    def index():
        return send_from_directory(app.static_folder, 'index.html')

    @app.get('/api/session')
    def session_info():
        return {'authenticated': bool(session.get('authenticated')), 'csrf': session['csrf']}

    @app.post('/api/login')
    def login():
        valid_password = hmac.compare_digest(
            request.form.get('password', '').encode(), app.config['PASSWORD'].encode())
        if request.form.get('username') != 'admin' or not valid_password:
            return {'error': 'Incorrect username or password. Please try again.'}, 401
        session.clear()
        session['authenticated'] = True
        session['csrf'] = secrets.token_urlsafe(32)
        session.permanent = True
        return {'authenticated': True, 'csrf': session['csrf']}

    @app.post('/api/logout')
    def logout():
        session.clear()
        return {'authenticated': False}

    @app.get('/api/dashboard')
    def dashboard_data():
        with database() as db:
            posts = db.execute('SELECT * FROM posts ORDER BY day DESC LIMIT 40').fetchall()
            memory = db.execute("SELECT summary FROM posts WHERE status='published' ORDER BY day DESC LIMIT 1").fetchone()
        return {'posts': [dict(post) for post in posts],
                'memory': memory['summary'] if memory else '',
                'previous_post': scheduler.previous_post(),
                'timezone': os.getenv('TIMEZONE', 'Africa/Johannesburg'),
                'model': os.getenv('OPENAI_MODEL', 'gpt-5.6-luna'),
                'reasoning': os.getenv('OPENAI_REASONING_EFFORT', 'low')}

    @app.post('/api/notes')
    def notes():
        body = request.form.get('body', '').strip()
        if not body or len(body) > 10000:
            abort(400)
        with database() as db, db:
            db.execute('INSERT INTO notes(body) VALUES (?)', (body,))
        return {'message': 'Learning note saved. It will inform your next draft.'}

    @app.post('/api/draft')
    def new_draft():
        with database() as db:
            day = datetime.now(ZoneInfo(os.getenv('TIMEZONE', 'Africa/Johannesburg'))).date().isoformat()
            result = scheduler.draft(db, day)
        if not result:
            message = 'No distinct draft generated this time. Try preparing a draft again.'
        elif result['status'] in ('draft', 'approved'):
            message = 'Draft ready for review.'
        elif result['status'] == 'declined':
            message = 'Today’s draft was declined. Use Generate New on that draft for another version.'
        else:
            message = 'Today’s draft has already been handled. Check its status below.'
        return {'message': message}

    @app.post('/api/posts/<day>/<action>')
    def review(day, action):
        if action not in ('approve', 'decline', 'regenerate'):
            abort(404)
        with database() as db:
            post = db.execute('SELECT * FROM posts WHERE day=?', (day,)).fetchone()
            if not post or str(post['revision']) != request.form.get('revision') or post['status'] not in ('draft', 'approved', 'declined'):
                abort(409, 'This draft has changed or has already been handled. Refresh the dashboard.')
            if action == 'approve':
                if post['status'] not in ('draft', 'approved'):
                    abort(409)
                author = os.getenv('LINKEDIN_PERSON_URN', '')
                if not author.startswith('urn:li:person:') or 'YOUR_' in author:
                    raise RuntimeError('Set your actual LINKEDIN_PERSON_URN in .env.')
                if db.execute("SELECT 1 FROM posts WHERE status='sending'").fetchone():
                    raise RuntimeError('Resolve the uncertain publication before approving another draft.')
                # Preflight before recording approval, so credential failures leave a draft.
                access_token()
                with db:
                    db.execute("UPDATE posts SET status='approved' WHERE day=?", (day,))
                post = db.execute('SELECT * FROM posts WHERE day=?', (day,)).fetchone()
                scheduler.publish(db, post)
                message = 'Published to LinkedIn. Your journey memory is updated.'
            elif action == 'decline':
                with db:
                    db.execute("UPDATE posts SET status='declined', revision=revision+1 WHERE day=?", (day,))
                message = 'Draft declined. Nothing was published. Generate New to try another angle.'
            else:
                # Reject regeneration of old drafts while a newer one awaits review.
                other = db.execute("SELECT 1 FROM posts WHERE day > ?", (day,)).fetchone()
                if other:
                    abort(409, 'Regenerate the latest draft instead.')
                result = scheduler.draft(db, day, regenerate=True)
                message = 'New version ready for review.' if result else 'No distinct draft generated. Your previous version is preserved.'
        return {'message': message}

    @app.errorhandler(Exception)
    def failure(exc):
        from werkzeug.exceptions import HTTPException
        if isinstance(exc, HTTPException):
            return {'error': exc.description}, exc.code
        # API exception bodies may contain private data; never render or log them.
        app.logger.error('Dashboard action failed: %s', type(exc).__name__)
        if request.method == 'GET':
            return {'error': 'Dashboard temporarily busy or unavailable. Try refreshing shortly.'}, 503
        message = str(exc) if isinstance(exc, (AuthenticationError, RuntimeError)) else 'Action failed. Check configuration and publication status before retrying.'
        return {'error': message}, 502

    return app
