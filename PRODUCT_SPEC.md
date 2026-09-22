# PRODUCT_SPEC.md — אפליקציית אימון למבחני מחוננים (כיתה ו'→ז')

**סטטוס:** טיוטת מפרט לאישור. אין קוד. אין שאלות חדשות. אין שינוי ב-Pilot הקיים.
**החלטה אסטרטגית:** קודם בונים את המערכת (אפליקציה + מנוע תוכן), ורק אחרי שהיא מוכנה חוזרים לייצור מאגר 1,500 השאלות — דרך הפייפליין שהמפרט הזה מגדיר, לא לפני.

---

## 0. חזון המוצר בשורה אחת

אפליקציית אימון אישית, בעברית ו-RTL מלא, לילד/ה בכיתה ו' המתכונן/ת למבחן מחוננים לכיתה ז' — עם אימון אדפטיבי אמיתי, מעקב הורים, וארכיטקטורת תוכן שמפרידה בבירור בין מה שניתן לאמת אוטומטית לבין מה שדורש שיפוט אנושי (semantic review).

---

## 1. מבנה המערכת המוצע (System Architecture)

המערכת מחולקת לשתי יחידות-על נפרדות, עם ממשק ברור ביניהן — כדי שאפשר יהיה לבנות ולבדוק כל אחת בנפרד:

```
┌─────────────────────────────┐         ┌──────────────────────────────────┐
│   CLIENT APP (תלמיד/הורה)    │         │   CONTENT ENGINE (backend/tוֹכן)   │
│   RTL, עברית, offline-first  │◄───────►│   ייצור, אימות, כיול, פרסום       │
└─────────────────────────────┘         └──────────────────────────────────┘
        │                                            │
        ▼                                            ▼
┌─────────────────────┐                   ┌──────────────────────────┐
│ Local Persistence    │                   │  Question Bank Store      │
│ (מקומי, offline)      │◄── sync ─────────►│  (מקור אמת מרכזי, מגורסן) │
└─────────────────────┘                   └──────────────────────────┘
```

**עקרונות מפתח:**
- **Offline-first**: האפליקציה חייבת לעבוד ללא רשת (תרגול, מעקב התקדמות) עם עותק מקומי של בנק השאלות; סנכרון לרקע כשיש חיבור.
- **Question Bank Store הוא היחיד ש"אמיתי"**: כל שינוי בבנק (שאלה חדשה, תיקון קושי, אישור semantic review) עובר רק דרך Content Engine, לא ישירות מהאפליקציה.
- **הפרדת קוראים/כותבים**: האפליקציה **קוראת בלבד** מבנק השאלות המפורסם (published snapshot); Admin Console הוא הצד היחיד שכותב לבנק.
- **גרסאות (versioning)**: כל "פרסום" של בנק השאלות מקבל מספר גרסה; מכשיר קליינט שסונכרן פעם אחת ממשיך לעבוד offline גם אם הבנק התעדכן, עד לסנכרון הבא.

---

## 2. מבנה הנתונים המרכזי (Core Data Model)

### 2.1 Question (רשומת שאלה)

שדה | תיאור
---|---
`id` | מזהה ייחודי וקבוע (לא משתנה בין גרסאות)
`category` / `subcategory` | טקסונומיה קבועה (היגיון, אנלוגיות, כמותי, סדרות, צורות/מרחבי...)
`skills[]` | תגיות מיומנות עדינות יותר מ-subcategory, לצורך אימון אדפטיבי לפי skill
`content_type` | `"textual"` \| `"visual"`
`prompt`, `options[4]`, `correct_option_id`, `explanation`, `reasoning_steps[]` | תוכן השאלה
`visual_schema` | חובה אם `content_type="visual"` — סכימה מובנית (לא טקסט חופשי) לרינדור SVG: סוג טרנספורמציה (rotation/reflection/movement/superposition/symmetry/folding/matrix...), פרמטרים גיאומטריים, מיפוי אופציות
`formal_spec` | אופציונלי — ייצוג פורמלי הניתן לאימות מכני (לוגיקה/CSP/חשבון/סדרה/עקביות סכימה חזותית); **לא קיים לאנלוגיות** (ראו 2.3)
`hypothesis_space` | **חובה** לשאלות מסוג paired-function/rule-discovery: הגדרה מפורשת של משפחת הכללים המועמדים שנבדקה, ואישור שמספר הדוגמאות הנתונות אכן מצמצם לחוקיות יחידה בתוך המשפחה המוצהרת — לא "מתאים ל-2 דוגמאות" גרידא
`mode_compatibility[]` | `["training"]` או `["training","simulation"]`. שאלה שמסבירה אסטרטגיית-פתרון בתוך ה-prompt עצמו (guided) מסומנת `["training"]` בלבד ולעולם לא נשלפת לסימולציה
`rubric_score` | ניקוד I/H/R/D/W (ראו DIFFICULTY_RUBRIC.md) — **prior** בלבד
`difficulty_prior` | הרמה שנגזרת מ-`rubric_score` (1–5) — נקודת פתיחה, לא אמת מוחלטת
`difficulty_calibrated` | nullable; מתמלא רק אחרי כיול מול נתוני שימוש אמיתיים (ראו 2.4); זהו הערך שהמנוע האדפטיבי מעדיף כשהוא קיים
`validation` | אובייקט מפורט (ראו 2.3)
`provenance` | מקור (pilot/generated/manual), batch_id, תאריך יצירה
`usage_stats` | `times_shown`, `times_correct`, `times_wrong`, `avg_time_seconds`, `last_shown_at` — הבסיס לכיול

### 2.2 מבני-משנה של visual_schema (דוגמאות סוגים מוכרים)
`matrix_attribute` · `rotation_matrix` · `reflection` / `reflection_matrix` · `superposition_matrix` (XOR/AND/OR) · `element_addition_polygon` · `position_matrix` · `net_diagram` (קיפול) · `paper_fold` · `cross_section` · `cube_rotation` / `cube_rotation_multi`.
**כלל מחייב**: שאלה חזותית שה"חוקיות" האמיתית שלה היא בעצם סדרה מספרית (גודל/אחוז-מילוי/ספירה) שרק צוירה — **נכשלת ב-content_quality_validation** ואינה יכולה להתפרסם. הטרנספורמציה חייבת להיות אחת מ: סיבוב, שיקוף, תזוזה מרחבית, הוספה/הפחתה של אלמנט נבדל, סופרפוזיציה, סימטריה, אינטראקציית-מטריצה, קיפול, רוטציה מנטלית.

### 2.3 validation (אובייקט אימות — ההפרדה המרכזית)

```
validation:
  structural_validation: bool        # 4 אופציות, תשובה יחידה, אין placeholder, אין כפילויות
  logical_validation:
    applicable: bool                 # false לאנלוגיות ולכל טיפוס שאין לו formal_spec
    status: "passed" | "failed" | "not_applicable"
    detail: string
  content_quality_validation: bool   # אין דליפת-חוקיות ב-prompt, אין "מספר מחופש כצורה"
  structural_analogy_validation:     # ספציפי לאנלוגיות בלבד
    tag_uniqueness_check: bool       # רק אופציה אחת מתויגת כתואמת ל-stem_relation
  semantic_review:
    required: bool                   # true תמיד לאנלוגיות; אחרת לפי סוג
    status: "pending" | "approved" | "rejected"
    reviewer: string | null
    notes: string | null
  difficulty_calibration:
    status: "prior_only" | "calibrating" | "calibrated"
    sample_size: int
    observed_p_value: float | null   # אחוז הצלחה נצפה בפועל
    flag_mismatch: bool              # true אם difficulty_prior סוטה משמעותית מהתנהגות בפועל
  approved_for_pool: bool            # תנאי סף — ראו למטה
```

**תנאי `approved_for_pool = true` (מחייב, לא הצהרתי):**
1. `structural_validation = true`
2. `logical_validation.status ∈ {"passed","not_applicable"}` — ואם `not_applicable`, **חובה** `semantic_review.status = "approved"`
3. `content_quality_validation = true`
4. עבור אנלוגיות: גם `structural_analogy_validation.tag_uniqueness_check = true` **וגם** `semantic_review.status = "approved"` — תיוג metadata לבדו **לעולם לא** מספיק
5. `difficulty_prior` קיים (rubric חושב); `difficulty_calibrated` אינו תנאי-סף לכניסה לבנק, אך שאלה עם `flag_mismatch=true` לא תשמש באימון אדפטיבי/סימולציה עד לבדיקה חוזרת

### 2.4 כיול קושי (Difficulty Calibration) — לא רק rubric
`difficulty_prior` הוא נקודת פתיחה בלבד. כיול אמיתי דורש **אחד משניים**:
- **נתוני שימוש**: לאחר N תשובות (סף מוגדר, למשל 30+) על פני מדגם ילדים בטווח הגיל, `observed_p_value` מחליף בהדרגה את המשקל של ה-prior (למשל ממוצע משוקלל שהולך ונוטה לעבר הנצפה).
- **פאנל מומחים/הורה-בודק** (לפני שיש מספיק דאטה): אישור ידני שה-prior סביר.
עד שאחד מהשניים קרה, `difficulty_calibrated = null` והמנוע האדפטיבי מתייחס לשאלה כ"קושי לא-מכויל" (עדיין שמישה, אך משוקללת בזהירות רבה יותר בבחירה אדפטיבית).

### 2.5 Hypothesis Space (ל-paired-function/rule-discovery)
```
hypothesis_space:
  candidate_family: string           # תיאור משפחת הכללים שנבדקה (למשל "linear a*x+b*y")
  candidates_tested: [string]        # רשימת הכללים הספציפיים שנבדקו בפועל
  examples_given: int
  disambiguation_verified: bool      # true רק אם אומת שמספר הדוגמאות מצמצם לכלל יחיד בתוך המשפחה המוצהרת
```
שאלה מסוג זה **לא** יכולה לטעון "unique mathematical rule" סתם — רק "ייחודי בתוך משפחת המועמדים המוצהרת, מאומת מול N דוגמאות".

### 2.6 User / Student Profile
`id`, `display_name`, `grade_track`, `created_at`, `skill_mastery_map{ skill_id → {exposure, correct, last_seen_at, mastery_score} }`, `difficulty_pointer` (per category, לאימון אדפטיבי), `linked_parent_id`.

### 2.7 Session / Attempt
`session_id`, `user_id`, `mode` (`quick`/`10`/`20`/`40`/`simulation`/`adaptive`), `started_at`, `ended_at`, `responses[]{question_id, chosen_option_id, correct, time_taken_seconds}`, `score_summary`.

### 2.8 Mistake Log Entry
`question_id`, `skill_ids[]`, `timestamp`, `chosen_option_id`, `resurfaced` (bool), `resurfaced_question_id` (שאלה **אחרת** באותו skill, לא אותה שאלה בדיוק).

---

## 3. מודולי האפליקציה (Client App)

1. **Onboarding / פרופיל** — יצירת פרופיל ילד/ה, קישור להורה.
2. **מסך בית / בחירת מצב** — אימון מהיר, 10/20/40 שאלות, סימולציה, אימון אדפטיבי.
3. **Practice Session Runner** — מנוע הרצת שאלה בודדת (טקסטואלי + רינדור SVG לחזותי), איסוף תשובה, הצגת הסבר + reasoning_steps.
4. **Simulation Runner** — מצב נפרד: טיימר, ללא רמזים, שולף **רק** שאלות עם `"simulation" ∈ mode_compatibility`, מציג תוצאה בסגנון מבחן אמיתי בסיום.
5. **מנוע אדפטיבי (לקוח)** — פונה לשירות הבחירה (ראו 4.10), אינו מממש לוגיקת-בחירה בעצמו.
6. **לוח התקדמות (תלמיד)** — מפת חוזק/חולשה לפי skill, מגמת קושי לאורך זמן, streaks.
7. **"הטעויות שלי"** — רשימת טעויות מקובצת לפי skill; "תרגל שוב" מציג שאלה **חדשה** באותו skill, לא את אותה שאלה.
8. **Parent Dashboard** — תצוגת קריאה בלבד, מסכם התקדמות, המלצות מיקוד, דוח שבועי.
9. **Admin Console** — ניהול תוכן: דפדוף/עריכה/אישור שאלות, תור semantic review, דוחות validator, ניהול batches ופרסום גרסאות.
10. **הגדרות** — locale (RTL/עברית קבוע), התראות, ניהול פרופילי ילדים (להורה).
11. **שכבת Offline/Local Persistence** — מטמון מקומי של בנק שאלות מפורסם + תור ניסיונות ממתינים לסנכרון.

---

## 4. מודולי מנוע התוכן (Content Engine)

1. **Question Bank Store** — מאגר מגורסן, מקור-אמת יחיד.
2. **Skill Taxonomy Registry** — הגדרת category/subcategory/skill קבועה, גרסתית.
3. **Question Generator Pipeline** — מבוסס-תבניות, פרמטרים אקראיים, יצירת מסיחים; כל פלט שלו נכנס לתור הבדיקה (5-6), **לעולם לא** ישירות לבנק הפעיל.
4. **Structural Validator** — בדיקה מכנית: 4 אופציות, תשובה יחידה, אין placeholder/כפילות, שדות חובה קיימים (כולל `visual_schema`/`hypothesis_space` היכן שרלוונטי).
5. **Logical/Mechanical Verification Engine** — בודקי-אמת פר-סוג (שרשור לוגי, CSP, חשבון, סדרה, עקביות סכימה חזותית). **מוגדר מראש כלא-רלוונטי** לאנלוגיות ולכל שאלה סמנטית-בעיקרה.
6. **Semantic Review Queue** — תור לבדיקה אנושית (או LLM-בתפקיד-בודק, מתויג ככזה) לכל מה שאינו מכני: טבעיות ניסוח, ייחודיות תשובה סמנטית, איכות מסיחים. שאלה לא עוברת ל-pool בלי אישור כאן כשנדרש.
7. **Difficulty Rubric Scorer** — מחשב `rubric_score`+`difficulty_prior` לפי DIFFICULTY_RUBRIC.md (עודכן: D לבדו אינו יכול לקבוע רמה 4/5 ללא מורכבות מבנית תואמת ב-I/R).
8. **Difficulty Calibration Service** — צובר `usage_stats`, מחשב `observed_p_value`, מעדכן `difficulty_calibrated`, מסמן `flag_mismatch`.
9. **Visual Schema → SVG Renderer** — רינדור דטרמיניסטי מ-`visual_schema` מובנה (משותף בין Admin-preview לאפליקציה עצמה — מקור רינדור יחיד).
10. **Anti-Repetition / Adaptive Selection Engine** — בורר שאלה הבאה: מדיר שאלות שנפתרו לאחרונה, מעדיף skills לא-מתורגלים, ל-mistake review: מחפש שאלה **אחרת** באותו skill/subcategory/difficulty קרוב, לא את אותו `id`.
11. **Mode-Compatibility Filter** — אוכף בזמן-בנייה ובזמן-שליפה שאין דליפת שאלת-training לתוך pool הסימולציה.
12. **Hypothesis-Space Registry & Checker** — אוכף בזמן-authoring ששאלות rule-discovery מצהירות ומאמתות `hypothesis_space`.
13. **Batch / Release Manager** — קיבוץ batches, מעקב אחר אילו עברו את כל השלבים, פרסום גרסה חדשה של הבנק לאפליקציה.

---

## 5. סדר Implementation מומלץ

| שלב | תוכן | תלוי ב- |
|---|---|---|
| **0** | סגירת Data Model (סעיף 2) + Skill Taxonomy סופית | — |
| **1** | Question Bank Store + Structural Validator + Admin viewer בסיסי (קריאה בלבד) — טעינת ה-Pilot/Gold הקיימים כ-seed לפיתוח | 0 |
| **2** | שלד אפליקציה: RTL/עברית, Local Persistence, Practice Session Runner (טקסטואלי בלבד) | 1 |
| **3** | Visual Schema → SVG Renderer + הרחבת ה-Runner לשאלות חזותיות | 1, 2 |
| **4** | מצבי אימון קבועים: מהיר/10/20/40 (בחירה אקראית פשוטה, כיבוד mode_compatibility ואי-חזרה מיידית) | 2, 3 |
| **5** | מודל שליטה ב-skills + לוח התקדמות תלמיד + "הטעויות שלי" | 4 |
| **6** | מנוע אדפטיבי אמיתי (קושי אדפטיבי + spaced-repetition לפי skill) | 5, 10 (content engine) |
| **7** | מצב סימולציה (טיימר, סינון simulation-eligible, דוח-תוצאה בסגנון מבחן) | 4, 11 (content engine) |
| **8** | Parent Dashboard | 5 |
| **9** | Admin Console מלא: תור semantic review, דוחות validator, ניהול batches/פרסום | 1, 6 (content engine) |
| **10** | Generator Pipeline מלא + Calibration Service מחוברים לזרם עבודה חי | 9 |
| **11** | **חזרה לייצור מאגר 1,500 השאלות** — דרך הפייפליין המלא (generator→structural→logical/מכני היכן שרלוונטי→semantic review לאנלוגיות/סמנטי→hypothesis-space checker→mode-compatibility tagging→rubric prior→המתנה לכיול) | הכל למעלה |

**הערה חשובה לסדר**: שלבים 1–5 יכולים לעבוד מול ה-Pilot/Gold הקיימים (125 שאלות) כ-seed data קבוע לפיתוח/בדיקה — **בלי לגעת בהם ובלי להרחיב אותם** — עד שהמערכת (במיוחד שלבים 9–10) מוכנה לקלוט את מאגר 1,500 בצורה מבוקרת.

---

## עקרונות QA מחייבים שנשמרים במפרט (תזכורת)
- אנלוגיות: **לעולם לא** `approved_for_pool` רק על סמך תיוג יחס — נדרש גם `semantic_review.status="approved"`.
- קושי: `difficulty_prior` (מ-rubric) אינו קביעה סופית — נדרש מסלול כיול (usage data או פאנל) לפני שנחשב "מכויל".
- שאלות paired-function: חובה `hypothesis_space` מוצהר ומאומת — אין טענת "ייחודיות מתמטית" סתמית.
- שאלות guided (מסבירות אסטרטגיה בגוף ה-prompt): `mode_compatibility=["training"]` בלבד — לא יופיעו בסימולציה לעולם.
- שאלות צורניות: visual-first בלבד — נפסלות אוטומטית ב-content_quality_validation אם החוקיות האמיתית היא סדרה מספרית מצוירת.
