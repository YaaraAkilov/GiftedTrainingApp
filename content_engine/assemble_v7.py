import json, random, hashlib, collections, re, sys, importlib.util
from pathlib import Path

WORK=Path('/mnt/data/gifted_release_v7/app')
BASE=Path('/mnt/data/v6base/gifted_training_app')
orig=json.loads((BASE/'data/questions.json').read_text(encoding='utf-8'))['questions']
seed=[q for q in orig if q.get('validation',{}).get('approved_for_pool') is not True]
orig_active=[q for q in orig if q.get('validation',{}).get('approved_for_pool') is True]
# Import custom builders.
spec=importlib.util.spec_from_file_location('custom', WORK/'content_engine/make_release_bank_v7.py')
custom=importlib.util.module_from_spec(spec); spec.loader.exec_module(custom)

def norm(s): return re.sub(r'\s+',' ',(s or '').strip())
def is_visual(q): return q.get('category')=='shapes_spatial' or q.get('visual_schema') is not None
def fingerprint(q):
    payload=norm(q.get('prompt'))+'|'+json.dumps(q.get('options'),ensure_ascii=False,sort_keys=True)+'|'+json.dumps(q.get('visual_schema'),ensure_ascii=False,sort_keys=True)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]
def family(q): return q.get('semantic_family_id') or q.get('template_id')
def active(q): return q.get('validation',{}).get('approved_for_pool') is True

def candidate_ok(q):
    opts=q.get('options') or []
    texts=[norm(o.get('text')) for o in opts]
    return len(opts)==4 and len(set(texts))==4 and all(texts) and family(q)

def prep_original(q):
    q=json.loads(json.dumps(q))
    q['difficulty_calibrated']=q.get('difficulty_calibrated') or q.get('difficulty_prior')
    q['content_hash']=fingerprint(q)
    return q

# Seed and preserve all pending semantic items; they never reach practice automatically.
seen_fp=set(); selected=[]; fam_count=collections.Counter(); prompt_nonvisual=set()
# First take original active questions, but reduce exact/pseudo duplicates.
orig_pool=sorted(orig_active, key=lambda q:(q.get('category'), q.get('difficulty_calibrated') or q.get('difficulty_prior') or 3))
bycat=collections.defaultdict(list)
for q in orig_pool:
    nq=prep_original(q); cat=nq['category']; fp=nq['content_hash']; fam=family(nq); p=norm(nq['prompt'])
    if not candidate_ok(nq): continue
    if fp in seen_fp: continue
    if not is_visual(nq) and p in prompt_nonvisual: continue
    if fam_count[fam]>=8: continue
    seen_fp.add(fp); fam_count[fam]+=1
    if not is_visual(nq): prompt_nonvisual.add(p)
    bycat[cat].append(nq)

random.seed(20260922)
candidates={
  'quantitative': custom.build_quant(800),
  'series': custom.build_series(800),
  'logic': custom.build_logic(500),
  'shapes_spatial': custom.build_shapes(350),
}
# add custom candidates after current original candidates
for cat, qs in candidates.items():
    for q in qs:
        if not candidate_ok(q):
            continue
        q['content_hash']=fingerprint(q)

TARGETS={'quantitative':560,'series':540,'logic':280,'shapes_spatial':120}
final=[]
for cat,target in TARGETS.items():
    pool=list(bycat.get(cat,[]))+[q for q in candidates[cat] if candidate_ok(q)]
    # prefer higher-quality existing items first, then custom; preserve variety by difficulty/family.
    # Take a balanced spread across calibrated difficulty, but do not fabricate difficulty labels.
    buckets=collections.defaultdict(list)
    for q in pool: buckets[int(q.get('difficulty_calibrated') or q.get('difficulty_prior') or 3)].append(q)
    for b in buckets.values(): random.shuffle(b)
    desired={1:round(target*.05),2:round(target*.15),3:round(target*.35),4:round(target*.30),5:target-round(target*.05)-round(target*.15)-round(target*.35)-round(target*.30)}
    local=[]; used=set(); local_fam=collections.Counter(); local_prompts=set()
    # First choose by desired difficulty with family cap 6.
    for d,n in desired.items():
        for q in buckets[d]:
            fp=q['content_hash']; fam=family(q); p=norm(q.get('prompt'))
            if fp in used or local_fam[fam]>=6 or (not is_visual(q) and p in local_prompts): continue
            used.add(fp); local_fam[fam]+=1; local.append(q)
            if not is_visual(q): local_prompts.add(p)
            if len([x for x in local if int(x.get('difficulty_calibrated') or x.get('difficulty_prior') or 3)==d])>=n: break
    # Fill with any remaining while respecting diversity.
    for q in pool:
        if len(local)>=target: break
        fp=q['content_hash']; fam=family(q); p=norm(q.get('prompt'))
        if fp in used or local_fam[fam]>=6 or (not is_visual(q) and p in local_prompts): continue
        used.add(fp); local_fam[fam]+=1; local.append(q)
        if not is_visual(q): local_prompts.add(p)
    if len(local)<target: raise RuntimeError(f'{cat} only {len(local)}/{target}')
    final.extend(local[:target])

# Stable unique IDs, re-point correct IDs, and ensure all active have published state.
for i,q in enumerate(final,1):
    q['id']=f'genv7_{q["category"][:4]}_{i:05d}'
    q['instance_id']=q['id']
    if q.get('formal_spec'):
        # formal specs may contain option IDs; correct_option_id already matches options after generation.
        q['formal_spec']['correct_option_id']=q['correct_option_id']
    q['validation']['approved_for_pool']=True
    q['validation']['publication_status']='published/active'
    q['provenance']['publication_status']='published/active'
    q['difficulty_calibrated']=int(q.get('difficulty_calibrated') or q.get('difficulty_prior') or 3)
    q['content_hash']=fingerprint(q)

# Rebuild output from original seed + exactly 1500 active.
out=seed+final
# QA checks
sys.path.insert(0, str(WORK))
from formal_checkers import run_formal_check
errors=[]; prompt_counts=collections.Counter(); hash_counts=collections.Counter(); ids=collections.Counter()
for q in out:
    if active(q):
        ids[q['id']]+=1; prompt_counts[norm(q['prompt'])]+=1; hash_counts[q.get('content_hash')]+=1
        opts=q.get('options',[])
        if len(opts)!=4 or sum(bool(o.get('is_correct')) for o in opts)!=1: errors.append((q['id'],'options'))
        if not q.get('explanation') or not q.get('reasoning_steps'): errors.append((q['id'],'explanation'))
        if q.get('formal_spec'):
            ok,detail=run_formal_check(q)
            if not ok: errors.append((q['id'],detail))
for q in seed:
    if q.get('id') in ids: errors.append((q['id'],'ID collision'))
nonvisual_prompt_dupes=sum(c-1 for p,c in prompt_counts.items() if c>1 and not any(is_visual(x) and norm(x['prompt'])==p for x in final))
# Exact prompt dup audit separated by visual/nonvisual.
active_nonvisual=[q for q in final if not is_visual(q)]
active_visual=[q for q in final if is_visual(q)]
np=collections.Counter(norm(q['prompt']) for q in active_nonvisual); vh=collections.Counter(q['content_hash'] for q in active_visual)
report={
 'version':'v7_release_candidate',
 'total_questions':len(out), 'active_questions':len(final),
 'seed_questions':len(seed), 'pending_semantic':sum(q.get('validation',{}).get('semantic_review',{}).get('status')=='pending' for q in out),
 'active_by_category':dict(collections.Counter(q['category'] for q in final)),
 'active_by_difficulty':dict(collections.Counter(q['difficulty_calibrated'] for q in final)),
 'active_nonvisual_exact_prompt_duplicates':sum(c-1 for c in np.values() if c>1),
 'active_visual_content_fingerprint_duplicates':sum(c-1 for c in vh.values() if c>1),
 'formal_checker_failures':len([e for e in errors if e[1] not in ('options','explanation','ID collision')]),
 'structural_errors':len([e for e in errors if e[1] in ('options','explanation','ID collision')]),
 'passed':not errors and len(final)==1500 and sum(1 for c in np.values() if c>1)==0 and sum(1 for c in vh.values() if c>1)==0,
 'notes':[
   'Generated release bank rebuilt from v6 with 1,500 active questions; semantic-pending seed items remain unpublished.',
   'Exact-prompt uniqueness is enforced for non-visual items; visual uniqueness is checked using prompt+options+visual_schema fingerprint.',
   'Difficulty is stored as calibrated prior and should later be refined from real usage data.'
 ]
}
(DATA:=WORK/'data'/'questions.json').write_text(json.dumps({'version':'v7_release_candidate','published_at':'2026-09-22','questions':out},ensure_ascii=False,indent=1),encoding='utf-8')
(WORK/'content_engine/reports').mkdir(parents=True,exist_ok=True)
(WORK/'content_engine/reports/v7_release_candidate_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
if not report['passed']: sys.exit(1)
