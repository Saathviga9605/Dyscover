# Privacy and Data Handling

This describes current behaviour. It is not a legal assessment; see `readiness/risk-register.md` (B4) for questions that need qualified legal review.

## What is stored

| Data | Stored | Not stored |
|---|---|---|
| Account | email, display name, role, bcrypt password hash, token version | plain passwords |
| Child profile | first name/nickname, optional birth year | surname, photo, school |
| Games | stimuli, answers, timing, interaction events, server-computed correctness | — |
| Gaze (opt-in) | estimated screen coordinates, fixations, quality flags | camera images or video |
| Speech (opt-in) | recognised words, timing, derived reading features | audio (the speech demo writes a temporary file and deletes it immediately) |
| Lexi | conversation text | the system prompt |
| Sessions | SHA-256 digests of refresh tokens | raw refresh tokens |

## Third parties

- **Groq** receives Lexi messages (contact details are redacted first; no child profile data is added).
- **Browser speech recognition**: some browsers (e.g. Chrome) send audio to the browser vendor to recognise speech. Dyscover does not receive that audio.
- **jsDelivr / Google Fonts** serve the pinned WebGazer script and fonts.

## Consent

Gaze and microphone use each require an explicit adult choice in the browser before capture starts; it can be withdrawn at any time and is cleared when the adult signs out. Speech activities cannot start without it.

## Access

Only the parent account that created a child profile can see its data. A parent can share read-only *summaries* with an educator account and revoke that at any time. Educators never see raw answers, gaze or speech records.

## Retention, export and deletion

- Data is kept until the parent deletes it. There is no automatic expiry yet.
- **Export:** Account → "Download all my data" (`GET /api/privacy/export`) returns a ZIP with everything listed above, excluding credentials.
- **Delete a child:** removes the profile and every assessment, trial, event, gaze sample, speech record, practice session and educator link derived from it.
- **Delete the account** (password required): removes the account, all its children (as above), Lexi conversations, refresh tokens and educator links. Deletion is a single transaction; nothing is soft-deleted. Database backups, if an operator configures them, are outside this mechanism.
- Audit logs record opaque IDs and reason codes only.
