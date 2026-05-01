# RCA: Playwright admin route timeout in test 19

## Symptom

Running `infra/tests/e2e/tests/19-web-ui.sh` against the running
humility-local cluster, the Playwright browser flow at
`infra/tests/e2e/lib/playwright/browser-flow.mjs:84` fails:

```text
locator.waitFor: Timeout 30000ms exceeded.
Call log:
  - waiting for getByRole('heading', { name: 'Chapter administration' }) to be visible
    at Object.assert (.../browser-flow.mjs:84:75)
    at .../browser-flow.mjs:357:16
```

The flow:
1. Navigates to `https://web.local.humility.local/admin/chapters`.
2. Pomerium routes the request through Authentik OAuth
   (officer login).
3. `loginIfNeeded(page)` handles the OAuth round-trip.
4. Page is expected to render `<h1>Chapter administration</h1>`
   (or similar), then the `chapter-table` testid.

## Reproduction

Cluster state was healthy enough to reproduce:

```bash
KUBECONFIG=/home/nes/.kube/humility-local.yaml \
  kubectl --context k3d-humility-local get pods -A
```

Relevant workloads were running:

```text
auth-system    authentik-server-7469d7d749-spg24        1/1 Running
auth-system    pomerium-proxy-5c76994f44-sj2j2          1/1 Running
server-manager server-manager-api-66694bb484-ktn6x      1/1 Running
web            server-manager-web-848fd8f7d5-qm8zh      1/1 Running
```

Exact test-flow reproduction:

```bash
rm -f /tmp/rca-playwright-web-ui.log
infra/tests/e2e/lib/playwright/run-browser-flow.sh \
  web-ui \
  /home/nes/.kube/humility-local.yaml \
  /tmp/rca-playwright-web-ui.log
tail -120 /tmp/rca-playwright-web-ui.log
```

Result:

```text
exit=1
locator.waitFor: Timeout 30000ms exceeded.
Call log:
  - waiting for getByRole('heading', { name: 'Chapter administration' }) to be visible

    at Object.assert (.../infra/tests/e2e/lib/playwright/browser-flow.mjs:84:75)
```

Instrumented browser reproduction with page errors showed the more precise
boundary:

```text
url=https://web.local.humility.local/admin/chapters
bodyLength=0
responses:
302 https://web.local.humility.local/admin/chapters
200 https://web.local.humility.local/admin/chapters
200 https://web.local.humility.local/assets/index-Q4fzm_aT.css
200 https://web.local.humility.local/assets/index-kRgcR9QJ.js
pageerror:
TypeError: Cannot read properties of undefined (reading 'effect')
    at cn (https://web.local.humility.local/assets/index-kRgcR9QJ.js:2:18744)
    at br (https://web.local.humility.local/assets/index-kRgcR9QJ.js:2:33001)
    at Nr (https://web.local.humility.local/assets/index-kRgcR9QJ.js:2:34429)
    at Lr (https://web.local.humility.local/assets/index-kRgcR9QJ.js:2:34765)
    at Ha (https://web.local.humility.local/assets/index-kRgcR9QJ.js:2:78211)
    at du (https://web.local.humility.local/assets/index-kRgcR9QJ.js:2:164697)
```

Source-map lookup for that stack:

```text
2:18744  node_modules/@solidjs/signals/dist/prod.js:1932
2:33001  node_modules/solid-js/dist/solid.js:590
2:34429  services/web/src/solid-compat/solid.ts:77
2:34765  services/web/src/solid-compat/solid.ts:121
2:78211  node_modules/@tanstack/solid-query/build/index.js:20
2:164697 services/web/src/app/providers.tsx:26
```

## Investigation findings

### 1. SPA response on `/admin/chapters`

Unauthenticated host probe through Pomerium redirects to the IdP:

```bash
curl -k -sS -D - -H 'Host: web.local.humility.local' \
  https://localhost/admin/chapters
```

Result excerpt:

```text
HTTP/2 302
location: https://authenticate.local.humility.local/.pomerium/sign_in?...
x-pomerium-intercepted-response: true
```

The web service itself serves the SPA shell for `/admin/chapters`:

```bash
kubectl -n web exec deploy/server-manager-web -- \
  sh -lc 'wget -S -O- http://127.0.0.1:8080/admin/chapters'
```

Result excerpt:

```text
HTTP/1.1 200 OK
<script type="module" crossorigin src="/assets/index-kRgcR9QJ.js"></script>
<div id="root"></div>
```

After OAuth, the browser receives the same SPA shell, CSS, and JS as 200s,
but the DOM body remains empty because the JS bundle throws during bootstrap.

### 2. OAuth flow completion

`loginIfNeeded(page)` is defined in
`infra/tests/e2e/lib/playwright/browser-flow.mjs:305-346`. The helper
detects Authentik/Pomerium URLs, fills `input#ak-identifier-input`, fills
`input#ak-stage-password-input`, and waits until the page leaves Authentik
and Pomerium callback URLs.

The instrumented run showed:

```text
after initial goto: https://auth.local.humility.local/if/flow/default-authentication-flow/?client_id=humility-local-pomerium...
login: complete:2
after login: https://web.local.humility.local/admin/chapters
final url: https://web.local.humility.local/admin/chapters
```

Pomerium logs confirm the authenticated allow:

```text
method="GET" path="/admin/chapters" host="web.local.humility.local"
allow=true allow-why-true=["user-ok"]
email="sample@local.humility.local"
response-code=200
```

Authentik logs also show successful password login and Pomerium app
authorization:

```text
"action": "login", "user": {"email": "sample@local.humility.local", "username": "sample"}
"action": "authorize_application", "authorized_application": {"name": "Pomerium"}
"scopes": "email profile openid"
```

Conclusion: the OAuth round-trip is completing before the timeout.

### 3. Authentik/Pomerium live config

The checked-in Authentik blueprint defines the `pomerium` app/provider and
`discord_user_id` scope mapping at
`gitops/channels/local/auth/authentik/bootstrap-blueprint-configmap.yaml:125-203`.
The checked-in local Pomerium template requests `openid email profile discord_user_id`
and maps `x-pomerium-claim-discord-user-id` at
`gitops/channels/local/auth/pomerium/secrets-infisicalsecret.yaml:31-105`.

The live cluster is behind the checked-in Pomerium template. The live
`InfisicalSecret/pomerium-config` still renders:

```text
idp_scopes: openid email profile
jwt_claims_headers:
  x-pomerium-claim-email: email
  x-pomerium-claim-sub: sub
  x-pomerium-claim-groups: groups
  x-pomerium-claim-name: name
routes:
  - from: https://web.local.humility.local
    prefix: /admin
    pass_identity_headers: true
  - from: https://web.local.humility.local
    prefix: /auth/discord/
  - from: https://web.local.humility.local
    allow_public_unauthenticated_access: true
```

It lacks the checked-in `/api/me`, `/api/web/admin/`, `/api/web/officer/`,
and `discord_user_id` claim-header routes. That drift would break the
admin/officer API calls after the SPA mounted, but it is not the first
failure boundary for this timeout.

### 4. Route registration

`services/web/src/app/router.tsx:91-100` registers the route:

```tsx
const adminChaptersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin/chapters",
  component: AdminChaptersRoute,
  staticData: { breadcrumb: "Admin chapters" },
});
```

The route is included in the route tree at
`services/web/src/app/router.tsx:102-108`.

### 5. Actual rendered heading contract

The source contains the exact accessible text:

```text
services/web/src/features/admin/AdminChaptersRoute.tsx:65:
  <h2 id="admin-title">Chapter administration</h2>
```

`browser-flow.mjs:84` uses `getByRole("heading", { name: "Chapter administration" })`
without constraining heading level, so the `h2` is compatible with the
test assertion. The deployed bundle also contains:

```text
<h2 id=admin-title>Chapter administration</h2>
<div data-testid=chapter-table>
```

Conclusion: the heading text did not drift. It simply never mounts.

### 6. API health for `/api/v1/web/admin/chapters`

Direct API probe inside the API pod with Pomerium-style identity headers:

```bash
kubectl -n server-manager exec deploy/server-manager-api -- sh -lc '
python - <<PY
import urllib.request
req = urllib.request.Request(
  "http://127.0.0.1:8000/api/v1/web/admin/chapters",
  headers={
    "x-pomerium-claim-email": "sample@local.humility.local",
    "x-pomerium-claim-sub": "sample-sub",
    "x-pomerium-claim-name": "Sample",
    "x-pomerium-claim-groups": "officers",
    "x-pomerium-claim-discord-user-id": "210987654321098765",
  },
)
with urllib.request.urlopen(req, timeout=10) as r:
  print(r.status, r.getheader("content-type"))
  print(r.read(500).decode())
PY'
```

Result:

```text
200 application/json
{"chapters":[]}
```

The API endpoint is healthy when identity headers are present.

However, the live web/Pomerium route drift means browser-facing
`/api/web/admin/chapters` currently reaches the API without Pomerium
identity headers. API logs showed:

```text
10.42.1.222 - "GET /api/v1/web/admin/chapters HTTP/1.1" 401 Unauthorized
127.0.0.1 - "GET /api/v1/web/admin/chapters HTTP/1.1" 200 OK
```

The 401 came through the web proxy without identity headers; the 200 was
the direct pod probe with headers.

### 7. Solid compat shim

This is the first failing boundary.

The cluster bundle throws:

```text
TypeError: Cannot read properties of undefined (reading 'effect')
```

The source-map stack identifies this chain:

```text
@tanstack/solid-query/build/index.js:20
services/web/src/solid-compat/solid.ts:121
services/web/src/solid-compat/solid.ts:77
solid-js/dist/solid.js:590
@solidjs/signals/dist/prod.js:1932
```

Relevant source:

```text
services/web/node_modules/@tanstack/solid-query/build/index.js:20:
  createRenderEffect((unmount) => {

services/web/src/solid-compat/solid.ts:120-121:
  if (arguments.length === 1) {
    return createLegacyEffect(effect);

services/web/src/solid-compat/solid.ts:74-78:
  function createLegacyEffect(...) {
    ...
    return solid.createEffect(() => {

services/web/node_modules/@solidjs/signals/dist/prod.js:1931-1932:
  function createEffect(e, t, n) {
    effect(e, t.effect || t, t.error, { user: true, ...n });
```

`@tanstack/solid-query` calls legacy Solid-style `createRenderEffect(fn)`
with one argument. The local compat wrapper routes that one-argument call
through `createLegacyEffect`. `createLegacyEffect` then calls the raw Solid
2 beta `solid.createEffect(...)` with one argument. In Solid 2 beta,
`@solidjs/signals` expects a second effect-handler argument and dereferences
`t.effect`; because `t` is undefined, the bundle throws before the app
children render.

This crash happens in `AppProviders` before `RouterProvider` can mount the
admin route:

```text
services/web/src/app/providers.tsx:26-37:
  <QueryClientProvider client={queryClient}>
    <ThemeRuntime>
      <RouterProvider router={props.router} />
```

### 8. Pomerium/Auth chain timing

The OAuth chain is not the 30-second bottleneck. In the instrumented run,
`loginIfNeeded` completed after two one-second loop attempts and landed on
`https://web.local.humility.local/admin/chapters`. Pomerium returned the
protected page with `200`, and assets loaded with `200`; the timeout is the
later Playwright wait for a heading that never appears because bootstrap
has already crashed.

## Root cause

The root cause is the local Solid 2 compatibility wrapper's legacy effect
path, not route registration, heading text, OAuth timing, or API health.

Specifically:

1. `AppProviders` renders `QueryClientProvider`
   (`services/web/src/app/providers.tsx:26`).
2. `@tanstack/solid-query` calls `createRenderEffect((unmount) => ...)`
   with one argument (`services/web/node_modules/@tanstack/solid-query/build/index.js:20`).
3. The alias routes that call through `services/web/src/solid-compat/solid.ts`.
4. The one-argument `createRenderEffect` path calls `createLegacyEffect`
   (`services/web/src/solid-compat/solid.ts:120-121`).
5. `createLegacyEffect` calls the raw Solid 2 beta `solid.createEffect(...)`
   with one argument (`services/web/src/solid-compat/solid.ts:77`).
6. Solid 2 beta's underlying `@solidjs/signals` implementation dereferences
   the missing second argument as `t.effect`
   (`services/web/node_modules/@solidjs/signals/dist/prod.js:1931-1932`).
7. The thrown `TypeError` aborts SPA bootstrap, leaving `<body>` empty and
   causing `browser-flow.mjs:84` to wait until timeout.

The cluster proves the sequence: after successful OAuth, `/admin/chapters`,
CSS, and JS all return `200`; immediately after the JS loads, the browser
page error is `Cannot read properties of undefined (reading 'effect')`,
and `h1 count`, `h2 count`, and `chapter-table` visibility are all zero.

## Affected surfaces

The exact failure boundary is any real-browser execution of the built web
SPA that enters `AppProviders` with the current Solid 2 beta compat layer.
The first visible assertion hit by `infra/tests/e2e/tests/19-web-ui.sh` is
the admin route heading at `infra/tests/e2e/lib/playwright/browser-flow.mjs:84`.

Because `QueryClientProvider` wraps the whole router, this can block every
test slice that depends on the built SPA after OAuth, including:

- β-i officer queue and claim flow: the browser flow cannot get past the
  initial `/admin/chapters` smoke check before continuing to `/applications`.
- β-ii officer detail/transcript flow: blocked behind the same browser-flow
  start boundary.
- β-iii officer messages/transitions flow: blocked behind the same boundary.
- INIT-134/INIT-135 web UI e2e legs that reuse `19-web-ui.sh` and
  `browser-flow.mjs`: blocked before public submit, queue, detail, message,
  transition, and chapter-selector checks can run.

Secondary affected surface after the bootstrap crash is fixed: the live
Pomerium config currently lacks the checked-in browser API identity-header
routes. That would make `/api/me`, `/api/web/admin/chapters`, and officer
API calls fail through the browser path even though the API itself is
healthy with identity headers.

## NOT proposing fix

This RCA is not proposing or selecting a fix.

Plainly, addressing the root cause would require changing the frontend
runtime compatibility/version story so legacy one-argument Solid effect
calls from the TanStack Solid packages no longer call the raw Solid 2 beta
effect API with a missing effect-handler argument. Separately, the live
Pomerium configuration would need to match the checked-in browser API
identity-header route contract before the later admin/officer API fetches
can pass through the browser.
