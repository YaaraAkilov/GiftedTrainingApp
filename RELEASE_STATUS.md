# Release Candidate v9

## Status
Release QA passed for the current local build.

- Question bank: 1,785 total
- Published/active: 1,651
- Active categories: 10
- Active semantic families: 471
- Release audit: PASS (0 errors)
- Verbal semantic audit: PASS (0 detected rule violations after manual review/fixes)
- Formal checker failures among active questions: 0
- Exact active prompt duplicates: 0
- Active visual fingerprint duplicates: 0
- Active content-hash duplicates: 0

## v9 QA fixes
- Fixed four ambiguous/weak analogies and normalized semantic-review status.
- Fixed Hebrew grammar in sentence completion and a duplicate/weak distractor.
- Replaced a real/common word that had been used as a supposed nonword.
- Corrected a nonword-context item whose prior keyed answer contradicted the sentence context.
- Added a dedicated verbal semantic audit.
- Adaptive selection now includes category-need weighting and stronger semantic-family diversity.
- Simulation uses a 30-question blueprint across all 10 active categories with difficulty balancing and family diversity.

## Publication note
134 legacy/seed questions remain outside the active pool. They are retained for development/review and are not served to the child.
