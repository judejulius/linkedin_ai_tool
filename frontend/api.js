// Same-origin cookies keep credentials out of JavaScript storage.
let csrf = '';

export async function api(path, values) {
  const options = {credentials: 'same-origin', headers: {Accept: 'application/json'}};
  if (values !== undefined) {
    options.method = 'POST';
    options.headers['X-CSRF-Token'] = csrf;
    options.body = new URLSearchParams(values);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    // Never retry a mutation automatically, especially publication.
    throw new Error('Connection interrupted. Refresh to check the draft status before trying again.');
  }
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 401 && path !== '/api/login') window.location.assign('/login');
    throw new Error(result.error || 'The request could not be completed.');
  }
  if (result.csrf) csrf = result.csrf;
  return result;
}

export function session() {
  return api('/api/session');
}
