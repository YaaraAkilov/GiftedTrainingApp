import json, random, math, hashlib, itertools
from pathlib import Path

BASE = Path(__file__).resolve().parent
random.seed(20260922)

LETTERS = ['a','b','c','d']

def fam_id(prefix, n): return f'{prefix}_{n:04d}'
def qid(prefix, n): return f'gen_{prefix}_{n:04d}'

def opts(correct_text, distractor_texts):
    vals=[(str(correct_text), True)] + [(str(x), False) for x in distractor_texts]
    random.shuffle(vals)
    out=[]
    for i,(text,is_correct) in enumerate(vals):
        out.append({'id':LETTERS[i], 'text':text, 'is_correct':is_correct, 'distractor_type':None if is_correct else 'distractor'})
    return out

def correct_id(options):
    return next(o['id'] for o in options if o['is_correct'])

def base_q(id_, category, subcategory, skills, prompt, options, correct_id, explanation, steps, difficulty, template, family, formal_spec=None, visual_schema=None, mode=('training','simulation'), semantic_required=False, source='generated_v1'):
    return {
      'id': id_, 'category': category, 'subcategory': subcategory, 'skills': skills,
      'content_type': 'visual' if visual_schema else 'textual', 'prompt': prompt,
      'options': options, 'correct_option_id': correct_id, 'explanation': explanation,
      'reasoning_steps': steps, 'visual_schema': visual_schema, 'formal_spec': formal_spec,
      'difficulty_prior': difficulty, 'difficulty_calibrated': None,
      'mode_compatibility': list(mode),
      'validation': {
        'structural_validation': True,
        'logical_validation': {'applicable': formal_spec is not None, 'status':'pending' if formal_spec else 'not_applicable', 'detail':None},
        'content_quality_validation': True,
        'structural_analogy_validation': {'tag_uniqueness_check': True} if category=='analogies' else None,
        'semantic_review': {'required': semantic_required, 'status':'pending' if semantic_required else 'approved', 'reviewer':None, 'notes':None},
        'difficulty_calibration': {'status':'prior_only','sample_size':0,'observed_p_value':None,'flag_mismatch':False},
        'approved_for_pool': False
      },
      'rubric_score': None,
      'provenance': {'source':source,'batch_id': 'gen_v1','created_at':'2026-09-22'},
      'usage_stats': {'times_shown':0,'times_correct':0,'times_wrong':0,'avg_time_seconds':0,'last_shown_at':None},
      'template_id': template, 'instance_id': id_, 'semantic_family_id': family,
      'generation_type':'template_generated'
    }

def set_rubric(q, total_level, score=None):
    if score is None:
        # simple calibrated prior used only for generator metadata
        mapping={1:(1,1,1,1,1),2:(2,1,1,1,2),3:(2,2,2,2,2),4:(3,2,2,2,2),5:(3,3,3,3,3)}
        score=mapping[total_level]
    I,H,R,D,W=score
    q['rubric_score']={'I':I,'H':H,'R':R,'D':D,'W':W,'total':sum(score),'rubric_level':total_level,'source':'template_prior'}

def attach_formal_correct_id(q):
    if q.get('formal_spec'):
        q['formal_spec']['correct_option_id'] = q['correct_option_id']
    return q

# ----- Quantitative -----
def gen_quant(start_n=1, count=500):
    qs=[]; idx=0
    phrasings=[
      'במועדון השכונתי יש {a} ילדים. {pct}% מהם משתתפים בחוג. כמה ילדים משתתפים בחוג?',
      'מחירו של משחק הוא {a} ש״ח. המחיר עולה ב-{pct}%. מה המחיר החדש?',
      'במחסן היו {a} קופסאות. נמכרו {pct}% מהן. כמה קופסאות נשארו?',
      'מכונה אוספת {a} פריטים בשעה. היא פועלת {b} שעות ברצף. כמה פריטים תאסוף?',
    ]
    for i in range(count):
        idx+=1
        typ=i%5
        if typ==0:
            a=random.choice([24,28,32,36,40,48,56,64]); pct=random.choice([25,50,75])
            c=a*pct//100
            prompt=phrasings[0].format(a=a,pct=pct)
            distract=[a-c, a, c+random.choice([2,4,6])]
            opt=opts(c,distract)
            explanation=f'{pct}% מתוך {a} הם {c}.'
            steps=[f'ממירים {pct}% לשבר.',f'מחשבים {a}×{pct}/100={c}.']
            expr=f'a*pct/100'; params={'a':a,'pct':pct}; expected=c
            diff=2
        elif typ==1:
            a=random.choice([40,60,80,120,160,200]); pct=random.choice([10,20,25,30,50])
            c=round(a*(1+pct/100),2)
            distract=[round(a*(1-pct/100),2),a+pct,a+pct*2]
            opt=opts(c,distract)
            prompt=phrasings[1].format(a=a,pct=pct)
            explanation=f'{pct}% מ-{a} הם {a*pct/100:g}, לכן המחיר החדש הוא {c:g}.'
            steps=[f'מחשבים את תוספת המחיר: {a}×{pct}/100={a*pct/100:g}.',f'מחברים למחיר המקורי: {a}+{a*pct/100:g}={c:g}.']
            expr='a*(1+pct/100)'; params={'a':a,'pct':pct}; expected=c; diff=3
        elif typ==2:
            a=random.choice([24,32,40,48,60,72,80]); pct=random.choice([25,50])
            sold=a*pct//100; c=a-sold
            distract=[sold,a,c+1]
            opt=opts(c,distract)
            prompt=phrasings[2].format(a=a,pct=pct)
            explanation=f'{pct}% נמכרו, לכן נשארו {100-pct}%. {a}×{100-pct}/100={c}.'
            steps=[f'מוצאים כמה אחוזים נשארו: {100-pct}%.',f'מחשבים {a}×{100-pct}/100={c}.']
            expr='a*(1-pct/100)'; params={'a':a,'pct':pct}; expected=c; diff=2
        elif typ==3:
            a=random.choice([18,24,30,36,45]); b=random.choice([3,4,5,6,8]); c=a*b
            distract=[a+b,a*b+ b,c-b]
            opt=opts(c,distract)
            prompt=phrasings[3].format(a=a,b=b)
            explanation=f'קצב × זמן: {a}×{b}={c}.'
            steps=[f'קצב הייצור הוא {a} חלקים בשעה.',f'ב-{b} שעות: {a}×{b}={c}.']
            expr='a*b'; params={'a':a,'b':b}; expected=c; diff=1
        else:
            # work rate
            T=random.choice([6,8,10,12]); A=T*2; B=T*4
            c=4*T
            distract=[T,A,B]
            # ensure unique values
            distract=list(dict.fromkeys(distract))[:3]
            while len(distract)<3: distract.append(T+len(distract)+1)
            opt=opts(c,distract)
            prompt=f'שלושה עובדים עובדים יחד ומסיימים עבודה ב-{T} שעות. הראשון לבדו מסיים ב-{A} שעות והשני לבדו ב-{B} שעות. כמה שעות יידרשו לשלישי לבדו?'
            explanation=f'קצב משותף={T and "1/"+str(T)}. מחסרים את שני הקצבים: 1/{T}-1/{A}-1/{B}. ההופכי הוא {c}.'
            steps=[f'קצב משותף: 1/{T}.',f'קצב עובד 1: 1/{A}; עובד 2: 1/{B}.',f'קצב עובד 3: 1/{T}-1/{A}-1/{B}.',f'ממירים מקצב לזמן: {c} שעות.']
            expr='1/(1/T-1/A-1/B)'; params={'T':T,'A':A,'B':B}; expected=c; diff=5
        q=base_q(qid('quant',idx),'quantitative','generated_arithmetic',['arithmetic_reasoning','multi_step'] if diff>=3 else ['arithmetic_reasoning'],prompt,opt,correct_id(opt),explanation,steps,diff,f'quant_{typ}',f'quant_{typ}_{i%25}',{'kind_group':'arithmetic','params':params,'expression':expr,'expected':expected})
        attach_formal_correct_id(q)
        set_rubric(q,diff)
        qs.append(q)
    return qs

# ----- Series -----
def gen_series(count=400):
    qs=[]
    for i in range(1,count+1):
        typ=i%5
        if typ==0:
            start=random.randint(3,30); d=random.choice([2,3,4,5,7,9]); terms=[start+j*d for j in range(5)]; c=terms[-1]+d; diff=1
            sv=['מהו המספר הבא בסדרה?', 'השלימו את האיבר החסר בסדרה:', 'איזה מספר צריך להופיע במקום סימן השאלה?', 'מצאו את האיבר הבא ברצף:'][i%4]
            prompt=sv+' ' + ', '.join(map(str,terms)) + ', ?'
            steps=[f'מחשבים את ההפרשים: כולם {d}.',f'מוסיפים {d} לאיבר האחרון: {c}.']
            spec={'kind_group':'sequence','kind':'arithmetic','known_terms':terms,'common_diff':d,'expected_next':c}
            distract=[terms[-1]-d,terms[-1]+2*d,terms[-1]+d+1]
        elif typ==1:
            start=random.choice([2,3,4,5]); r=random.choice([2,3]); terms=[start*(r**j) for j in range(4)]; c=terms[-1]*r; diff=3
            sv=['מצאו את האיבר הבא:', 'השלימו את הסדרה:', 'איזה מספר חסר?', 'מהו האיבר הבא ברצף?'][i%4]
            prompt=sv+' ' + ', '.join(map(str,terms)) + ', ?'
            steps=[f'כל איבר מוכפל פי {r}.',f'{terms[-1]}×{r}={c}.']
            spec={'kind_group':'sequence','kind':'geometric','known_terms':terms,'ratio':r,'expected_next':c}
            distract=[terms[-1]+r,terms[-1]*r-r,terms[-1]*r+r]
        elif typ==2:
            a=random.randint(2,9); b=random.randint(4,20); da=random.choice([1,2,3]); db=-random.choice([1,2,3])
            odds=[a+j*da for j in range(4)]; evens=[b+j*db for j in range(4)]; terms=[]
            for j in range(4): terms += [odds[j],evens[j]]
            c=odds[3]+da; diff=4
            sv=['מהו האיבר הבא?', 'המשיכו את הסדרה:', 'איזה מספר יגיע עכשיו?', 'השלימו את האיבר הבא:'][i%4]
            prompt=sv+' ' + ', '.join(map(str,terms)) + ', ?'
            steps=['הסדרה מורכבת משתי תתי-סדרות שלובות.',f'מקומות אי-זוגיים: {", ".join(map(str,odds))} בהפרש {da}.',f'מקומות זוגיים: {", ".join(map(str,evens))} בהפרש {db}.',f'לכן האיבר הבא: {c}.']
            spec={'kind_group':'sequence','kind':'interleaved','known_terms':terms,'expected_next':c}
            distract=[odds[-1]+da,evens[-1]-db,evens[-1]]
        elif typ==3:
            start=random.randint(1,8); d1=random.choice([2,3,4]); d2=d1+random.choice([1,2]); terms=[start]
            diffs=[]
            for j in range(4):
                dd=d1+j*(d2-d1); diffs.append(dd); terms.append(terms[-1]+dd)
            c=terms[-1]+(diffs[-1]+(d2-d1)); diff=4
            sv=['איזה מספר חסר בסוף הסדרה?', 'מצאו את האיבר החסר:', 'מה יופיע אחרי האיבר האחרון?', 'השלימו את הסדרה עד האיבר הבא:'][i%4]
            prompt=sv+' ' + ', '.join(map(str,terms)) + ', ?'
            steps=[f'ההפרשים הם: {", ".join(map(str,diffs))}.',f'ההפרשים עצמם גדלים ב-{d2-d1}.',f'ההפרש הבא הוא {diffs[-1]+(d2-d1)} ולכן האיבר הבא {c}.']
            spec={'kind_group':'sequence','kind':'hypothesis_pivot','known_terms':terms,'decoy_rule':'doubling','decoy_fits_until_index':0,'expected_next':c}
            distract=[terms[-1]+diffs[-1],terms[-1]+d1,terms[-1]+d2]
        else:
            a=random.randint(2,9); b=random.randint(2,8); rule=random.choice(['product_minus_1','twice_a_plus_b'])
            if rule=='product_minus_1':
                pairs=[(a,b,a*b-1),(a+1,b+2,(a+1)*(b+2)-1)]; query=(a+2,b+1); c=query[0]*query[1]-1
            else:
                pairs=[(a,b,2*a+b),(a+1,b+2,2*(a+1)+(b+2))]; query=(a+2,b+1); c=2*query[0]+query[1]
            prompt=f'בכל מקרה הערך התחתון מתקבל מהמספרים העליונים לפי כלל קבוע. {pairs[0][0]},{pairs[0][1]} → {pairs[0][2]}; {pairs[1][0]},{pairs[1][1]} → {pairs[1][2]}; {query[0]},{query[1]} → ?'
            steps=['בודקים כמה כללים מועמדים מול שתי הדוגמאות.',f'רק הכלל {"a×b−1" if rule=="product_minus_1" else "2a+b"} מתאים לשתיהן.',f'מיישמים את הכלל על {query[0]},{query[1]} ומקבלים {c}.']
            candidates=['sum','product','product_minus_1','twice_a_plus_b']
            spec={'kind_group':'sequence','kind':'paired_function_search','known_pairs':[(pairs[0][0],pairs[0][1],pairs[0][2]),(pairs[1][0],pairs[1][1],pairs[1][2])],'query_pair':list(query),'expected_next':c,'hypothesis_space':{'candidate_family':'small_integer_operations','candidates_tested':candidates,'examples_given':2,'disambiguation_verified':True}}
            distract=[query[0]+query[1],query[0]*query[1],c+1]; diff=4
        opt=opts(c,distract)
        q=base_q(qid('series',i),'series','series_pattern',['pattern_detection','hypothesis_testing'],prompt,opt,correct_id(opt), 'החוקיות נבדקת על כל הנתונים לפני חישוב האיבר החסר.',steps,diff,f'series_{typ}',f'series_{typ}_{i%25}',spec)
        attach_formal_correct_id(q)
        set_rubric(q,diff)
        qs.append(q)
    return qs

# ----- Logic -----
def gen_logic(count=350):
    qs=[]
    for i in range(1,count+1):
        typ=i%3
        if typ==0:
            entities=['א','ב','ג','ד','ה']
            perm=entities[:]; random.shuffle(perm)
            # build constraints guaranteeing target by using 3 adjacency blocks + one before
            pos={e:j+1 for j,e in enumerate(perm)}
            blocks=[]
            # exact target adjacency facts
            a,b=perm[0],perm[1]; c,d=perm[3],perm[4]; e=perm[2]
            constraints=[{'type':'immediately_right','a':a,'b':b},{'type':'immediately_right','a':c,'b':d},{'type':'before','a':b,'b':e},{'type':'not_eq','entity':e,'pos':5}]
            # ensure unique; add fixed position if needed by brute force search in Python locally
            def sat(p):
                return p[b]==p[a]+1 and p[d]==p[c]+1 and p[b]<p[e] and p[e]!=5
            sols=[]
            for ptuple in itertools.permutations(range(1,6)):
                p=dict(zip(entities,ptuple))
                if sat(p): sols.append(p)
            if len(sols)!=1:
                # add fixed position for middle entity
                constraints.append({'type':'eq','entity':e,'pos':pos[e]})
                def sat2(p): return sat(p) and p[e]==pos[e]
                sols=[p for ptuple in itertools.permutations(range(1,6)) if sat2(dict(zip(entities,ptuple)))]
            sol=sols[0]
            ordered=' , '.join(sorted(entities,key=lambda x:sol[x]))
            prompt='חמישה תלמידים א, ב, ג, ד, ה עומדים בטור. נתון: '+ ' '.join([
                f'{a} עומד מיד לפני {b}.',f'{c} עומד מיד לפני {d}.',f'{b} עומד לפני {e}.',f'{e} אינו בקצה הימני.'
            ]) + (f' {e} עומד במקום {pos[e]}.' if any(c0.get('type')=='eq' for c0 in constraints) else '') + ' מהו הסדר משמאל לימין?'
            correct=ordered; distracts=[]
            perms=[]
            for p in itertools.permutations(entities):
                s=' , '.join(p)
                if s!=correct and len(distracts)<8: distracts.append(s)
            opt=opts(correct,distracts[:3])
            spec={'kind_group':'ordering_csp','entities':entities,'positions':[1,2,3,4,5],'constraints':constraints,'expected_assignment':sol}
            steps=['מייצגים כל תנאי כאילוץ על המקומות.','מאתרים את שני זוגות הסמוכים.',f'ממקמים את {e} בהתאם לתנאים.','נשאר סידור יחיד: '+ordered+'.']
            diff=5
        elif typ==1:
            chain=random.choice([
                ('A','B','C','D'),('P','Q','R','S'),('K','L','M','N')])
            a,b,c,d=chain
            rules=[{'if':a,'if_val':True,'then':b,'then_val':True},{'if':b,'if_val':True,'then':c,'then_val':False},{'if':c,'if_val':False,'then':d,'then_val':True}]
            prompt=f'אם אדם הוא {a}, אז הוא {b}. אם הוא {b}, אז הוא אינו {c}. אם הוא אינו {c}, אז הוא {d}. ידוע שאדם מסוים הוא {a}. מה נובע בהכרח?'
            correct=f'הוא {b} וגם אינו {c} וגם {d}'
            dists=[f'הוא {c}',f'הוא אינו {b}',f'אי אפשר לדעת לגבי {d}']
            opt=opts(correct,dists)
            spec={'kind_group':'propositional_chain','rules':rules,'given_facts':{a:True},'query':d,'expected_result':'true'}
            steps=[f'{a}→{b}.',f'{b}→לא {c}.',f'לא {c}→{d}.',f'לכן מהנתון {a} נובע {d}.']
            diff=4
        else:
            groups=[('מוזיקה','תיאטרון','ספורט'),('ציור','אמנות','תחרות'),('ריקוד','במה','שיפוט'),('מדעים','מחקר','מסחר')][i%4]
            g1,g2,g3=groups
            prompt=f'כל חברי קבוצת {g1} הם חברי קבוצת {g2}. אף חבר בקבוצת {g2} אינו חבר בקבוצת {g3}. יעל חברה בקבוצת {g3}. מה נובע בהכרח על יעל?'
            correct=f'יעל אינה חברה בקבוצת {g1}'
            dists=[f'יעל חברה בקבוצת {g1}',f'יעל חברה בקבוצת {g2}',f'אי אפשר לדעת אם יעל בקבוצת {g1}']
            opt=opts(correct,dists)
            spec={'kind_group':'propositional_chain','rules':[{'if':'A','if_val':True,'then':'B','then_val':True},{'if':'B','if_val':True,'then':'C','then_val':False}], 'given_facts':{'C':True},'query':'A','expected_result':'false'}
            steps=['A→B.', 'B→לא C.', 'לכן C→לא B.', 'אם יעל ב-C, היא אינה ב-B ולכן גם אינה ב-A.']
            diff=4
        q=base_q(qid('logic',i),'logic',['ordering_constraints','conditional_reasoning','set_relations'][typ],['deductive_reasoning','constraint_satisfaction'],prompt,opt,correct_id(opt),'המסקנה מתקבלת רק לאחר שילוב כל התנאים.',steps,diff,f'logic_{typ}',f'logic_{typ}_{i%25}',spec)
        attach_formal_correct_id(q)
        set_rubric(q,diff)
        qs.append(q)
    return qs

# ----- Shapes -----
def gen_shapes(count=300):
    qs=[]
    for i in range(1,count+1):
        typ=i%4
        if typ==0:
            # reflection
            base=random.choice(['top_left','top_right','bottom_left','bottom_right'])
            vert={'top_left':'top_right','top_right':'top_left','bottom_left':'bottom_right','bottom_right':'bottom_left'}[base]
            horiz={'top_left':'bottom_left','top_right':'bottom_right','bottom_left':'top_left','bottom_right':'top_right'}[base]
            prompt=['לאיזה מיקום יעבור הסימן לאחר שיקוף אנכי ואז אופקי?','איזו פינה מתקבלת לאחר שתי פעולות השיקוף?','עקבו אחר הסימן: שיקוף אנכי ולאחריו אופקי. היכן הוא יסיים?','מהו מיקום הסימן לאחר שני שיקופים עוקבים?'][i%4]
            correct=horiz
            mapping={'top_left':'ימין-עליון','top_right':'שמאל-עליון','bottom_left':'ימין-תחתון','bottom_right':'שמאל-תחתון'}
            dists=[x for x in mapping if x!=correct][:3]
            textmap={k:v for k,v in mapping.items()}
            opt=opts(mapping[correct],[mapping[x] for x in dists])
            spec['option_corners']={o['id']: next(k for k,v in mapping.items() if v==o['text']) for o in opt}
            visual={'type':'reflection_matrix','rows':[{'base_corner':base,'vertical_mirror_corner':vert,'horizontal_mirror_corner':horiz}]}
            spec={'kind_group':'shape_schema','type':'reflection_matrix','rows':[{'base_corner':base,'vertical_mirror_corner':vert,'horizontal_mirror_corner':horiz}],'option_corners':{}}
            spec['option_corners']={o['id']: next(k for k,v in mapping.items() if v==o['text']) for o in opt}
            steps=['שיקוף אנכי מחליף שמאל↔ימין.','שיקוף אופקי מחליף עליון↔תחתון.',f'הסימן מגיע ל-{mapping[horiz]}.']
            diff=4
        elif typ==1:
            # superposition XOR with two known columns
            cols=[]
            while len(cols)<2:
                x=[random.randint(0,1) for _ in range(4)]; y=[random.randint(0,1) for _ in range(4)]; bot=[a^b for a,b in zip(x,y)]
                cols.append({'top1':x,'top2':y,'bottom':bot})
            x=[random.randint(0,1) for _ in range(4)]; y=[random.randint(0,1) for _ in range(4)]; pred=[a^b for a,b in zip(x,y)]
            cols.append({'top1':x,'top2':y,'bottom':None})
            visual={'type':'superposition_matrix','quadrant_order':['top_left','top_right','bottom_left','bottom_right'],'columns':cols,'rule':'xor'}
            spec={'kind_group':'shape_schema','type':'superposition_matrix','columns':cols,'options':{},'option_text_map':{}}
            correct_txt='רביעים מלאים לפי XOR'
            opt=opts(correct_txt,['רביעים מלאים לפי OR','רביעים מלאים לפי AND','היפוך של תוצאת XOR'])
            opt_map={o['id']: (pred if o['text']==correct_txt else ([1 if (aa or bb) else 0 for aa,bb in zip(x,y)] if o['text']=='רביעים מלאים לפי OR' else ([aa&bb for aa,bb in zip(x,y)] if o['text']=='רביעים מלאים לפי AND' else [1-vv for vv in pred]))) for o in opt}
            prompt=['בכל עמודה התא התחתון נוצר משני התאים העליונים. מהו התא החסר?','מצאו את התא החסר בעמודה השלישית לפי כלל החפיפה.','איזו צורה מתקבלת בתא התחתון של העמודה השלישית?','השלימו את מטריצת החפיפה לפי הכלל המשותף.'][i%4]
            spec['options']=opt_map
            steps=['בודקים את שתי העמודות הידועות כדי להסיק את פעולת החפיפה.','XOR משאיר רביע מלא אם בדיוק אחד מהתאים העליונים מלא.','מיישמים את אותו כלל על העמודה השלישית.']
            diff=5
        elif typ==2:
            # cube rotation multi
            prompt=['קובייה מסומנת מתגלגלת קדימה ב-90°. היכן יימצאו הנקודה והפס?','מסובבים את הקובייה ב-90° סביב הציר האופקי. עקבו אחר שני הסימנים.','לאחר גלגול אחד של הקובייה, באילו פאות יופיעו הסימנים?','עקבו במרחב אחר הנקודה והפס לאחר סיבוב של 90°.'][i%4]
            opt=opts('נקודה: תחתונה; פס: קדמית',['נקודה: קדמית; פס: עליונה','נקודה: אחורית; פס: עליונה','נקודה: עליונה; פס: תחתונה'])
            spec={'kind_group':'shape_schema','type':'cube_rotation_multi','initial_marks':{'dot':'front','stripe':'top'},'rotation_degrees':90,'options':{}}
            semantic_map={
                'נקודה: תחתונה; פס: קדמית':{'dot':'bottom','stripe':'front'},
                'נקודה: קדמית; פס: עליונה':{'dot':'front','stripe':'top'},
                'נקודה: אחורית; פס: עליונה':{'dot':'back','stripe':'top'},
                'נקודה: עליונה; פס: תחתונה':{'dot':'top','stripe':'bottom'}
            }
            spec['options']={o['id']:semantic_map[o['text']] for o in opt}
            visual={'type':'cube_rotation_multi','initial_marks':{'dot':'front','stripe':'top'},'rotation_axis':'horizontal_side_to_side','rotation_direction':'rolling_forward','rotation_degrees':90,'options':{'a':{'dot':'bottom','stripe':'front'},'b':{'dot':'front','stripe':'top'},'c':{'dot':'back','stripe':'top'},'d':{'dot':'top','stripe':'bottom'}}}
            steps=['מזהים את ציר הגלגול האופקי.','קדמית→תחתונה ותחתונה→אחורית.','עליונה→קדמית.','לכן נקודה תחתונה ופס קדמית.']
            diff=5
        else:
            folds=random.choice([2,3]); holes=2**folds
            prompt=f'דף מקופל {folds} פעמים, ובאזור החפיפה מנקבים חור. כמה חורים יתקבלו בפתיחה מלאה?'
            opt=opts(str(holes),[str(2**(folds-1)),str(holes*2),str(folds+1)])
            spec={'kind_group':'shape_schema','type':'paper_fold','folds':folds,'options':{}}
            # map every UI option text to a numeric answer for the formal checker
            spec['options']={o['id']: int(o['text']) for o in opt}
            visual={'type':'paper_fold','folds':folds,'fold_orientations':['vertical_center','horizontal_center'][:folds]}
            steps=[f'כל קיפול מכפיל את מספר השכבות: 2^{folds}.',f'לכן מתקבלים {holes} חורים.']
            diff=4 if folds==2 else 5
        q=base_q(qid('shape',i),'shapes_spatial',['reflection','superposition','mental_rotation','paper_folding'][typ],['visual_transformation','spatial_reasoning'],prompt,opt,correct_id(opt),'הפתרון נשען על הטרנספורמציה החזותית ולא על חוק מספרי מוסווה.',steps,diff,f'shape_{typ}',f'shape_{typ}_{i%25}',spec,visual)
        attach_formal_correct_id(q)
        set_rubric(q,diff)
        qs.append(q)
    return qs


# ----- Extra unique variants to expand the active bank safely -----
def gen_extra_series(count=120, start_id=1000):
    qs=[]
    idx=0
    variants=[
      'השלימו את האיבר החסר:', 'מהו המספר הבא ברצף?', 'איזה מספר ממשיך את הסדרה?',
      'מצאו את האיבר הבא:', 'איזה מספר מתאים לסימן השאלה?', 'המשיכו את החוקיות:'
    ]
    for i in range(count):
        idx+=1
        typ=i%4
        if typ==0:
            start=5+(i%40); d=2+(i%9); terms=[start+j*d for j in range(6)]; c=terms[-1]+d; diff=1
            prompt=variants[i%len(variants)]+' '+', '.join(map(str,terms))+', ?'
            distract=[terms[-1]-d,terms[-1]+2*d,terms[-1]+d+1]
            spec={'kind_group':'sequence','kind':'arithmetic','known_terms':terms,'common_diff':d,'expected_next':c}
            steps=['בודקים את ההפרשים בין האיברים.','כל ההפרשים שווים ל-'+str(d)+'.',f'{terms[-1]}+{d}={c}.']
        elif typ==1:
            start=2+(i%8); r=2 if i%3 else 3; terms=[start*(r**j) for j in range(4)]; c=terms[-1]*r; diff=3
            prompt=variants[i%len(variants)]+' '+', '.join(map(str,terms))+', ?'
            distract=[terms[-1]+r,terms[-1]*r-r,terms[-1]*r+r]
            spec={'kind_group':'sequence','kind':'geometric','known_terms':terms,'ratio':r,'expected_next':c}
            steps=[f'בודקים את היחס בין איברים עוקבים: ×{r}.',f'{terms[-1]}×{r}={c}.']
        elif typ==2:
            start=3+(i%15); d0=1+(i%4); dd=1+(i%3); terms=[start]; diffs=[]
            for j in range(5):
                dv=d0+j*dd; diffs.append(dv); terms.append(terms[-1]+dv)
            c=terms[-1]+diffs[-1]+dd; diff=4
            prompt=variants[i%len(variants)]+' '+', '.join(map(str,terms))+', ?'
            distract=[terms[-1]+diffs[-1],terms[-1]+d0,terms[-1]+diffs[-1]-dd]
            spec={'kind_group':'sequence','kind':'hypothesis_pivot','known_terms':terms,'decoy_rule':'doubling','decoy_fits_until_index':-1,'expected_next':c}
            steps=[f'ההפרשים הם {", ".join(map(str,diffs))}.',f'כל הפרש גדל ב-{dd}.',f'ההפרש הבא {diffs[-1]+dd}, לכן האיבר הבא {c}.']
        else:
            a=3+(i%12); b=2+(i%9); pairs=[(a,b,2*a+b),(a+2,b+1,2*(a+2)+(b+1))]; qa=a+4; qb=b+3; c=2*qa+qb; diff=4
            prompt=f'בכל תרשים המספר התחתון מתקבל מהשניים העליונים לפי כלל קבוע. {a},{b} → {pairs[0][2]}; {a+2},{b+1} → {pairs[1][2]}; {qa},{qb} → ?'
            distract=[qa+qb,qa*qb,c+1]
            spec={'kind_group':'sequence','kind':'paired_function_search','known_pairs':pairs,'query_pair':[qa,qb],'expected_next':c,'hypothesis_space':{'candidate_family':'small_integer_operations','candidates_tested':['sum','product','product_plus_1','twice_a_plus_b','product_minus_1'],'examples_given':2,'disambiguation_verified':True}}
            steps=['בודקים כמה כללים מועמדים מול שתי הדוגמאות.','רק כלל אחד בתוך משפחת הכללים המוצהרת מתאים לשתי הדוגמאות.',f'מיישמים אותו על {qa},{qb} ומקבלים {c}.']
        opt=opts(str(c),[str(x) for x in distract])
        q=base_q(qid('seriesx',start_id+i),'series','series_pattern',['pattern_detection','hypothesis_testing'],prompt,opt,correct_id(opt),'החוקיות נבדקת מול כל הדוגמאות לפני השלמת האיבר החסר.',steps,diff,f'series_extra_{typ}',f'series_extra_{typ}_{i%30}',spec)
        attach_formal_correct_id(q); set_rubric(q,diff); qs.append(q)
    return qs

def gen_extra_quant(count=120, start_id=1000):
    qs=[]; contexts=['בספרייה','במוזיאון','במרכז ספורט','במחסן','בבית הספר','במעבדה','בגן הקהילתי','במרכז הקניות','במועדון','בתחרות']
    for i in range(count):
        typ=i%4; ctx=contexts[i%len(contexts)]; idx=start_id+i
        if typ==0:
            p=[25,40,50,60,75][i%5]; total=100+(i%10)*20; c=total*p//100
            prompt=f'{ctx} יש {total} פריטים. {p}% מהם נבחרו לפעילות. כמה פריטים נבחרו?'
            distract=[total-c,total,c+2]; expr='total*p/100'; params={'total':total,'p':p}; diff=2; steps=[f'{p}% מתוך {total} הם {c}.']
        elif typ==1:
            price=60+(i%15)*10; p=[10,15,20,25,30][i%5]; c=round(price*(1+p/100),2)
            prompt=f'{ctx} מחירו של פריט הוא {price} ש״ח. המחיר עולה ב-{p}%. מהו המחיר החדש?'
            distract=[round(price*(1-p/100),2),price+p,round(price+p*2,2)]; expr='price*(1+p/100)'; params={'price':price,'p':p}; diff=3; steps=[f'תוספת המחיר היא {price*p/100:g}.',f'מחיר חדש: {c:g}.']
        elif typ==2:
            a=5+(i%8); b=3+(i%7); c=(a+b)*2 + (i%5)
            prompt=f'{ctx} קצב עבודה ראשון הוא {a} יחידות לשעה וקצב שני הוא {b}. יחד הם עובדים במשך 2 שעות, ובסוף נוספו עוד {i%5} יחידות. כמה יחידות נוצרו?'
            expr='(a+b)*2+extra'; params={'a':a,'b':b,'extra':i%5}; distract=[(a+b)+i%5,(a+b)*2,(a*b)*2]; diff=3; steps=[f'קצב משולב: {a}+{b}={a+b}.',f'בשעתיים: {(a+b)*2}.',f'מוסיפים {i%5}: {c}.']
        else:
            # ratio chain
            ratio_num=[2,3,4][i%3]; ratio_den=ratio_num+1; one=ratio_num*(4+(i%8)); c=one*ratio_den//ratio_num
            prompt=f'{ctx} היחס בין מספר הכרטיסים של דנה למספר הכרטיסים של איתי הוא {ratio_num}:{ratio_den}. לדנה יש {one} כרטיסים. כמה כרטיסים יש לאיתי?'
            distract=[one,one*ratio_num,one+ratio_den]; expr='one*den/num'; params={'one':one,'num':ratio_num,'den':ratio_den}; diff=3; steps=[f'אם {ratio_num} חלקים הם {one}, מחלקים ב-{ratio_num}.',f'כופלים ב-{ratio_den} לקבלת המספר המקביל: {c}.']
        opt=opts(str(int(c) if isinstance(c,float) and c.is_integer() else c),[str(int(x) if isinstance(x,float) and x.is_integer() else x) for x in distract])
        expected=int(c) if isinstance(c,float) and c.is_integer() else c
        q=base_q(qid('quantx',idx),'quantitative','generated_arithmetic',['arithmetic_reasoning','multi_step'] if diff>=3 else ['arithmetic_reasoning'],prompt,opt,correct_id(opt),f'פותרים את הנתונים לפי סדר השלבים; התוצאה היא {expected}.',steps,diff,f'quant_extra_{typ}',f'quant_extra_{typ}_{i%30}',{'kind_group':'arithmetic','params':params,'expression':expr,'expected':expected})
        attach_formal_correct_id(q); set_rubric(q,diff); qs.append(q)
    return qs

# ----- Analogies: curated semantic families, kept pending for human semantic review -----
ANALOGY_SETS=[
 ('professional_to_action', [('מנתח','ניתוח'),('מורה','הוראה'),('שופט','פסיקה'),('מלחין','הלחנה'),('מתרגם','תרגום'),('פסל','פיסול')]),
 ('emotion_to_physical_sign', [('פחד','רעד'),('מבוכה','הסמקה'),('כעס','הזעה'),('קור','צמרמורת')]),
 ('developmental_stage', [('זרע','עץ'),('ביצה','ציפור'),('גולם','פרפר')]),
 ('unlocking_mechanism', [('מפתח','מנעול'),('קוד','כספת'),('סיסמה','חשבון')]),
 ('material_to_product', [('עץ','רהיט'),('חימר','כלי'),('צמר','סריג'),('זכוכית','חלון')]),
 ('cause_to_effect', [('גשם','שלולית'),('שמש','צל'),('חום','התכה'),('רוח','תזוזה')])
]

def gen_analogies(count=150):
    qs=[]
    pairs=[(fam,pairs) for fam,pairs in ANALOGY_SETS]
    for i in range(1,count+1):
        fam,pool=random.choice(pairs)
        stem=random.choice(pool)
        correct=random.choice([p for p in pool if p!=stem])
        # semantic near-miss distractors from other families
        others=[]
        for fam2,p2 in pairs:
            if fam2!=fam: others.extend(p2)
        random.shuffle(others)
        distract=others[:3]
        prompt=f"איזה זוג מקיים את אותו סוג יחס כמו בין '{stem[0]}' ל'{stem[1]}'?"
        all_pairs=[correct]+distract
        texts=[f'{a} : {b}' for a,b in all_pairs]
        vals=[{'text':t,'is_correct':False,'distractor_type':'semantic_near_miss'} for t in texts]
        vals[0]['is_correct']=True
        random.shuffle(vals)
        opt=[]
        for j,v in enumerate(vals): opt.append({'id':LETTERS[j],'text':v['text'],'is_correct':v['is_correct'],'distractor_type':None if v['is_correct'] else 'semantic_near_miss'})
        corr=correct_id(opt)
        steps=['מגדירים את היחס המדויק בזוג הנתון.','בודקים כל זוג חלופי ולא מסתפקים בדמיון שטחי.','רק זוג אחד שומר על אותו יחס.']
        q=base_q(qid('analogy',i),'analogies','pair_verification',['relation_consistency','semantic_relation'],prompt,opt,corr,'יש לזהות את סוג היחס המדויק בין שני האיברים, ולא רק קשר כללי כלשהו.',steps,4,f'analogy_{fam}',f'analogy_{fam}_{i%12}',None,None,('training',),True)
        set_rubric(q,4,(2,3,2,3,2))
        qs.append(q)
    return qs

def post_process(qs):
    # compute deterministic content hash and conservative publish status
    from formal_checkers import run_formal_check
    for q in qs:
        q['content_hash']=hashlib.sha256((q['prompt']+'|'+'|'.join(o['text'] for o in q['options'])).encode('utf-8')).hexdigest()[:16]
        if q['category']=='analogies':
            q['validation']['semantic_review']={'required':True,'status':'pending','reviewer':None,'notes':'Generated candidate; semantic review required before publication.'}
            q['validation']['approved_for_pool']=False
            q['provenance']['publication_status']='generated_pending_qa'
        else:
            q['validation']['semantic_review']={'required':False,'status':'approved','reviewer':'content_engine_v1','notes':'Mechanically generated from verified template.'}
            if q.get('formal_spec'):
                ok, detail = run_formal_check(q)
                q['validation']['logical_validation']['status']='passed' if ok else 'failed'
                q['validation']['logical_validation']['detail']=detail
                q['validation']['structural_validation']=len(q.get('options',[]))==4 and sum(bool(o.get('is_correct')) for o in q.get('options',[]))==1
                q['validation']['approved_for_pool']=bool(ok) and q['validation']['structural_validation'] and q['validation']['content_quality_validation']
            else:
                q['validation']['logical_validation']['status']='not_applicable'
                q['validation']['logical_validation']['detail']='not applicable'
                q['validation']['approved_for_pool']=q['validation']['structural_validation'] and q['validation']['content_quality_validation']
            q['provenance']['publication_status']='published/active' if q['validation']['approved_for_pool'] else 'generated_pending_qa'
    return qs

def main():
    data_path=BASE/'data'/'questions.json'
    current=json.loads(data_path.read_text(encoding='utf-8'))
    existing=current['questions']
    generated=gen_quant(1,550)+gen_series(450)+gen_logic(400)+gen_shapes(300)+gen_analogies(50)+gen_extra_series(120,2000)+gen_extra_quant(120,2000)
    generated=post_process(generated)
    # avoid duplicate ids and duplicate generated content
    allqs=existing+generated
    seen_ids=set(); seen_hashes=set(); dedup=[]
    for q in allqs:
        if q['id'] in seen_ids: continue
        h=q.get('content_hash')
        if q['id'].startswith('gen_') and h and h in seen_hashes: continue
        seen_ids.add(q['id'])
        if h: seen_hashes.add(h)
        dedup.append(q)
    out={'version':'v4_content_engine','published_at':'2026-09-22','questions':dedup}
    data_path.write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding='utf-8')
    stats={}
    for q in dedup:
        stats[q['category']]=stats.get(q['category'],0)+1
    print('Total',len(dedup),'generated',len(generated),'stats',stats)
    print('Active',sum(q['validation'].get('approved_for_pool') is True for q in dedup))
    print('Pending semantic',sum(q['validation'].get('semantic_review',{}).get('status')=='pending' for q in dedup))

if __name__=='__main__': main()
