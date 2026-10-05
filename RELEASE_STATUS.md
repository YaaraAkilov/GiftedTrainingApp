# v17 Release Notes

- Fixed a publication-filter/schema mismatch that could make the app appear empty.
- Uses `validation.approved_for_pool === true` as the release gate.
- Added cache-busting to `questions.json` and bumped the service-worker cache.
- Expected active pool in the bundled dataset: 2,573 questions (difficulty 4-5).

# GiftedTrainingApp v15

## Release focus
- Multi-profile local student accounts with isolated progress/history.
- Clear separation between Practice and Full Simulation modes.
- Safe exit from active sessions with answered items preserved.
- Full Simulation: 90 questions / 90 minutes; no hints or correctness feedback during the run.
- Practice options: 10, adaptive, topic, 20 timed, 40 mixed, and 5-minute challenge.
- Progress dashboard separates simulation results from practice results.

## Content QA
- 3,479 total question records retained in the source store.
- 2,573 published/active questions after the v15 expansion and prior level screen.
- Active pool contains only difficulty prior levels 4-5.
- New v15 quality expansion added 1,696 high-difficulty candidates before deduplication/guards (1,396 from the first quality batch + 300 ordering-logic variants retained after guards).
- Formal QA: 0 structural/level failures, 0 formal-check failures, 0 duplicate IDs, 0 duplicate content hashes.
- The prior 772 screened-out low-level items remain archived in the source data; they are not selected by the published pool.

## Important limitation
Difficulty 4-5 is a rubric-based prior, not a validated Ministry-of-Education score. Real-world calibration requires usage data and/or expert review. Semantic questions remain a separate review concern; v15 generated analogies were reviewed as candidates, but this does not establish official equivalence to the Ministry exam.


## v15 timing + local user access
- Per-question timer: simulation counts down from 60 seconds; practice counts up.
- Per-question elapsed time stored per attempt for statistics.
- Local user profiles now support username + 4-8 digit PIN (PIN stored as SHA-256 hash).
- Abandoned sessions can be resumed on the same device.
- Cloud/cross-device accounts are not implemented in this release.
