# GiftedTrainingApp v14

## Release focus
- Multi-profile local student accounts with isolated progress/history.
- Clear separation between Practice and Full Simulation modes.
- Safe exit from active sessions with answered items preserved.
- Full Simulation: 90 questions / 90 minutes; no hints or correctness feedback during the run.
- Practice options: 10, adaptive, topic, 20 timed, 40 mixed, and 5-minute challenge.
- Progress dashboard separates simulation results from practice results.

## Content QA
- 3,479 total question records retained in the source store.
- 2,573 published/active questions after the v14 expansion and prior level screen.
- Active pool contains only difficulty prior levels 4-5.
- New v14 quality expansion added 1,696 high-difficulty candidates before deduplication/guards (1,396 from the first quality batch + 300 ordering-logic variants retained after guards).
- Formal QA: 0 structural/level failures, 0 formal-check failures, 0 duplicate IDs, 0 duplicate content hashes.
- The prior 772 screened-out low-level items remain archived in the source data; they are not selected by the published pool.

## Important limitation
Difficulty 4-5 is a rubric-based prior, not a validated Ministry-of-Education score. Real-world calibration requires usage data and/or expert review. Semantic questions remain a separate review concern; v14 generated analogies were reviewed as candidates, but this does not establish official equivalence to the Ministry exam.
