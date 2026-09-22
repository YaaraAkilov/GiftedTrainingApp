import json, re, sys, hashlib, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from formal_checkers import run_formal_check

ROOT=Path(__file__).resolve().parents[1]
path=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'data/questions.json'
qs=json.loads(path.read_text(encoding='utf-8'))['questions']

def norm(s): return re.sub(r'\s+',' ',str(s or '').strip())
def is_visual(q): return q.get('category')=='shapes_spatial' or q.get('visual_schema') is not None
def published(q): return q.get('validation',{}).get('approved_for_pool') is True

def fp(q):
    payload=json.dumps({'prompt':norm(q.get('prompt')),'options':[o.get('text','') for o in q.get('options',[])],'visual_schema':q.get('visual_schema')},ensure_ascii=False,sort_keys=True)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

r={'total':len(qs),'active':sum(published(q) for q in qs),'seed_only':sum(not published(q) for q in qs),'errors':[],'warnings':[]}
ids=collections.Counter(q.get('id') for q in qs)
r['duplicate_ids']=[k for k,v in ids.items() if v>1]
active=[q for q in qs if published(q)]
for q in active:
    opts=q.get('options',[])
    if len(opts)!=4: r['errors'].append([q.get('id'),'option_count',len(opts)])
    if sum(bool(o.get('is_correct')) for o in opts)!=1: r['errors'].append([q.get('id'),'correct_option_count'])
    texts=[norm(o.get('text')) for o in opts]
    if len(set(texts))!=len(texts): r['errors'].append([q.get('id'),'duplicate_option_text'])
    if any((not t) or 'placeholder' in t.lower() for t in texts): r['errors'].append([q.get('id'),'placeholder_or_empty_option'])
    if not q.get('explanation') or not q.get('reasoning_steps'): r['errors'].append([q.get('id'),'missing_explanation_or_steps'])
    if not q.get('mode_compatibility'): r['errors'].append([q.get('id'),'missing_mode_compatibility'])
    if not q.get('semantic_family_id'): r['errors'].append([q.get('id'),'missing_semantic_family_id'])
    if not q.get('instance_id'): r['errors'].append([q.get('id'),'missing_instance_id'])
    if q.get('generation_type')=='template_generated' and not q.get('formal_spec'):
        r['errors'].append([q.get('id'),'generated_without_formal_spec'])
    if q.get('category')=='analogies' and q.get('validation',{}).get('semantic_review',{}).get('status')!='approved':
        r['errors'].append([q.get('id'),'analogy_published_without_semantic_approval'])
    if q.get('category')=='shapes_spatial' and not q.get('visual_schema'):
        r['errors'].append([q.get('id'),'visual_without_schema'])

nonvisual_prompts=collections.Counter(norm(q.get('prompt')) for q in active if not is_visual(q))
r['active_nonvisual_prompt_duplicate_groups']={k:v for k,v in nonvisual_prompts.items() if v>1}
visual_fp=collections.Counter(fp(q) for q in active if is_visual(q))
r['active_visual_fingerprint_duplicate_groups']={k:v for k,v in visual_fp.items() if v>1}
hashes=collections.Counter(q.get('content_hash') for q in active if q.get('content_hash'))
r['active_content_hash_duplicates']={k:v for k,v in hashes.items() if v>1}

formal_fail=[]
formal_unchecked=[]
for q in active:
    if q.get('formal_spec'):
        ok,detail=run_formal_check(q)
        if ok is False: formal_fail.append([q.get('id'),detail])
        elif ok is None: formal_unchecked.append([q.get('id'),detail])
r['formal_failures']=formal_fail
r['formal_unchecked']=formal_unchecked
r['active_by_category']=dict(collections.Counter(q.get('category') for q in active))
r['active_by_difficulty']=dict(collections.Counter(str(q.get('difficulty_calibrated') or q.get('difficulty_prior') or '') for q in active))
r['active_by_family']=len({q.get('semantic_family_id') for q in active})
r['simulation_eligible']=sum('simulation' in (q.get('mode_compatibility') or []) for q in active)
r['semantic_pending_seed']=sum(q.get('validation',{}).get('semantic_review',{}).get('status')=='pending' for q in qs if not published(q))

# Basic diversity thresholds, warnings only.
if r['active'] < 1500: r['warnings'].append('active pool below 1500')
if len(r['active_by_category']) < 5: r['warnings'].append('active pool currently covers fewer than 5 categories; supporting verbal categories remain outside the active pool')
if len(r['active_nonvisual_prompt_duplicate_groups']): r['errors'].append(['GLOBAL','nonvisual_exact_prompt_duplicates',len(r['active_nonvisual_prompt_duplicate_groups'])])
if len(r['active_visual_fingerprint_duplicate_groups']): r['errors'].append(['GLOBAL','visual_fingerprint_duplicates',len(r['active_visual_fingerprint_duplicate_groups'])])
if len(r['active_content_hash_duplicates']): r['errors'].append(['GLOBAL','content_hash_duplicates',len(r['active_content_hash_duplicates'])])
if r['duplicate_ids']: r['errors'].append(['GLOBAL','duplicate_ids',r['duplicate_ids']])
if formal_fail: r['errors'].append(['GLOBAL','formal_failures',len(formal_fail)])

r['passed']=not r['errors']
print(json.dumps(r,ensure_ascii=False,indent=2))
out=ROOT/'content_engine'/'reports'/'release_audit.json'
out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
sys.exit(0 if r['passed'] else 1)
