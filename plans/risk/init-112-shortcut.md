# INIT-112 Risk Assessment: Shortcut

Result: LOW

## Assessment

The proposal avoids the common shortcut of treating `ScheduledBackup` existence
as recoverability. The restore drill creates and restores a real backup, then
checks data.

The remaining shortcut risk is leaving k3d volume snapshots as documentation
only. A dedicated script with argument validation and archive output is enough
for INIT-112 because the binding requirement is local control-cluster volume
snapshot capability, not automated retention management for Docker archives.

## Conditions

- Runtime harness must call the restore drill in non-static mode.
- The k3d snapshot script must operate on Docker volumes, not only print
  commands.
- Do not add feature flags or alternate legacy config paths.
