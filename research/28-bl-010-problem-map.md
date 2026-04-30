# BL-010 problem map — web form richer inputs

Source: BL-010 in `plans/BACKLOG.md` line 323. Independent of
the BL-019D-β family.

## What we're building

Day-1 form has two text fields (`character_name`,
`application_text`) targeting `scope_kind=global`. BL-010
wants:

1. **Chapter selector** — applicant picks a chapter; submit
   uses `scope_kind=chapter, scope_id=<chapter>`.
2. **Multi-page form** — multiple steps with progress
   indication.
3. **Conditional fields** — fields visible based on prior
   answers.
4. **File upload** — applicants attach files.

## Substrate audit

- **Form definitions**:
  `services/api/app/contracts/form_definitions.py` (or
  similar) holds the `form_definitions.fields` shape.
  Today's shape supports `field_type` ∈
  {text, textarea, ...}; need to verify exact enum.
- **Public submit**:
  `services/api/app/api/v1/endpoints/applications/public.py`
  + `_submit_application_internal` in
  `services/api/app/services/applications.py`. Today
  expects `responses: dict[str, str]` and `scope:
  {scope_kind, scope_id}`.
- **SPA form renderer**:
  `services/web/src/features/public/ApplicationFormRoute.tsx`
  (β-i landed). Renders 2 fields hardcoded. Needs to switch
  to data-driven rendering from `form_definitions.fields`.
- **Contract fixture**:
  `infra/tests/fixtures/web-ui/contract.json` is the test
  contract. Extension needed for new field types.
- **Form publishing**:
  `services/api/app/services/application_forms.py` — chapter
  officers publish forms.
- **Chapter listing**: `/api/v1/web/admin/chapters` exists
  (β-ii admin route). Public form needs a public-readable
  chapter list endpoint.

## Open questions for the proposal

### Q1. Decomposition

This is large (4 features). Likely split:
- **β-1**: Chapter selector + chapter-scoped submit. New
  field type (`chapter_select`); chapter list public endpoint.
- **β-2**: Multi-page + conditional fields. New field
  schema additions: `page`, `visible_when`.
- **β-3**: File upload. Storage backend (S3/object-storage)
  + presigned upload + reference in response.

Lock: **start with β-1 (chapter selector) only.** It's the
smallest standalone slice, unblocks chapter-scoped applicant
flow (BL-019D-β assumed chapter scope but applicants can
only submit at global today).

### Q2. Chapter list public endpoint

New `GET /api/v1/public/chapters?state=active` API route
— exposed to the SPA as `/api/public/chapters` — returns
`[{id, name}]`. Public (Pomerium catch-all), receipt-not-
required (it's just a list of chapters — no PII).

### Q3. New field type: `chapter_select`

Pydantic field shape:
```python
class FormFieldChapterSelect(BaseModel):
    id: str
    type: Literal["chapter_select"]
    label: str
    required: bool = True
    placeholder: str | None = None
```

Renders as a `<select>` populated from
`/api/public/chapters`.

### Q4. Submit flow change

When a `chapter_select` field exists, the SPA submits
`scope: {scope_kind: "chapter", scope_id: <selected>}` instead
of global. The existing form_definition determines whether
the submit is global or chapter-scoped (presence of
`chapter_select` field).

### Q5. Form lookup

`get_current_form_for_scope` currently lookups by chapter or
global. The public form for "richer inputs" is published at
global scope but produces chapter-scoped applications via
the `chapter_select`. Confirm form-lookup remains global.

### Q6. Test plan

- API: `chapter_select` field round-trips in form
  definitions; submit accepts `scope_kind=chapter` with
  `scope_id` from selector.
- SPA: chapter-select field renders, validates, submits
  correct scope.
- E2e: extend test 19 — submit with chapter, verify chapter-
  scoped application created.

### Q7. Anti-scope (β-1)

- Multi-page (β-2).
- Conditional fields (β-2).
- File upload (β-3).
- Chapter creation/deletion UI (separate).

## What the proposal must lock

Q1–Q7 above. Plus diff budget.

## Diff budget

Estimate ~+450/-50:
- Contracts: +50.
- Public chapter endpoint: +60.
- Form publish/render: +100.
- SPA form renderer extension: +120.
- Tests: +120.
