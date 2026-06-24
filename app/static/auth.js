const AUTH_KEY = "xpander_auth";

function getSession() {
  try {
    const raw = sessionStorage.getItem(AUTH_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveSession(data) {
  sessionStorage.setItem(
    AUTH_KEY,
    JSON.stringify({
      access_token: data.access_token,
      refresh_token: data.refresh_token,
      user_id: data.user_id,
      email: data.email,
      full_name: data.full_name,
    })
  );
}

function displayName(session) {
  if (!session) return "";
  return session.full_name || session.email || "";
}

function updateSessionProfile(data) {
  const current = getSession() || {};
  saveSession({
    ...current,
    user_id: data.user_id ?? current.user_id,
    email: data.email ?? current.email,
    full_name: data.full_name ?? current.full_name,
  });
}

function clearSession() {
  sessionStorage.removeItem(AUTH_KEY);
}

function authHeaders(extra) {
  const session = getSession();
  const headers = { ...(extra || {}) };
  if (session?.access_token) {
    headers.Authorization = "Bearer " + session.access_token;
  }
  return headers;
}

function requireAuth() {
  if (!getSession()?.access_token) {
    window.location.replace("/login.html");
    return false;
  }
  return true;
}

async function authFetch(url, options) {
  const opts = options || {};
  opts.headers = authHeaders(opts.headers);
  const res = await fetch(url, opts);
  if (res.status === 401) {
    clearSession();
    window.location.replace("/login.html");
  }
  return res;
}
