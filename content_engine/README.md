# Content Engine

Pipeline להרצת ייצור שאלות מבוסס תבניות, בדיקות מבניות, אימות מכני, תיוג semantic review וניהול סטטוס publication.

## עקרונות
- generated questions לעולם לא נכנסות אוטומטית למאגר פעיל ללא validation מתאים.
- אנלוגיות מסומנות `semantic_review=pending` ואינן מפורסמות ללא review.
- שאלה מכנית חייבת לעבור formal checker מתאים לפני `approved_for_pool=true`.
- `template_id`, `instance_id` ו-`semantic_family_id` משמשים למניעת חזרתיות.
- `difficulty_prior` אינו תחליף לכיול שימוש עתידי.

## הרצה
```bash
python content_engine/generate_bank.py
python validator.py data/questions.json --apply-stages
```

הבנק שנוצר נשמר תחת `data/questions.json`.
