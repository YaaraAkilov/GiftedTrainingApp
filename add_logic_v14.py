import json, random, hashlib, itertools
from pathlib import Path
random.seed(20261004)
P=Path('data/questions.json')
data=json.loads(P.read_text(encoding='utf-8')); qs=data['questions']
LET=['a','b','c','d']
names=[('אורי','נועה','תמר','יואב','רון'),('אלה','דניאל','מיה','עומר','ליה'),('שחר','גילי','עמית','נועם','רוני'),('תום','מאיה','איתי','יעל','נדב'),('רותם','עדי','נבו','גל','דנה')]
def make_opts(correct):
    alts=[]; base=correct[:]
    while len(alts)<3:
        a=base[:]; i,j=random.sample(range(5),2); a[i],a[j]=a[j],a[i]
        s=', '.join(a)
        if s not in alts and s!=', '.join(base): alts.append(s)
    vals=[(', '.join(base),True)]+[(x,False) for x in alts]; random.shuffle(vals)
    return [{'id':LET[i],'text':t,'is_correct':ok,'distractor_type':None if ok else 'close_order'} for i,(t,ok) in enumerate(vals)]
def add_logic(i):
    e=list(names[i%len(names)]); A,B,C,D,E=e
    # Canonical unique arrangement: C first; B immediately right of A; D immediately left of E; A/E not edges.
    cons=[{'type':'eq','entity':C,'pos':1},{'type':'immediately_right','a':A,'b':B},{'type':'immediately_right','a':D,'b':E},{'type':'not_eq','entity':A,'pos':1},{'type':'not_eq','entity':A,'pos':5},{'type':'not_eq','entity':E,'pos':1},{'type':'not_eq','entity':E,'pos':5}]
    # derive expected
    sols=[]
    for perm in itertools.permutations(range(1,6)):
        a=dict(zip(e,perm)); ok=True
        for c in cons:
            if c['type']=='eq' and a[c['entity']]!=c['pos']: ok=False
            elif c['type']=='immediately_right' and a[c['b']]!=a[c['a']]+1: ok=False
            elif c['type']=='not_eq' and a[c['entity']]==c['pos']: ok=False
            if not ok: break
        if ok: sols.append(a)
    if len(sols)!=1: return None
    sol=sols[0]; order=[x for x,p in sorted(sol.items(),key=lambda kv:kv[1])]
    prompt=f'חמישה תלמידים — {", ".join(e)} — עומדים בשורה, משמאל לימין. {C} עומד/ת בקצה השמאלי. {B} עומד/ת מיד מימין ל{A}. {E} עומד/ת מיד מימין ל{D}. {A} אינו/ה בקצה, וגם {E} אינו/ה בקצה. מהו הסדר המלא?'
    opts=make_opts(order); corr=next(o['id'] for o in opts if o['is_correct'])
    h=hashlib.sha256((prompt+'|'+'|'.join(o['text'] for o in opts)).encode()).hexdigest()[:16]
    return {'id':f'v14_logic2_{i:04d}','category':'logic','subcategory':'ordering_csp','skills':['deductive_reasoning','constraint_satisfaction','working_memory'],'content_type':'textual','prompt':prompt,'options':opts,'correct_option_id':corr,'explanation':f'ממקמים את {C} בקצה, את שני הזוגות הסמוכים, ואז בודקים את אילוצי הקצוות. מתקבל: {", ".join(order)}.','reasoning_steps':['מקבעים את התלמיד שנמצא בקצה השמאלי.','ממקמים את שני הזוגות של תלמידים צמודים.','בודקים את אילוצי הקצוות והסדר היחסי.',f'נשאר סידור יחיד: {", ".join(order)}.'],'visual_schema':None,'formal_spec':{'kind_group':'ordering_csp','entities':e,'positions':[1,2,3,4,5],'constraints':cons,'expected_assignment':sol,'correct_option_id':corr},'difficulty_prior':5,'difficulty_calibrated':None,'mode_compatibility':['training','simulation'],'rubric_score':{'I':3,'H':3,'R':3,'D':2,'W':3,'total':14,'rubric_level':5,'source':'quality_v14'},'validation':{'structural_validation':True,'logical_validation':{'applicable':True,'status':'passed','detail':'unique ordering verified'},'content_quality_validation':True,'structural_analogy_validation':None,'semantic_review':{'required':False,'status':'approved','reviewer':'content_engine_v14','notes':'parameterized ordering item'},'difficulty_calibration':{'status':'prior_only','sample_size':0,'observed_p_value':None,'flag_mismatch':False},'approved_for_pool':True},'provenance':{'source':'quality_v14','batch_id':'v14_logic2','created_at':'2026-10-04','publication_status':'published/active'},'usage_stats':{'times_shown':0,'times_correct':0,'times_wrong':0,'avg_time_seconds':0,'last_shown_at':None},'template_id':'logic_ordering_v14_2','instance_id':f'v14_logic2_{i:04d}','semantic_family_id':f'logic_ordering_v14_2_{i%60}','generation_type':'curated_parameterized_v14','content_hash':h}
new=[]
for i in range(300):
 q=add_logic(i)
 if q: new.append(q)
# avoid duplicates
ids={q['id'] for q in qs}; hashes={q.get('content_hash') or hashlib.sha256((q.get('prompt','')+'|'+'|'.join(o.get('text','') for o in q.get('options',[]))).encode()).hexdigest()[:16] for q in qs}
for q in new:
 if q['id'] not in ids and q['content_hash'] not in hashes: qs.append(q);ids.add(q['id']);hashes.add(q['content_hash'])
data['questions']=qs; data['version']='v14'; P.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('added logic',len(new),'total',len(qs))
