# Synthesis: Parser Verification Needs

## Context

P0041 requires verifying that the `bot-activity` argparse subparser
wiring implemented in P0040 is correct. This is a verification partition,
not a new feature partition.

## Mapping research to needs

### 1. Parser correctness

The research confirms all four parser elements (subcommand name,
positional `bot_id`, optional `--per-channel-limit`, `set_defaults`)
match the proposal specification exactly. No gaps exist between the
proposal and the implementation.

### 2. Argument validation

The research confirms `type=int` on both arguments provides parse-time
rejection of non-integer input. The handler-level validation
(`per_channel_limit > 0`) is a separate concern implemented in the
handler body, not the parser. The parser's responsibility is type
coercion and default assignment, both of which are correct.

### 3. Placement

The research confirms the subparser block is placed after the `read`
subparser and before `return parser`, consistent with the hookpoint
analysis. No reordering is needed.

### 4. No gaps identified

The parser wiring is complete and correct. No additional arguments,
type changes, default adjustments, or structural modifications are
needed. The verification pass confirms the implementation matches the
proposal with zero deviations.

## Summary

This is a no-change verification. The `bot-activity` parser wiring
implemented in P0040 fully satisfies the proposal requirements. No
action is needed beyond documenting the verification.
