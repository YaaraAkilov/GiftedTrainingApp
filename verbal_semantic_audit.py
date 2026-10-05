import json,re,sys,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
path=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'data/questions.json'
qs=json.loads(path.read_text(encoding='utf8'))['questions']
verbal={'analogies','sentence_completion','vocabulary','odd_one_out','nonword_context','reading_comprehension'}
active=[q for q in qs if q.get('validation',{}).get('approved_for_pool') is True and q.get('category') in verbal]
errors=[]; warnings=[]
for q in active:
    opts=q.get('options',[]); prompt=q.get('prompt','')
    if len(opts)!=4 or sum(bool(o.get('is_correct')) for o in opts)!=1: errors.append([q['id'],'answer_structure'])
    sr=q.get('validation',{}).get('semantic_review',{})
    if sr.get('status')!='approved': errors.append([q['id'],'semantic_review_not_approved'])
    correct=next((o.get('text','') for o in opts if o.get('is_correct')), '')
    # flag exact answer echo as a full standalone clause/line, not ordinary word overlap
    if correct.strip() and len(correct.strip())>5 and correct.strip() in [x.strip(' .?!,:;') for x in re.split(r'[\n.!?]',prompt)]:
        errors.append([q['id'],'correct_answer_restates_prompt_clause'])
    texts=[re.sub(r'\s+',' ',o.get('text','').strip()) for o in opts]
    if len(set(texts))<4: errors.append([q['id'],'duplicate_options'])
    if q.get('category')=='nonword_context':
        m=re.search(r'["“](.+?)["”]',prompt)
        if m and m.group(1) in {'זפזף'}: errors.append([q['id'],'nonword_is_real_or_common_word'])
bycat=collections.Counter(q['category'] for q in active)
report={'active_verbal':len(active),'by_category':dict(bycat),'errors':errors,'warnings':warnings,'passed':not errors}
out=ROOT/'content_engine'/'reports'/'v9_verbal_semantic_audit.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2));sys.exit(0 if not errors else 1)
