# Ticket Index

## Overview

**Total initiatives:** 7
**Total value slices:** 24
**Total work units:** 78
**Phases:** 5
**Critical path:** SLICE-001 -> SLICE-002 -> SLICE-006 -> SLICE-009 -> SLICE-010 -> SLICE-013 -> SLICE-018 -> SLICE-022

Effort and prototyping values below are copied from `engineering roadmap.md`. For Phase 0 tickets that bundle multiple foundation items, the `Effort` cell lists the mapped roadmap magnitudes in ticket order and the `Prototyping` cell rolls up to `yes`, then `conditional`, then `no`.

## Phase 0: Foundations

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-001 | Persistence and mutation substrate | L-XL; M-L | no | none |
| SLICE-002 | Audit, authority, and policy event substrate | M-L; L; M-L | conditional | SLICE-001 |
| SLICE-003 | Permission and chapter core schemas | L-XL; M-L | yes | SLICE-001, SLICE-002 |
| SLICE-004 | Scheduler and deferred-effects backbone | L-XL; M-L | yes | SLICE-001, SLICE-002 |
| SLICE-005 | Test harness and runtime settings | M | no | none |
| SLICE-006 | API and Discord runtime plumbing | M-L; L-XL | conditional | SLICE-001, SLICE-002, SLICE-005 |

## Phase 1: Governance Foundation

### INIT-001: Governance Infrastructure

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-008 | Scoped authority with enforcement | L | conditional | SLICE-002, SLICE-005 |
| SLICE-009 | Audit trail with causal correlation | M | no | SLICE-002, SLICE-006, SLICE-008 |
| SLICE-010 | Policy versioning with configuration safety | M-L | no | SLICE-002, SLICE-008, SLICE-009 |

### INIT-002: Identity and Trust

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-007 | Member onboarding with initial trust assessment | M-L | no | SLICE-001, SLICE-002, SLICE-005, SLICE-006 |


## Phase 2: Core Operational Workflows

### INIT-001: Governance Infrastructure

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-015 | Configurable operator notifications | M-L | conditional | SLICE-002, SLICE-004, SLICE-006, SLICE-008, SLICE-009, SLICE-010 |
| SLICE-017 | Cross-subsystem operational views | M-L | no | SLICE-004, SLICE-008, SLICE-009, SLICE-014 |

### INIT-002: Identity and Trust

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-016 | Advanced trust management | M-L | no | SLICE-007, SLICE-009, SLICE-010 |

### INIT-003: Case Management

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-011 | Ticket creation and case lifecycle | M-L | no | SLICE-005, SLICE-006, SLICE-008, SLICE-009, SLICE-010 |

### INIT-004: Structured Intake

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-012 | Structured application intake with reviewer ownership | M-L | no | SLICE-005, SLICE-006, SLICE-007, SLICE-008, SLICE-009, SLICE-010 |

### INIT-005: Chapter Operations

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-013 | Chapter provisioning from templates | L-XL | yes | SLICE-003, SLICE-004, SLICE-005, SLICE-006, SLICE-008, SLICE-009, SLICE-010 |

### INIT-006: Permission Management

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-014 | Permission intent and drift detection | XL | yes | SLICE-003, SLICE-006, SLICE-008, SLICE-009 |


## Phase 3: Operational Depth

### INIT-003: Case Management

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-019 | SLA enforcement for tickets | L | conditional | SLICE-004, SLICE-011, SLICE-015 |

### INIT-004: Structured Intake

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-021 | Application interview and waitlist handling | M | no | SLICE-005, SLICE-006, SLICE-012, SLICE-015 |

### INIT-005: Chapter Operations

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-018 | Roster management with role lifecycle | L | conditional | SLICE-003, SLICE-004, SLICE-006, SLICE-008, SLICE-009, SLICE-013 |

### INIT-006: Permission Management

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-020 | Temporary permission management | M-L | no | SLICE-004, SLICE-008, SLICE-009, SLICE-014, SLICE-015 |


## Phase 4: Operational Maturity

### INIT-005: Chapter Operations

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-023 | Chapter governance lifecycle | M-L | no | SLICE-004, SLICE-008, SLICE-009, SLICE-011, SLICE-012, SLICE-013 |
| SLICE-024 | Leadership succession with context transfer | M-L | no | SLICE-008, SLICE-009, SLICE-011, SLICE-012, SLICE-017, SLICE-018, SLICE-023 |

### INIT-007: Activity and Compliance

| Ticket | Name | Effort | Prototyping | Dependencies |
|---|---|---|---|---|
| SLICE-022 | Compliance rule evaluation with evidence | XL | yes | SLICE-004, SLICE-006, SLICE-007, SLICE-008, SLICE-009, SLICE-010, SLICE-013, SLICE-015, SLICE-018 |


## Dependency Graph

```text
SLICE-001 <- none
SLICE-002 <- SLICE-001
SLICE-003 <- SLICE-001, SLICE-002
SLICE-004 <- SLICE-001, SLICE-002
SLICE-005 <- none
SLICE-006 <- SLICE-001, SLICE-002, SLICE-005
SLICE-007 <- SLICE-001, SLICE-002, SLICE-005, SLICE-006
SLICE-008 <- SLICE-002, SLICE-005
SLICE-009 <- SLICE-002, SLICE-006, SLICE-008
SLICE-010 <- SLICE-002, SLICE-008, SLICE-009
SLICE-011 <- SLICE-005, SLICE-006, SLICE-008, SLICE-009, SLICE-010
SLICE-012 <- SLICE-005, SLICE-006, SLICE-007, SLICE-008, SLICE-009, SLICE-010
SLICE-013 <- SLICE-003, SLICE-004, SLICE-005, SLICE-006, SLICE-008, SLICE-009, SLICE-010
SLICE-014 <- SLICE-003, SLICE-006, SLICE-008, SLICE-009
SLICE-015 <- SLICE-002, SLICE-004, SLICE-006, SLICE-008, SLICE-009, SLICE-010
SLICE-016 <- SLICE-007, SLICE-009, SLICE-010
SLICE-017 <- SLICE-004, SLICE-008, SLICE-009, SLICE-014
SLICE-018 <- SLICE-003, SLICE-004, SLICE-006, SLICE-008, SLICE-009, SLICE-013
SLICE-019 <- SLICE-004, SLICE-011, SLICE-015
SLICE-020 <- SLICE-004, SLICE-008, SLICE-009, SLICE-014, SLICE-015
SLICE-021 <- SLICE-005, SLICE-006, SLICE-012, SLICE-015
SLICE-022 <- SLICE-004, SLICE-006, SLICE-007, SLICE-008, SLICE-009, SLICE-010, SLICE-013, SLICE-015, SLICE-018
SLICE-023 <- SLICE-004, SLICE-008, SLICE-009, SLICE-011, SLICE-012, SLICE-013
SLICE-024 <- SLICE-008, SLICE-009, SLICE-011, SLICE-012, SLICE-017, SLICE-018, SLICE-023
```

## Parallelization Summary

| Phase | Parallel groups | Max concurrent |
|---|---|---|
| 0 | [SLICE-001 + SLICE-005]; [SLICE-002]; [SLICE-003 + SLICE-004 + SLICE-006] | 3 |
| 1 | [SLICE-007 + SLICE-008]; [SLICE-009]; [SLICE-010] | 2 |
| 2 | [SLICE-011 + SLICE-012 + SLICE-013 + SLICE-014 + SLICE-015 + SLICE-016]; [SLICE-017] | 6 |
| 3 | [SLICE-018 + SLICE-019 + SLICE-020 + SLICE-021] | 4 |
| 4 | [SLICE-022 + SLICE-023]; [SLICE-024] | 2 |
