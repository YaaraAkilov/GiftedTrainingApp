# אתגר המחוננים — Release Candidate v7

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
- סימולציה של 30 שאלות / 35 דקות.
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
