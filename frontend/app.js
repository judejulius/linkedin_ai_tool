import {api, session} from './api.js';

let busy = false;
const notice = document.querySelector('#notice');
function message(text) {
  notice.textContent = text;
  notice.hidden = false;
}
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll('button').forEach(button => { button.disabled = value; });
}

async function refresh() {
  const data = await api('/api/dashboard');
  document.querySelector('#timezone').textContent = data.timezone;
  document.querySelector('#previous').textContent = data.previous_post || 'No previous post added. The AI will start from your writing profile.';
  document.querySelector('#memory').textContent = data.memory || 'Your running summary will appear after your first approved post is published.';
  document.querySelector('#model').textContent = `Private review dashboard · ${data.model} · ${data.reasoning} reasoning`;
  const container = document.querySelector('#posts');
  container.replaceChildren();
  for (const post of data.posts) {
    const card = element('article', 'card');
    const meta = element('div', 'meta');
    meta.append(element('span', '', `${post.day} · Version ${post.revision}`));
    meta.append(element('span', 'badge', ['draft', 'approved'].includes(post.status) ? 'Awaiting review' : post.status));
    card.append(meta, element('div', 'post', post.body));
    if (['draft', 'approved', 'declined'].includes(post.status)) {
      const actions = element('div', 'actions');
      for (const [action, label, css] of [
        ['approve', 'Approve & publish', 'primary'],
        ['decline', 'Decline', 'decline'],
        ['regenerate', 'Generate New', ''],
      ]) {
        if (post.status === 'declined' && action !== 'regenerate') continue;
        const button = element('button', css, label);
        button.addEventListener('click', () => perform(`/api/posts/${encodeURIComponent(post.day)}/${action}`, {revision: post.revision}));
        actions.append(button);
      }
      card.append(actions);
    } else if (post.status === 'sending') {
      card.append(element('p', 'muted', 'Publication is uncertain. Check your LinkedIn feed and use the recovery command in the README before retrying.'));
    } else if (post.status === 'published') {
      card.append(element('small', '', 'Published successfully · Journey memory updated'));
    }
    container.append(card);
  }
  if (!data.posts.length) container.append(element('div', 'card empty', 'No drafts yet. Prepare your first draft now, or let the AI create one at 8 p.m. No notes needed.'));
}

async function perform(path, values = {}) {
  if (busy) return;
  setBusy(true);
  message('Working on your request. This may take a moment…');
  try {
    const result = await api(path, values);
    if (path === '/api/logout') {
      window.location.replace('/login');
      return;
    }
    message(result.message);
  } catch (problem) {
    message(problem.message);
  } finally {
    if (path !== '/api/logout') {
      try { await refresh(); } catch (problem) { message(problem.message); }
    }
    setBusy(false);
  }
}

document.querySelector('#prepare').addEventListener('click', () => perform('/api/draft'));
document.querySelector('#logout').addEventListener('click', () => perform('/api/logout'));
document.querySelector('#refresh').addEventListener('click', async () => {
  if (busy) return;
  setBusy(true);
  try { await refresh(); } catch (problem) { message(problem.message); }
  finally { setBusy(false); }
});

try {
  const state = await session();
  if (!state.authenticated) {
    window.location.replace('/login');
  } else {
    await refresh();
    setBusy(false);
  }
} catch (problem) {
  message(problem.message + ' Reload this page to reconnect.');
}
