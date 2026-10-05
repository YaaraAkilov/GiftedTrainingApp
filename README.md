# v17 QA hotfix

Fixes the question publication filter to use the dataset release flag `validation.approved_for_pool` and adds cache-busting for the question bank.

Expected active pool: 2,573 released questions at difficulty 4-5.

# אתגר המחוננים — Release Candidate v15

אפליקציית אימון RTL בעברית לתלמידי כיתה ו׳ העולים לכיתה ז׳.

## סטטוס v8
- 1,785 שאלות נשמרות במאגר.
- 1,651 שאלות פעילות.
- 134 שאלות seed נשארות מחוץ ל-pool עד review/validation נוסף.
- המאגר הפעיל כולל גם אנלוגיות, השלמת משפטים, אוצר מילים, יוצא מן הכלל, מילת תפל והבנת הנקרא.
- שאלות אנלוגיה/מילולי שהוגדרו כ-pending נשארות במסלול semantic review ואינן מוגשות לילד.
- exact-prompt duplicates: 0 בפול הפעיל (לא-חזותי).
- visual fingerprint duplicates: 0.
- duplicate content hashes: 0.
- formal checker failures: 0 בפול הפעיל.
- כל 1,500 השאלות הפעילות כוללות 4 אפשרויות, תשובה נכונה יחידה, explanation, reasoning steps, semantic family ו-mode compatibility.

## יכולות אפליקציה
- אימון מהיר, אדפטיבי, לפי נושא, אימון 20, אתגר 5 דקות ואתגר יומי.
- סימולציית מבחן מלאה configurable in the app; current app mode is 90 questions / 90 minutes based on the project target, not an official Ministry blueprint.
- הסברים ו-reasoning steps לאחר תשובה במצבי תרגול.
- hints במצבי תרגול.
- anti-repetition לפי question/template/semantic family.
- skill mastery והמלצות חיזוק.
- היסטוריה, טעויות, parent dashboard ו-admin בסיסי.
- RTL + local persistence + PWA/offline-first.
- structured visual schemas ורינדור SVG.

## Content Engine
- generation באמצעות templates.
- structural validation.
- formal mechanical verification.
- semantic review queue נפרדת.
- release audit הכולל duplicates, options, publication state, formal failures וגיוון.

## QA
הדוח האחרון נמצא ב-`content_engine/reports/release_audit.json`.

להרצה מקומית:

```bash
python -m http.server 8000
```

ואז לפתוח `http://localhost:8000`.

## v9 Release QA
v9 adds a dedicated verbal semantic audit, fixes identified verbal-content defects, strengthens adaptive category balancing, and uses a fixed 30-question simulation blueprint across all 10 active categories. See `RELEASE_STATUS.md` and `content_engine/reports/v9_release_audit.json`.

## v10/v11 — Profiles, practice vs. full simulation

- Multiple local student profiles with separate progress, mistakes, daily challenge, sessions and simulation history.
- Automatic migration of the existing v9 local profile/history into the first v10 profile.
- Clear separation between Practice/Learning and Full Exam Simulation.
- Full simulation blueprint: 90 questions / 90 minutes, no hints or correctness feedback during the exam.
- Safe Exit button during practice and simulation; answered questions remain saved and the interrupted session is marked abandoned.
- Simulation results are shown separately from practice progress.
- Profile switching from the top navigation and settings.
- v11: dedicated simulation pre-start screen, clearer exam status, and separate simulation result disclaimer.
- v11: top navigation displays the active student name and PWA cache bumped to v11.

Note: profiles are local to the browser/device in v10; there is no cloud account sync yet.


## v15 Level QA

The active pool is conservatively restricted to questions screened at difficulty 4-5. All prior level 1-3 items are archived from the active pool. The 105-item simple averages template family is also archived despite its level-4 label because it does not meet the required reasoning-depth standard. See `tests/v15_level_qa_report.json`.
