# SLICE-007 Phase 5+6 Implementation

## Files Touched

### API

- `migrations/versions/wu-011_members.py`
- `migrations/versions/wu-012_trust.py`
- `services/api/app/contracts/members.py`
- `services/api/app/contracts/trust.py`
- `services/api/app/repositories/members.py`
- `services/api/app/repositories/trust.py`
- `services/api/app/services/members.py`
- `services/api/app/services/trust.py`
- `services/api/app/api/v1/endpoints/members.py`
- `services/api/app/api/v1/endpoints/trust.py`
- `services/api/app/api/v1/router.py`
- `services/api/tests/conftest.py`
- `services/api/tests/test_members.py`
- `services/api/tests/test_trust.py`

### Discord

- `services/discord/app/contracts/onboarding.py`
- `services/discord/app/handlers/onboarding.py`
- `services/discord/app/core/bot.py`
- `services/discord/tests/test_onboarding.py`

## Test Counts

- `cd services/api && uv run pytest tests/ -q`
  - `375 passed, 1 warning in 106.97s`
  - Warning: existing Pydantic deprecation warning in `tests/test_settings.py`.
- `cd services/discord && uv run pytest tests/ -q`
  - `63 passed, 20 warnings in 0.22s`
  - Warnings: existing discord.py deprecation warnings from command registration tests.

## Deviations

- No product-scope deviations from proposal revision 1.
- The trust evaluator accepts both tier mapping rules and the list form used by the contract tests:
  `{"name": "...", "max_score": ...}`. Both are deterministic policy-rule inputs.
- No Discord-visible Tier 3 actions were executed.

## Grep Invariants

### Service actor grant

```text
migrations/versions/wu-012_trust.py:77:            'member-onboarder',
migrations/versions/wu-012_trust.py:80:            '["member.read", "member.write", "trust.read", "trust.write"]'::jsonb,
migrations/versions/wu-012_trust.py:89:            WHERE grantee_id = 'member-onboarder'
migrations/versions/wu-012_trust.py:92:              AND permissions @> '["member.read", "member.write", "trust.read", "trust.write"]'::jsonb
services/discord/app/handlers/onboarding.py:11:    "X-Actor-Id": "member-onboarder",
```

### No hardcoded system actor in member service

```text
$ rg -n "['\"]system['\"]" services/api/app/services/members.py
<no matches>
```

### Aggregate and uniqueness wiring

```text
migrations/versions/wu-011_members.py:37:            name="uq_members__discord_user_id",
services/api/app/repositories/members.py:20:      ON h.aggregate_type = 'member'
services/api/app/repositories/trust.py:20:      ON h.aggregate_type = 'trust_profile'
services/api/app/services/members.py:119:            aggregate_type="member",
services/api/app/services/members.py:207:        aggregate_type="member",
services/api/app/services/trust.py:226:            aggregate_type="trust_profile",
```
