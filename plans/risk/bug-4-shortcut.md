# BUG-4 — Shortcut risk gate (local gitserver resync)

**Verdict:** LOW

Source: `proposals/20-bug-4-gitserver-resync.md`,
`research/33-bug-4-flux-gitserver-rca.md`,
`infra/scripts/install-flux-for-channel.sh`,
`infra/scripts/bring-up-local-channel.sh`.

## C1 — Reseed actually renders + force-pushes a real snapshot, not just a SHA bump

**Pass.**

The proposal locks the reseed mechanism on the existing renderer plus the
existing seed function, end-to-end. There is no hand-edit-the-SHA path.

Q3 (proposal lines 60-75) is explicit:

> Lock: yes, preserve the snapshot marker, generated CRs, and OPAL policy
> files by rendering a complete snapshot through the existing
> `infra/scripts/render-gitops-source.py`.
> The reseed path must not manually copy selected manifests.

Substrate (lines 138-149) wires that into the script:

> Render `SNAPSHOT_DIR="${REPO_ROOT}/.tmp/gitops-source/${CHANNEL_ID}"` using
> `render-gitops-source.py`.
> Apply `gitops/sources/local/git-daemon.yaml`, wait for the git-daemon
> Deployment, reseed `/srv/git/humility-local.git`, apply generated source
> CRs, and wait for the GitRepository.

The actual write surface — `seed_git_daemon`
(`infra/scripts/install-flux-for-channel.sh:168-205`) — already does a real
synthetic-commit force-push:

- `tar` the rendered `SNAPSHOT_DIR` into the running `git-daemon` container.
- `git init --initial-branch=main` in `/tmp/humility-gitops-seed`.
- `git add -A && git commit -m 'seed local gitops snapshot'`.
- `git push --force origin main` to `/srv/git/humility-${CHANNEL_ID}.git`.
- `git --git-dir=… update-server-info`.

Reusing this function (Q3 + substrate) means the reseed path produces a
genuine new commit object with a new tree, not a SHA pointer change. The
gitserver bare repo is on a PVC and the on-disk objects must change for the
artifact revision to advance.

TG-1 (lines 170-193) closes the loop with an externally-visible check:

- Record `status.artifact.revision` before the reseed.
- Run `bring-up-local-channel.sh --channel local --reseed-gitserver-only`.
- Acceptance: artifact revision is a *new* SHA, **explicitly not**
  `main@sha1:5d872983c9d8d2b708023f185682dbecadcfc2d4` and **not**
  abbreviated as `5d872983`. `GitRepository/humility-local` is `Ready=True`.

The "not 5d872983" assertion guards against the exact shortcut this gate is
checking for: an implementation that updates a Flux setting or annotation
without producing a new artifact would still report the old SHA and would
fail the test.

The anti-scope reinforces it (line 285):

> Do not hand-copy selected manifests into the bare repo.

## C2 — New flag reuses existing helpers, not a parallel reimplementation

**Pass.**

The proposal explicitly enumerates the helpers to reuse and they all already
exist in `install-flux-for-channel.sh`. This is a thread-through-existing-code
plan, not a fork.

Substrate (lines 138-149) lists the reuse contract directly:

> Reuse existing helpers where possible: channel resolution, `kubectl_cmd`,
> `git_daemon_pod`, `wait_for_git_daemon`, `seed_git_daemon`,
> `apply_source_crs`, and `wait_for_source_reconciliation`.

Cross-referencing against the existing script confirms each one is present:

| Helper | Location |
|---|---|
| `kubectl_cmd` | `install-flux-for-channel.sh:119-121` |
| `git_daemon_pod` | `install-flux-for-channel.sh:140-145` |
| `wait_for_git_daemon` | `install-flux-for-channel.sh:147-166` |
| `seed_git_daemon` | `install-flux-for-channel.sh:168-205` |
| `apply_source_crs` | `install-flux-for-channel.sh:221-225` |
| `wait_for_source_reconciliation` | `install-flux-for-channel.sh:241-249` |
| Channel resolution (`json_field`, `RESOLVED_JSON`) | `install-flux-for-channel.sh:83-117, 451-471` |

In `bring-up-local-channel.sh`, the proposal (lines 129-136) keeps the
existing flag-parsing and contract-validation flow intact and only adds:

- one new arg case for `--reseed-gitserver-only`
- mutual-exclusion against `--force`, `--repair`, `--cluster-only`
- a delegate call into `install-flux-for-channel.sh --reseed-gitserver-only`
- "Do not create, delete, repair, or recreate the k3d cluster in this mode."

That preserves `verify_kubectl_reachability` / `verify_cluster_contract` /
kubeconfig matching as gating preconditions for the new mode rather than
duplicating them.

The diff budget (lines 290-303) matches the reuse claim:

> `bring-up-local-channel.sh`: small flag parsing and one reseed-only
> branch, roughly 30-60 changed lines.
> `install-flux-for-channel.sh`: reseed-only flag plus an early mode branch
> that reuses existing helper functions, roughly 40-90 changed lines.
> Total target: under 230 changed lines. Any implementation that needs new
> manifests, new services, CI, GitHub credentials, or broad bootstrap
> rewrites is outside this proposal and should fail risk review.

Under-230 with helper reuse is structurally inconsistent with a parallel
reimplementation; a duplicated seed function alone (currently ~38 lines) plus
matching wait/apply helpers would push the diff well past that ceiling.

The anti-scope (lines 277-288) also blocks the most likely
parallel-implementation escape hatches: no new GitHub-to-gitserver mirror,
no CronJob, no controller, no standalone script.

## C3 — `infra/README.md` gets a real documentation update, not a TODO

**Pass.**

The documentation deliverable is concrete and graded by an explicit test
gate, not a TODO/"document later."

Substrate (lines 152-160) defines the doc body, not just its existence:

> Add a "Narrow local GitOps reseed" subsection under "GitOps Substrate".
> Document when to use the flag: an existing local cluster whose in-cluster
> gitserver is stale relative to the desired checkout.
> Document the exact command, TG-1 revision check, explicit resume patch,
> reconcile watch, and representative manifest checks.
> State that this is not a full bootstrap and does not directly mutate
> Pomerium or Authentik secrets.

TG-4 (lines 263-274) makes the doc a hard acceptance criterion, not a soft
follow-up:

- `infra/README.md` documents `bring-up-local-channel.sh
  --reseed-gitserver-only`.
- The docs explain that local Flux follows the in-cluster gitserver, not
  GitHub.
- The docs include the artifact revision check, the explicit resume patch,
  and the reconcile/watch commands.
- "Future operators can perform this recovery without re-running full
  bootstrap or re-deriving the gitserver PVC/exec workflow from the RCA."

The last bullet is the honest test: a future operator must be able to act
from the README without re-reading the RCA. That excludes a stub like
"see proposal 20" or "TODO: write up reseed mode."

The diff budget (line 298) sizes it as "one focused operator subsection,
roughly 40-80 changed lines" — large enough for the named contents (when to
use, exact command, TG-1 verification, resume patch, reconcile/watch,
representative checks) and far past a placeholder.

## C4 — No "skip OPAL/Cedar files for now" stubs

**Pass.**

Q3 (lines 64-75) names the snapshot contents that must be present and
explicitly includes the policy/Cedar/marker pieces this check exists to
protect:

> the in-cluster synthetic repo contains:
> - the `gitops/` tree;
> - the `policy/` tree;
> - generated Cedar policy files and `.manifest`;
> - generated `gitops/sources/local/{gitrepository.yaml,kustomization.yaml}`;
> - `gitops/channels/local/generated/gitops-snapshot-marker.yaml`.
> This keeps Flux, OPAL policy materialization, and the snapshot sentinel
> aligned with the established local GitOps shape.

The mechanism is structurally complete-by-default rather than
opt-in-per-file: `render-gitops-source.py` produces the entire snapshot
tree, and `seed_git_daemon` tars the whole `SNAPSHOT_DIR`
(`install-flux-for-channel.sh:187-188`) — there is no per-file allowlist or
denylist in either the renderer call or the seed step where a "skip OPAL"
shortcut could land.

Anti-scope (line 285) reinforces this from the other direction:

> Do not hand-copy selected manifests into the bare repo.

That rules out a "render only what changed" or "seed just the
api-deployment" shortcut.

TG-3 (lines 228-261) verifies the resumed cluster actually contains the
new manifests after Flux applies the new artifact:

- `Deployment/server-manager/server-manager-api` contains
  `WEB_PUBLIC_BASE_URL` and the INIT-134 Discord env vars.
- The e2e fixture runtime secret surface contains the expected five keys
  including the INIT-134 additions.
- INIT-135 Pomerium routes for public chapter intake and officer review
  reach the cluster.
- INIT-135 identity forwarding includes `discord_user_id` where defined.

INIT-134 fixture keys and INIT-135 Pomerium routes are exactly the
content categories the RCA flagged as missing
(`research/33-bug-4-flux-gitserver-rca.md:148-178`). A reseed that quietly
omitted those families would fail TG-3 even if TG-1 (artifact SHA advanced)
passed.

Note: the snapshot marker (`gitops-snapshot-marker.yaml`) is named in Q3
but TG-3 does not directly assert the new marker hash. That is an
implementation-phase nicety to consider, not a shortcut blocker — the marker
is part of the rendered tree and the tar+seed flow includes it by
construction; TG-1's "not 5d872983" check plus TG-3's INIT-134/135 manifest
checks are sufficient evidence the marker advanced.

## Findings worth carrying into implementation

Not blockers — the shortcut review is LOW — but the implementation phase
should preserve them:

1. **Don't drift `seed_git_daemon` into a per-file copy.** The shortcut
   risk is highest if someone "optimizes" the seed to avoid re-tarring the
   whole tree. The current implementation force-pushes a fresh synthetic
   commit over `main`, which is how Flux's source-controller notices a new
   artifact. A diff-only or selective-overwrite path would silently break
   the snapshot shape (OPAL `.manifest`, Cedar files, snapshot marker).
   Preserve the tar+commit+force-push contract.

2. **`--reseed-gitserver-only` must early-exit before the bootstrap chain.**
   The existing `main()` in `install-flux-for-channel.sh:445-500` runs a
   long sequence after `apply_source_crs`/`wait_for_source_reconciliation`
   (Infisical identity/storage/databases/auth/server-manager/CI-CD,
   MinIO refresh, Authentik/Pomerium OIDC bootstrap,
   `wait_for_reconciliation` of the Kustomization). Substrate (lines 56-58)
   names these as forbidden in reseed mode. Implementation must branch out
   of `main()` after the source CRs reconcile and explicitly not call
   `wait_for_reconciliation`, since the Kustomization remains suspended at
   that point. Q4 (lines 78-106) keeps the resume as an explicit operator
   step gated on TG-1.

3. **Mutual exclusion has to be enforced, not just documented.** Substrate
   (lines 44-49) lists `--reseed-gitserver-only` as mutually exclusive with
   `--force`, `--repair`, `--cluster-only`. The existing
   `--force`/`--repair` exclusion check (`bring-up-local-channel.sh:94-96`)
   is the pattern; the implementation should add explicit `die` checks for
   the new combinations rather than relying on argument-parse order to
   short-circuit them.

4. **`REPO_ROOT` resolution is the worktree boundary.** Q5 (lines 108-118)
   notes that `REPO_ROOT` is computed from the script path, so the script
   must be invoked from (or by absolute path inside) the desired worktree.
   The README subsection (TG-4) should call this out so an operator running
   the script from a stale checkout doesn't re-seed the same stale snapshot
   and conclude the flag is broken.

5. **TG-2/TG-3 depend on the explicit resume sequence.** Q4 (lines 78-106)
   keeps the Kustomization resume out of the reseed script. Implementation
   must not "helpfully" patch `spec.suspend: false` inside
   `--reseed-gitserver-only` mode — that would bypass the TG-1 gate and
   defeat the staged-recovery design.

## Verdict

LOW. No shortcuts. The proposal:

- Reseeds via `render-gitops-source.py` + the existing `seed_git_daemon`
  tar/commit/force-push, producing a real new synthetic commit on `main`,
  with TG-1 explicitly rejecting the current `5d872983` SHA as the new
  artifact.
- Reuses the seven named helpers
  (`kubectl_cmd`, `git_daemon_pod`, `wait_for_git_daemon`,
  `seed_git_daemon`, `apply_source_crs`, `wait_for_source_reconciliation`,
  channel resolution) and budgets the diff under 230 lines, structurally
  ruling out a parallel reimplementation.
- Treats `infra/README.md` as a graded TG-4 deliverable with named contents
  (when to use, exact command, TG-1 verification, explicit resume patch,
  reconcile/watch, representative manifest checks), not a TODO.
- Renders a complete snapshot — `gitops/`, `policy/`, generated Cedar
  files + `.manifest`, generated source CRs, snapshot marker — and seeds
  via tar of the whole `SNAPSHOT_DIR`, with anti-scope explicitly forbidding
  hand-copied manifests and TG-3 verifying the INIT-134/INIT-135 content
  families the RCA identified as missing.

SHORTCUT_DONE: plans/risk/bug-4-shortcut.md
