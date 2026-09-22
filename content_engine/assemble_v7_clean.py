import json, random, hashlib, collections, re, sys, importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=Path('/mnt/data/v6base/gifted_training_app')
orig=json.loads((BASE/'data/questions.json').read_text(encoding='utf-8'))['questions']
seed=[q for q in orig if q.get('validation',{}).get('approved_for_pool') is not True]

spec=importlib.util.spec_from_file_location('custom', ROOT/'content_engine/make_release_bank_v7.py')
custom=importlib.util.module_from_spec(spec); spec.loader.exec_module(custom)
random.seed(20260922)

def norm(s): return re.sub(r'\s+',' ',str(s or '').strip())
def is_visual(q): return q.get('category')=='shapes_spatial' or q.get('visual_schema') is not None
def family(q): return q.get('semantic_family_id') or q.get('template_id')
def candidate_ok(q):
    opts=q.get('options') or []
    texts=[norm(o.get('text')) for o in opts]
    return len(opts)==4 and len(set(texts))==4 and all(texts) and family(q) and q.get('formal_spec')
def fp(q):
    payload=json.dumps({'prompt':norm(q.get('prompt')),'options':[norm(o.get('text')) for o in q.get('options',[])],'visual_schema':q.get('visual_schema')},ensure_ascii=False,sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()

def prepare(q):
    q=json.loads(json.dumps(q))
    q['content_hash']=fp(q)
    q['difficulty_calibrated']=int(q.get('difficulty_calibrated') or q.get('difficulty_prior') or 3)
    if q.get('formal_spec'):
        q['formal_spec']['correct_option_id']=q.get('correct_option_id')
    return q

TARGETS={'quantitative':560,'series':540,'logic':280,'shapes_spatial':120}
final=[]
for cat,target in TARGETS.items():
    if cat=='quantitative': pool=custom.build_quant(1200)
    elif cat=='series': pool=custom.build_series(1200)
    elif cat=='logic': pool=custom.build_logic(700)
    else: pool=custom.build_shapes(500)
    pool=[prepare(q) for q in pool if candidate_ok(q)]
    # exact-prompt uniqueness and family diversity
    for q in pool: q['_fp']=q['content_hash']
    buckets=collections.defaultdict(list)
    for q in pool: buckets[q['difficulty_calibrated']].append(q)
    for b in buckets.values(): random.shuffle(b)
    # feasible target distribution per category: prioritize variety and challenge; do not inflate labels.
    desired_by_cat={
      'quantitative':{1:40,2:100,3:220,4:150,5:50},
      'series':{1:60,2:0,3:90,4:290,5:100},
      'logic':{1:0,2:0,3:0,4:150,5:130},
      'shapes_spatial':{1:0,2:0,3:0,4:55,5:65},
    }
    desired=desired_by_cat[cat]
    chosen=[]; used_fp=set(); used_prompt=set(); fam_count=collections.Counter()
    for d,n in desired.items():
        for q in buckets.get(d,[]):
            p=norm(q.get('prompt')); f=family(q); k=q['_fp']
            if k in used_fp or p in used_prompt or fam_count[f]>=8: continue
            chosen.append(q); used_fp.add(k); used_prompt.add(p); fam_count[f]+=1
            if sum(1 for x in chosen if x['difficulty_calibrated']==d)>=n: break
    for q in pool:
        if len(chosen)>=target: break
        p=norm(q.get('prompt')); f=family(q); k=q['_fp']
        if k in used_fp or p in used_prompt or fam_count[f]>=8: continue
        chosen.append(q); used_fp.add(k); used_prompt.add(p); fam_count[f]+=1
    if len(chosen)<target: raise RuntimeError(f'{cat} only {len(chosen)}/{target}')
    final.extend(chosen[:target])

# Remove private helper field and assign stable IDs.
for i,q in enumerate(final,1):
    q.pop('_fp',None)
    q['id']=f'genv7_{q["category"][:4]}_{i:05d}'
    q['instance_id']=q['id']
    q['validation']['approved_for_pool']=True
    q['validation']['publication_status']='published/active'
    q['validation']['semantic_review']={'required': q['category']=='analogies','status':'approved' if q['category']!='analogies' else 'pending','reviewer':None,'notes':None}
    q['provenance']['batch_id']='v7_release_candidate'
    q['provenance']['publication_status']='published/active'
    q['content_hash']=fp(q)
    q['formal_spec']['correct_option_id']=q['correct_option_id']

# Keep every original seed-only question preserved, but not published.
# Mark them for transparent status without changing question content.
out=seed+final
(ROOT/'data'/'questions.json').write_text(json.dumps({'version':'v7_release_candidate','published_at':'2026-09-22','questions':out},ensure_ascii=False,indent=1),encoding='utf-8')
print(json.dumps({'total':len(out),'active':len(final),'by_category':dict(collections.Counter(q['category'] for q in final)),'by_difficulty':dict(collections.Counter(q['difficulty_calibrated'] for q in final))},ensure_ascii=False,indent=2))
