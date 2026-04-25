# `secrets/dev` - SOPS+age secrets for the `dev` channel

## Per-channel age model (Q4 lock, 2026-04-25)

The `dev` channel has its own age key. Other channels, when added, get their own keys. This isolates secret access per channel and enables per-channel rotation.

## Custody

- Public recipient: committed in `.sops.yaml`
- Private key: `~/.config/sops/age/dev.txt` on the operator machine, never committed
- SOPS key lookup: `SOPS_AGE_KEY_FILE=~/.config/sops/age/dev.txt`

## Add a channel

1. `mkdir -p ~/.config/sops/age && age-keygen -o ~/.config/sops/age/<channel>.txt`
2. `age-keygen -y ~/.config/sops/age/<channel>.txt`
3. `mkdir -p gitops/secrets/<channel>`
4. Write `gitops/secrets/<channel>/.sops.yaml` with the public recipient.
5. Encrypt secrets: `sops --encrypt --age <recipient> --in-place gitops/secrets/<channel>/<file>.enc.yaml`

## Remove a channel

1. `git rm -r gitops/secrets/<channel>`
2. Optionally delete `~/.config/sops/age/<channel>.txt` on the operator machine.
3. Remove the channel overlay so Flux prunes reconciled resources through `prune: true`.

## Rotate a recipient

1. `age-keygen -o ~/.config/sops/age/<channel>-new.txt`
2. `age-keygen -y ~/.config/sops/age/<channel>-new.txt`
3. Add the new public recipient to `.sops.yaml` alongside the old recipient.
4. `find gitops/secrets/<channel> -name '*.enc.yaml' | xargs -I{} sops updatekeys {}`
5. Remove the old recipient from `.sops.yaml`.
6. `find gitops/secrets/<channel> -name '*.enc.yaml' | xargs -I{} sops updatekeys {}`
7. Replace the old private key with the new one locally.

## Verification

`bash gitops/tests/validate_gitops.sh --sops-only` runs:

- `.sops.yaml` exists for each channel under `gitops/secrets/`
- `.sops.yaml` lists at least one age recipient matching `age1[a-z0-9]{58}`
- Placeholder recipients are reported as `PLACEHOLDER` and do not fail validation
- For each real `*.enc.yaml`, SOPS metadata exists
- `sops --decrypt` succeeds when `sops`, `age`, a real recipient, and the local private key are present

If `sops` or `age` is missing, decrypt verification is reported as `SKIPPED`. Tool installation is owned by `gitops/scripts/install-tools.sh`.
