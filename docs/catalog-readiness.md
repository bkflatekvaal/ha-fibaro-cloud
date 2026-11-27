# HACS / Marketplace catalog readiness

Review date: 2026-11-27. This is a submission-preparation review, not a claim of
catalog acceptance. HACS and Home Assistant Marketplace share `hacs/default`.

## Lessons from earlier submissions

All four PRs found under `repo:hacs/default author:bkflatekvaal is:pr` were reviewed,
including reviews, inline comments and discussion.

| Previous PR | Reviewer feedback | Applied here |
| --- | --- | --- |
| [SweTrack #10086](https://github.com/hacs/default/pull/10086) | Do not submit from the fork's `master` branch. | Use a dedicated branch from current upstream `master` for the eventual catalog PR. |
| [Amina card #11257](https://github.com/hacs/default/pull/11257) | Same branch problem. | The project repository can use `main`; this rule concerns the submission branch in the `hacs/default` fork. |
| [SweTrack #10087](https://github.com/hacs/default/pull/10087) | Redact `account_id`; remove unsupported SVG and redundant dark/logo PNGs; mask API-key fields in both setup and reauth; release the fixes after validation. | Every config/option value is redacted, including unknown future fields. `SENSITIVE_KEYS` includes account identifiers. Only four distinct, supported PNGs are shipped. Password selectors and secret markers are tested in cloud setup, hub setup and reauth, including rejected submissions. |
| [Amina card #11258](https://github.com/hacs/default/pull/11258) | After catalog inclusion, lead with searching for the card instead of claiming it is unlisted. | Keep Add from link as the current route. Change README to catalog search only after this project is merged and available. |

SweTrack #10087 and Amina #11258 were merged by the time of this review. The two
earlier submissions from `master` were closed without merging. Do not copy their
old pending status into a new checklist.

## Current evidence

- Repository is public, active, owned by `bkflatekvaal`, with Issues enabled,
  a description, relevant topics and a GitHub-recognized MIT license.
- One integration under `custom_components/fibaro_cloud`; runtime assets are
  inside that folder. No additional runtime package requirements.
- `fibaro_cloud` is separate from HA's local `fibaro` integration. No folder for
  this domain was found in the checked core `master` or `dev` branches; recheck
  when submitting. The project was not in the `hacs/default` integration list.
- Manifest has the required fields and sorted keys, a hub category, maintainer,
  cloud-polling classification and version `0.1.0`.
- `hacs.json` has the same display name and now declares minimum HA `2026.11.0`,
  matching the tested API baseline and README. No country restriction is claimed.
- English translation is supplied; README covers setup, device selection,
  supported functions, credential handling, limitations and limited support.
- Image names, sizes and duplicates are checked in tests; the official hassfest
  and HACS checks also run on every push/PR, with no skipped checks.
- Authentication requests use verified HTTPS and an allowlist. Hub credentials
  are not forwarded on redirects; transport exceptions omit request URLs and
  payloads. Login is serialized and bounded, commands are not replayed, and
  manual reauth remains available.
- Diagnostics omit raw hub payloads and client/session objects. Tests verify
  account identifiers, passwords, cookies, tokens and unknown fields cannot
  appear as diagnostic values. These tests do not sanitize arbitrary user logs.

## Remaining steps before submission

1. Wait for Tests, hassfest and Marketplace/HACS to pass on the exact commit
   intended for release. Save the successful job links.
2. Publish a **full GitHub release**, not only a tag, from that commit. No release
   existed during this audit. Use tag `0.1.0` to match the manifest; prepared notes
   are in [release-notes/0.1.0.md](release-notes/0.1.0.md).
3. Verify that the published release actually contains the integration,
   translations and four brand PNGs, and carries the minimum HA version. A real
   Marketplace UI install has not been exercised; do not claim otherwise.
4. In the owner's fork of `hacs/default`, create a new branch such as
   `add-ha-fibaro-cloud` from current upstream `master`. Add
   `bkflatekvaal/ha-fibaro-cloud` alphabetically to the JSON `integration` list.
   Keep that diff to the one addition and permit maintainer edits.
5. Fill the current PR template with truthful checkboxes and actual release,
   HACS and hassfest URLs. Only open the PR after all prerequisites are met.
   Do not request individual reviewers, post reminders or open duplicates.
6. If requested changes arrive, fix them, rerun validation, publish an updated
   release and update the submission evidence. Mark a drafted PR ready only
   after its issues are resolved. After merge, update README to lead with catalog
   search and retain Add from link as a fallback if useful.

No release or catalog PR was published as part of this audit. Approval remains
the HACS maintainers' decision. The undocumented vendor web protocol, limited
live hardware coverage and maintainer availability remain practical limitations.

## Sources checked

- [hacs/default README](https://github.com/hacs/default/blob/master/README.md)
- [Current PR template](https://github.com/hacs/default/blob/master/.github/PULL_REQUEST_TEMPLATE.md)
- [HACS general requirements](https://www.hacs.xyz/docs/publish/start/)
- [HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/)
- [HACS inclusion requirements](https://www.hacs.xyz/docs/publish/include/)
- [HA catalog submission guide](https://contributors.home-assistant.io/marketplace/guides/catalog/)
- [HA custom integration guide](https://contributors.home-assistant.io/marketplace/guides/integrations/)
- [Validation checks](https://contributors.home-assistant.io/marketplace/reference/validation/)
- [Releases and minimum HA versions](https://contributors.home-assistant.io/marketplace/guides/releases/)
- [hacs.json reference](https://contributors.home-assistant.io/marketplace/reference/hacs-json/)
- [Brand image requirements](https://contributors.home-assistant.io/core/integrations/brands/)
- [Diagnostics privacy](https://contributors.home-assistant.io/core/integrations/diagnostics/)
- [Config flows](https://contributors.home-assistant.io/core/integrations/config-flow/)
