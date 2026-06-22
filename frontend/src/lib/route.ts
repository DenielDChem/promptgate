// Tiny hash/query route reader for the auth gate. Supports:
//   ?invite=<token>            (query string)
//   #/register?invite=<token>  (hash route)
// Returns the invite token if present, else null.

export function readInviteToken(): string | null {
  const fromQuery = new URLSearchParams(window.location.search).get('invite');
  if (fromQuery) return fromQuery;

  const hash = window.location.hash; // e.g. "#/register?invite=abc"
  const qIdx = hash.indexOf('?');
  if (qIdx === -1) return null;
  return new URLSearchParams(hash.slice(qIdx + 1)).get('invite');
}

/** True when the hash route explicitly targets registration. */
export function isRegisterRoute(): boolean {
  return window.location.hash.startsWith('#/register');
}

/** Strip auth params from the URL after a successful login/registration. */
export function clearAuthUrl(): void {
  const url = new URL(window.location.href);
  url.search = '';
  url.hash = '';
  window.history.replaceState({}, '', url.toString());
}
