import json, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from formal_checkers import run_formal_check

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'data' / 'questions.json'
data=json.loads(path.read_text(encoding='utf-8'))
qs=data.get('questions',[])
report={'total':len(qs),'structural_errors':[],'formal_failures':[],'publication_errors':[],'duplicate_ids':[],'duplicate_content_hashes':[],'semantic_pending':0,'active':0,'by_category':dict(collections.Counter(q.get('category') for q in qs))}
ids=collections.Counter(); hashes=collections.Counter()
for q in qs:
    ids[q.get('id')]+=1
    if q.get('content_hash'): hashes[q['content_hash']]+=1
    opts=q.get('options',[])
    if len(opts)!=4: report['structural_errors'].append((q.get('id'),'expected 4 options'))
    if sum(bool(o.get('is_correct')) for o in opts)!=1: report['structural_errors'].append((q.get('id'),'expected exactly 1 correct option'))
    if q.get('category')=='analogies':
        if q.get('validation',{}).get('semantic_review',{}).get('status')!='approved' and q.get('validation',{}).get('approved_for_pool'):
            report['publication_errors'].append((q.get('id'),'analogy published before semantic approval'))
        if q.get('validation',{}).get('semantic_review',{}).get('status')=='pending': report['semantic_pending']+=1
    if q.get('validation',{}).get('approved_for_pool'): report['active']+=1
    if q.get('generation_type')=='template_generated' and q.get('formal_spec'):
        ok,detail=run_formal_check(q)
        if not ok: report['formal_failures'].append((q.get('id'),detail))
report['duplicate_ids']=[k for k,v in ids.items() if v>1]
report['duplicate_content_hashes']=[(k,v) for k,v in hashes.items() if v>1]
report['passed']=not any(report[k] for k in ['structural_errors','formal_failures','publication_errors','duplicate_ids','duplicate_content_hashes'])
print(json.dumps(report,ensure_ascii=False,indent=2))
(Path(__file__).resolve().parent/'reports'/'v7_bank_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
raise SystemExit(0 if report['passed'] else 1)
