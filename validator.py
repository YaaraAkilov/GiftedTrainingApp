import json, sys
from collections import Counter
from difflib import SequenceMatcher
from formal_checkers import run_formal_check

def load(path):
    return json.load(open(path, encoding='utf-8'))

def validate(data):
    qs = data['questions']
    report = {
        'total': len(qs),
        'structural_errors': [],   # (id, error)
        'logical_errors': [],
        'content_quality_errors': [],
        'difficulty_errors': [],
        'id_counts': Counter(),
        'per_question': {}
    }

    seen_ids = set()
    prompts = []

    for q in qs:
        qid = q.get('id', '???')
        report['id_counts'][qid] += 1
        errs = {'structural': [], 'logical': [], 'content_quality': [], 'difficulty': []}

        # --- structural ---
        opts = q.get('options', [])
        if len(opts) != 4:
            errs['structural'].append(f"expected exactly 4 options, found {len(opts)}")
        ids_in_q = [o.get('id') for o in opts]
        if len(set(ids_in_q)) != len(ids_in_q):
            errs['structural'].append("duplicate option ids within question")
        texts = [o.get('text', '').strip() for o in opts]
        for t in texts:
            if not t or 'placeholder' in t.lower():
                errs['structural'].append(f"empty or placeholder option text: '{t}'")
        if len(set(texts)) != len(texts):
            errs['structural'].append("duplicate option text within question")
        correct = [o for o in opts if o.get('is_correct')]
        if len(correct) != 1:
            errs['structural'].append(f"expected exactly 1 correct option, found {len(correct)}")
        if not q.get('explanation', '').strip():
            errs['structural'].append("missing explanation")
        if not q.get('reasoning_steps'):
            errs['structural'].append("missing reasoning_steps")
        if q.get('category') == 'shapes_spatial':
            if not q.get('visual_schema'):
                errs['structural'].append("shapes_spatial question missing structured visual_schema")
            # prompt must not leak the rule
            leak_terms = ['עמודות מייצג', 'שורות מייצג', 'כל עמודה שומרת', 'חוקיות העמודות', 'חוקיות השורות', 'הכלל הוא']
            for t in leak_terms:
                if t in q.get('prompt', ''):
                    errs['content_quality'].append(f"prompt leaks the rule to the child: contains '{t}'")

        seen_ids.add(qid)

        # --- difficulty sanity: only a smell-test for questions WITHOUT a rubric_score;
        # once a rubric_score exists, IT is the authoritative source and prompt length
        # is explicitly not used to second-guess it (per DIFFICULTY_RUBRIC.md).
        diff = q.get('difficulty')
        prompt_len = len(q.get('prompt', ''))
        has_rubric = isinstance(q.get('rubric_score'), dict) and 'total' in q['rubric_score']
        if diff and diff >= 3 and prompt_len < 25 and q.get('category') != 'shapes_spatial' and not has_rubric:
            errs['difficulty'].append(f"difficulty {diff} but prompt very short/simple ({prompt_len} chars) and NO rubric_score on file - possible mislabeling")

        prompts.append((qid, q.get('prompt', '')))

        for k in ['structural', 'logical', 'content_quality', 'difficulty']:
            report[f'{k}_errors'].extend([(qid, e) for e in errs[k]])
        report['per_question'][qid] = errs

    # duplicate IDs across whole set
    dup_ids = [i for i, c in report['id_counts'].items() if c > 1]
    if dup_ids:
        report['structural_errors'].append(('GLOBAL', f'duplicate ids: {dup_ids}'))

    # near-duplicate prompt detection
    near_dupes = []
    for i in range(len(prompts)):
        for j in range(i+1, len(prompts)):
            id1, p1 = prompts[i]
            id2, p2 = prompts[j]
            if not p1 or not p2:
                continue
            ratio = SequenceMatcher(None, p1, p2).ratio()
            if ratio > 0.85:
                near_dupes.append((id1, id2, round(ratio, 2)))
    report['near_duplicates'] = near_dupes

    return report

def summarize(report):
    print("=== VALIDATION REPORT ===")
    print("Total questions:", report['total'])
    print("Structural errors:", len(report['structural_errors']))
    for qid, e in report['structural_errors']:
        print("  -", qid, ":", e)
    print("Content quality errors:", len(report['content_quality_errors']))
    for qid, e in report['content_quality_errors']:
        print("  -", qid, ":", e)
    print("Difficulty flags:", len(report['difficulty_errors']))
    for qid, e in report['difficulty_errors']:
        print("  -", qid, ":", e)
    print("Near-duplicate prompts (similarity>0.85):", len(report['near_duplicates']))
    for a, b, r in report['near_duplicates']:
        print("  -", a, b, r)

    approved = 0
    failed = []
    for qid, errs in report['per_question'].items():
        total_err = sum(len(v) for v in errs.values())
        if total_err == 0:
            approved += 1
        else:
            failed.append(qid)
    print(f"\nQuestions with zero detected errors: {approved}/{report['total']}")
    print("Questions with at least one detected error:", len(failed))
    return failed

def apply_validation_stages(data, report):
    """
    Rewrites validation_stages on EVERY question from actual check results only.
    A question's logical_validation may never be True unless a formal_spec exists
    AND run_formal_check() actually returned True for it. difficulty_validation may
    never be True unless a rubric_score breakdown is present (not just a bare int).
    approved requires all four stages to be True.
    """
    per_q_errs = report['per_question']
    summary = {'unchecked_logic': [], 'failed_logic': [], 'passed_logic': [],
               'no_rubric': [], 'has_rubric': []}

    for q in data['questions']:
        qid = q['id']
        errs = per_q_errs[qid]
        structural_ok = len(errs['structural']) == 0
        content_ok = len(errs['content_quality']) == 0

        formal_spec = q.get('formal_spec')
        if formal_spec:
            ok, detail = run_formal_check(q)
            logical_ok = bool(ok)
            logic_status = 'passed' if ok else 'failed'
            summary['passed_logic' if ok else 'failed_logic'].append(qid)
            q['logical_validation_detail'] = detail
        else:
            logical_ok = False
            logic_status = 'unchecked_no_formal_spec'
            summary['unchecked_logic'].append(qid)
            q['logical_validation_detail'] = "no formal_spec present - not mechanically verified"

        has_rubric = isinstance(q.get('rubric_score'), dict) and 'total' in q['rubric_score']
        if has_rubric:
            summary['has_rubric'].append(qid)
        else:
            summary['no_rubric'].append(qid)

        q['validation_stages'] = {
            "structural_validation": structural_ok,
            "logical_validation": logical_ok,
            "logical_validation_status": logic_status,
            "content_quality_validation": content_ok,
            "difficulty_validation": has_rubric,
            "approved": structural_ok and content_ok and logical_ok and has_rubric
        }
    return summary


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'pilot_100_questions.json'
    data = load(path)
    report = validate(data)
    failed = summarize(report)
    print("\nFAILED IDS (structural/content/duplicate heuristics):", failed)

    if '--apply-stages' in sys.argv:
        summary = apply_validation_stages(data, report)
        print("\n=== VALIDATION STAGES CONSISTENCY PASS ===")
        print("Logic mechanically PASSED:", len(summary['passed_logic']), summary['passed_logic'])
        print("Logic mechanically FAILED:", len(summary['failed_logic']), summary['failed_logic'])
        print("Logic UNCHECKED (no formal_spec yet):", len(summary['unchecked_logic']))
        print("Has rubric_score (difficulty_validation=True):", len(summary['has_rubric']))
        print("No rubric_score (difficulty_validation=False):", len(summary['no_rubric']))
        approved = sum(1 for q in data['questions'] if q['validation_stages']['approved'])
        print(f"\nFinal APPROVED (all 4 stages actually verified, not declarative): {approved}/{len(data['questions'])}")
        out_path = path.replace('.json', '_staged.json')
        json.dump(data, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print("Written:", out_path)
