import {api, session} from './api.js';

const form = document.querySelector('#login-form');
const button = document.querySelector('#submit');
const error = document.querySelector('#error');
function showError(message) {
  error.textContent = message;
  error.hidden = false;
}

try {
  const state = await session();
  if (state.authenticated) window.location.replace('/');
  button.disabled = false;
  button.textContent = 'Sign in';
} catch (problem) {
  showError(problem.message + ' Reload this page to reconnect.');
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  button.disabled = true;
  button.textContent = 'Signing in…';
  error.hidden = true;
  try {
    await api('/api/login', Object.fromEntries(new FormData(form)));
    window.location.replace('/');
  } catch (problem) {
    showError(problem.message);
    button.disabled = false;
    button.textContent = 'Sign in';
  }
});
