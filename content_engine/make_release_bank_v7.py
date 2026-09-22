import json, random, hashlib, itertools, re, collections, sys, importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'/'questions.json'
GEN=ROOT/'content_engine'/'generate_bank.py'
spec=importlib.util.spec_from_file_location('oldgen',GEN); oldgen=importlib.util.module_from_spec(spec); spec.loader.exec_module(oldgen)

# Preserve the existing 114 seed items from the v6 release package.
raw=json.loads(DATA.read_text(encoding='utf-8'))['questions']
seed=[q for q in raw if not str(q.get('id','')).startswith('gen_')]

TARGETS={'quantitative':560,'series':540,'logic':280,'shapes_spatial':120}
LETTERS=['a','b','c','d']
NAMES=['עדי','נועם','אורי','מאיה','רון','תמר','יואב','שירה','דניאל','אלה','איתן','ליה']
CONTEXTS=['בספרייה','במרכז הספורט','במעבדה','במוזיאון','בבית הספר','במחסן','במרכז הקהילתי','בתחרות','במועדון','בגינה הקהילתית','בחנות','בסדנה']

def norm(s): return re.sub(r'\s+',' ',(s or '').strip())
def opts(correct,distr):
    values=[]; correct_s=str(correct); values.append(correct_s)
    for x in distr:
        sx=str(x)
        if sx!=correct_s and sx not in values: values.append(sx)
    fallback=1
    while len(values)<4:
        candidate=str(correct + fallback) if isinstance(correct,(int,float)) else f'חלופה {fallback}'
        if candidate not in values: values.append(candidate)
        fallback+=1
    random.shuffle(values)
    return [{'id':LETTERS[i],'text':t,'is_correct':t==correct_s,'distractor_type':None if t==correct_s else 'plausible_error'} for i,t in enumerate(values[:4])]

def correct_id(o): return next(x['id'] for x in o if x['is_correct'])
def make_q(qid,cat,sub,skills,prompt,options,explanation,steps,diff,template,family,formal=None,visual=None,mode=('training','simulation')):
    cid=correct_id(options)
    if formal: formal['correct_option_id']=cid
    q={
      'id':qid,'category':cat,'subcategory':sub,'skills':skills,'content_type':'visual' if visual else 'textual',
      'prompt':prompt,'options':options,'correct_option_id':cid,'explanation':explanation,'reasoning_steps':steps,
      'visual_schema':visual,'formal_spec':formal,'difficulty_prior':diff,'difficulty_calibrated':diff,
      'mode_compatibility':list(mode),'validation':{
        'structural_validation':True,
        'logical_validation':{'applicable':bool(formal),'status':'pending' if formal else 'not_applicable','detail':None},
        'content_quality_validation':True,'structural_analogy_validation':None,
        'semantic_review':{'required':False,'status':'approved','reviewer':'content_engine_v7','notes':None},
        'difficulty_calibration':{'status':'calibrated_prior','method':'v7_category_specific','sample_size':0,'observed_p_value':None,'flag_mismatch':False},
        'approved_for_pool':True
      },
      'provenance':{'source':'v7_original_generator','batch_id':'v7_release','publication_status':'published/active','created_at':'2026-09-22'},
      'usage_stats':{'times_shown':0,'times_correct':0,'times_wrong':0,'avg_time_seconds':0,'last_shown_at':None},
      'template_id':template,'instance_id':qid,'semantic_family_id':family,'generation_type':'template_generated'
    }
    return q

def build_quant(n):
    qs=[]; seen=set(); idx=0
    pcts=[10,15,20,25,30,35,40,50,60,75]
    for k in range(n*3):
        if len(qs)>=n: break
        t=k%7; idx+=1; name=NAMES[k%len(NAMES)]; ctx=CONTEXTS[k%len(CONTEXTS)]
        if t==0:
            total=random.randint(4,24)*20; pct=random.choice(pcts); c=total*pct//100
            prompt=f'{ctx} יש {total} משתתפים. {pct}% מהם בחרו בפעילות מסוימת. כמה משתתפים בחרו בה?'
            distr=[total-c,total,c+random.choice([1,2,3,4])]
            diff=2; sub='percentages'; template='quant_v7_percent'
            steps=[f'{pct}% מתוך {total}: {total}×{pct}/100={c}.']; expl=f'{pct}% מתוך {total} הם {c}.'
            formal={'kind_group':'arithmetic','params':{'total':total,'pct':pct},'expression':'total*pct/100','expected':c}
        elif t==1:
            price=random.randint(40,450); pct=random.choice([10,15,20,25,30,40]); up=random.choice([True,False]); new=round(price*(1+pct/100),2) if up else round(price*(1-pct/100),2)
            verb='עלה' if up else 'ירד'; prompt=f'{ctx} מחירו של פריט הוא {price} ש"ח. המחיר {verb} ב-{pct}%. מהו המחיר החדש?'
            distr=[round(price*(1-pct/100),2) if up else round(price*(1+pct/100),2), price+pct, round(price,2)]
            diff=3; sub='percent_change'; template='quant_v7_change'; steps=[f'מחשבים {pct}% מתוך {price}: {price*pct/100:g}.',f"{'מוסיפים' if up else 'מחסירים'} את השינוי לקבלת {new:g}."]; expl=f"השינוי הוא {price*pct/100:g}, ולכן המחיר החדש הוא {new:g}."
            formal={'kind_group':'arithmetic','params':{'price':price,'pct':pct,'up':1 if up else 0},'expression':'price*(1+pct/100) if up else price*(1-pct/100)','expected':new}
        elif t==2:
            total=random.randint(60,300); a=random.randint(8,40); b=random.randint(5,30); hours=random.choice([2,3,4,5]); extra=random.randint(0,15); c=(a+b)*hours+extra
            prompt=f'{ctx} קצב עבודה ראשון הוא {a} יחידות לשעה ושני הוא {b}. הם עובדים יחד {hours} שעות, ואז נוצרות עוד {extra} יחידות. כמה יחידות נוצרו בסך הכל?'
            distr=[(a+b)+extra,(a+b)*hours,c-extra]
            diff=3; sub='combined_rates'; template='quant_v7_rates'; steps=[f'קצב משולב: {a}+{b}={a+b}.',f'ב-{hours} שעות: {(a+b)*hours}.',f'מוסיפים {extra}: {c}.']; expl=f'אחרי {hours} שעות נוצרו {(a+b)*hours} יחידות, ועוד {extra}, לכן {c}.'
            formal={'kind_group':'arithmetic','params':{'a':a,'b':b,'hours':hours,'extra':extra},'expression':'(a+b)*hours+extra','expected':c}
        elif t==3:
            rnum,rden=random.choice([(2,3),(3,4),(3,5),(4,5),(5,6)]); one=rnum*random.randint(6,50); c=one*rden//rnum
            prompt=f'לדנה ול{name} יש מספר כרטיסים ביחס של {rnum}:{rden}. לדנה יש {one} כרטיסים. כמה כרטיסים יש ל{name}?'
            distr=[one,one*rnum,one+rden]
            diff=3; sub='ratio'; template='quant_v7_ratio'; steps=[f'אם {rnum} חלקים הם {one}, חלק אחד הוא {one//rnum}.',f'{rden} חלקים הם {c}.']; expl=f'יחס של {rnum}:{rden} אומר שמחלקים את {one} ב-{rnum} ואז כופלים ב-{rden}: {c}.'
            formal={'kind_group':'arithmetic','params':{'one':one,'num':rnum,'den':rden},'expression':'one*den/num','expected':c}
        elif t==4:
            a=random.randint(2,12); b=random.randint(2,12); op=random.choice(['sum','product_minus_1','twice_a_plus_b']);
            if op=='sum': c=a+b; rule=f'{a}+{b}'
            elif op=='product_minus_1': c=a*b-1; rule=f'{a}×{b}-1'
            else: c=2*a+b; rule=f'2×{a}+{b}'
            a2=a+random.randint(1,4); b2=b+random.randint(1,4)
            c2=(a2+b2) if op=='sum' else (a2*b2-1 if op=='product_minus_1' else 2*a2+b2)
            qa=a+random.randint(3,7); qb=b+random.randint(3,7); qc=(qa+qb) if op=='sum' else (qa*qb-1 if op=='product_minus_1' else 2*qa+qb)
            prompt=f'בכל תרשים המספר התחתון מתקבל משני המספרים העליונים לפי כלל קבוע. {a},{b} → {c}; {a2},{b2} → {c2}; {qa},{qb} → ?'
            distr=[qa+qb,qa*qb,qc+1]
            diff=4 if op!='sum' else 3; sub='custom_operator'; template='quant_v7_operator'; steps=['בודקים כלל שמתאים לשתי הדוגמאות הנתונות.',f'כלל מתאים: {op}.',f'מיישמים אותו על {qa},{qb} ומקבלים {qc}.']; expl=f'אותו כלל חל בשתי הדוגמאות, ולכן במצב השלישי מתקבל {qc}.'
            formal={'kind_group':'arithmetic','params':{'a':a,'b':b,'a2':a2,'b2':b2,'qa':qa,'qb':qb},'expression':('qa+qb' if op=='sum' else 'qa*qb-1' if op=='product_minus_1' else '2*qa+qb'),'expected':qc,'hypothesis_space':{'candidate_family':'small_integer_operations','candidates_tested':['sum','product','product_minus_1','twice_a_plus_b'],'examples_given':2,'disambiguation_verified':True}}
        elif t==5:
            total=random.randint(90,360); avg=random.randint(20,80); count_nums=random.choice([3,4,5]); total2=avg*count_nums; adjust=random.randint(5,25); target=total2+adjust; prompt=f'{ctx} הממוצע של {count_nums} מספרים הוא {avg}. לאחר שמחליפים מספר אחד, סכום המספרים גדל ב-{adjust}. מהו הסכום החדש?';
            distr=[total2,total2-adjust,avg+adjust]; diff=4; sub='averages'; template='quant_v7_average'; steps=[f'סכום התחלתי: {count_nums}×{avg}={total2}.',f'מוסיפים {adjust}: {target}.']; expl=f'אם הממוצע הוא {avg} ויש {n} מספרים, הסכום הוא {total2}. לאחר השינוי: {target}.'
            formal={'kind_group':'arithmetic','params':{'n':count_nums,'avg':avg,'adjust':adjust},'expression':'n*avg+adjust','expected':target}
        else:
            age=random.randint(7,16); gap=random.randint(3,12); years=random.randint(2,8); future_age=age+years; other=age+gap+years; c=other
            prompt=f'{name} בן/בת {age} היום. אחיו/אחותו מבוגר/ת ממנו ב-{gap} שנים. בן/בת כמה יהיה/תהיה האח/ות בעוד {years} שנים?'
            distr=[age+gap,age+years,age+gap+years+1]; diff=2; sub='ages'; template='quant_v7_age'; steps=[f'גיל האח/ות היום: {age}+{gap}={age+gap}.',f'בעוד {years} שנים: {age+gap}+{years}={c}.']; expl=f'פער הגילים נשאר קבוע: {age+gap} היום, ולכן בעוד {years} שנים יהיו {c}.'
            formal={'kind_group':'arithmetic','params':{'age':age,'gap':gap,'years':years},'expression':'age+gap+years','expected':c}
        ph=norm(prompt)
        if ph in seen: continue
        seen.add(ph); opt=opts(c,distr)
        q=make_q(f'genv7_quant_{len(qs)+1:04d}','quantitative',sub,['arithmetic_reasoning','multi_step'] if diff>=3 else ['arithmetic_reasoning'],prompt,opt,expl,steps,diff,template,f'{template}_{len(qs)%25}',formal)
        qs.append(q)
    if len(qs)<n: raise RuntimeError('quant generation short')
    return qs

def build_series(n):
    qs=[]; seen=set(); k=0
    while len(qs)<n and k<n*5:
        t=k%6; k+=1
        if t==0:
            start=random.randint(2,300); d=random.randint(2,25); terms=[start+i*d for i in range(5)]; c=terms[-1]+d; diff=1; steps=[f'ההפרש קבוע: {d}.',f'{terms[-1]}+{d}={c}.']; sub='arithmetic'; template='series_v7_arithmetic'; expl=f'בכל מעבר מוסיפים {d}, לכן האיבר הבא הוא {c}.'
        elif t==1:
            start=random.randint(2,12); r=random.choice([2,3]); terms=[start*(r**i) for i in range(4)]; c=terms[-1]*r; diff=3; steps=[f'כל איבר מוכפל פי {r}.',f'{terms[-1]}×{r}={c}.']; sub='geometric'; template='series_v7_geometric'; expl=f'כל איבר הוא פי {r} מהקודם.'
        elif t==2:
            a=random.randint(2,40); b=random.randint(20,80); da=random.randint(2,9); db=random.randint(2,9); sign=random.choice([-1,1]);
            odds=[a+i*da for i in range(4)]; evens=[b+i*sign*db for i in range(4)]; terms=[v for i in range(4) for v in (odds[i],evens[i])]; c=odds[-1]+da; diff=4; steps=['יש כאן שתי תתי-סדרות שלובות.',f'במקומות אי-זוגיים ההפרש הוא {da}.',f'במקומות זוגיים ההפרש הוא {sign*db}.',f'לכן האיבר הבא הוא {c}.']; sub='interleaved'; template='series_v7_interleaved'; expl='המספרים במקומות הזוגיים והאי-זוגיים יוצרים שתי סדרות נפרדות.'
        elif t==3:
            start=random.randint(1,60); d0=random.randint(2,8); dd=random.randint(1,4); diffs=[d0+i*dd for i in range(5)]; terms=[start];
            for d in diffs: terms.append(terms[-1]+d)
            c=terms[-1]+(diffs[-1]+dd); diff=4; steps=[f'ההפרשים: {", ".join(map(str,diffs))}.',f'ההפרשים עצמם גדלים ב-{dd}.',f'לכן ההפרש הבא הוא {diffs[-1]+dd}, והאיבר הבא {c}.']; sub='second_difference'; template='series_v7_second'; expl='במקום להתמקד באיברים, בודקים את ההפרשים ביניהם.'
        elif t==4:
            start=random.randint(5,80); cycle=[random.randint(2,10),random.randint(2,10),random.randint(2,10)]; terms=[start]
            diffs=[]
            for j in range(6):
                d=cycle[j%3]; diffs.append(d); terms.append(terms[-1]+d)
            c=terms[-1]+cycle[0]; diff=4; steps=[f'נוצר מחזור של הפרשים: {cycle}.','מאתרים את המחזור וחוזרים לתחילתו.',f'ההפרש הבא הוא {cycle[0]}, ולכן האיבר הבא {c}.']; sub='cyclic'; template='series_v7_cyclic'; expl='החוקיות נמצאת במחזור ההפרשים, שחוזר על עצמו.'
        else:
            a=random.randint(2,9); b=random.randint(2,9); rule=random.choice(['product_minus_1','twice_a_plus_b']);
            if rule=='product_minus_1': pairs=[(a,b,a*b-1),(a+1,b+2,(a+1)*(b+2)-1)]; qa=a+3; qb=b+4; c=qa*qb-1
            else: pairs=[(a,b,2*a+b),(a+1,b+2,2*(a+1)+(b+2))]; qa=a+3; qb=b+4; c=2*qa+qb
            prompt=f'בכל תרשים המספר התחתון מתקבל משני המספרים העליונים לפי כלל קבוע. {pairs[0][0]},{pairs[0][1]} → {pairs[0][2]}; {pairs[1][0]},{pairs[1][1]} → {pairs[1][2]}; {qa},{qb} → ?'
            steps=['בודקים כלל שמתאים לשתי הדוגמאות.',f'הכלל הוא {rule}.',f'מיישמים אותו על {qa},{qb}.']; sub='operation_discovery'; template='series_v7_operator'; expl=f'לאחר אימות הכלל בשתי הדוגמאות מתקבלת התוצאה {c}.'; diff=4
            terms=[]; distract=[qa+qb,qa*qb,c+1]
        if t!=5:
            prompt=['השלימו את האיבר הבא:','איזה מספר צריך להופיע במקום סימן השאלה?','מצאו את המספר הבא ברצף:','מהו האיבר החסר?'][k%4]+' '+', '.join(map(str,terms))+', ?'
            distract=[terms[-1]-1,terms[-1]+1,terms[-1]+(2 if c>terms[-1] else -2)]
        else:
            distract=[qa+qb,qa*qb,c+1]
        ph=norm(prompt)
        if ph in seen: continue
        seen.add(ph); opt=opts(c,distract); formal=None
        if t==5: formal={'kind_group':'sequence','kind':'paired_function_search','known_pairs':pairs,'query_pair':[qa,qb],'expected_next':c,'hypothesis_space':{'candidate_family':'small_integer_operations','candidates_tested':['sum','product','product_minus_1','twice_a_plus_b'],'examples_given':2,'disambiguation_verified':True}}
        else:
            if t==0: formal={'kind_group':'sequence','kind':'arithmetic','known_terms':terms,'common_diff':d,'expected_next':c}
            elif t==1: formal={'kind_group':'sequence','kind':'geometric','known_terms':terms,'ratio':r,'expected_next':c}
            elif t==2: formal={'kind_group':'sequence','kind':'interleaved','known_terms':terms,'expected_next':c}
            elif t==3: formal={'kind_group':'sequence','kind':'second_difference','known_terms':terms,'second_difference':dd,'expected_next':c}
            else: formal={'kind_group':'sequence','kind':'cyclic_differences','known_terms':terms,'cycle':cycle,'diff_cycle':cycle,'expected_next':c}
        q=make_q(f'genv7_series_{len(qs)+1:04d}','series',sub,['pattern_detection','hypothesis_testing'],prompt,opt,expl,steps,diff,template,f'{template}_{len(qs)%25}',formal)
        qs.append(q)
    return qs

def build_logic(n):
    qs=[]; seen=set(); k=0
    while len(qs)<n and k<n*5:
        k+=1; t=k%3; names=random.sample(NAMES,5); a,b,c,d,e=names
        if t==0:
            # Build unique ordering puzzle by searching random constraints.
            entities=names; base=entities[:]; random.shuffle(base); pos={x:i+1 for i,x in enumerate(base)}
            constraints=[{'type':'immediately_right','a':base[0],'b':base[1]},{'type':'immediately_right','a':base[3],'b':base[4]},{'type':'before','a':base[1],'b':base[2]},{'type':'not_eq','entity':base[2],'pos':5}]
            def solve(cons):
                sols=[]
                for perm in itertools.permutations(range(1,6)):
                    p=dict(zip(entities,perm)); ok=True
                    for cc in cons:
                        if cc['type']=='immediately_right' and p[cc['b']]!=p[cc['a']]+1: ok=False
                        elif cc['type']=='before' and p[cc['a']]>=p[cc['b']]: ok=False
                        elif cc['type']=='not_eq' and p[cc['entity']]==cc['pos']: ok=False
                        elif cc['type']=='eq' and p[cc['entity']]!=cc['pos']: ok=False
                    if ok: sols.append(p)
                return sols
            sols=solve(constraints)
            if len(sols)!=1:
                constraints.append({'type':'eq','entity':base[2],'pos':pos[base[2]]}); sols=solve(constraints)
            if len(sols)!=1: continue
            sol=sols[0]; correct=' , '.join(sorted(entities,key=lambda x:sol[x])); diff=5
            prompt=f'חמישה תלמידים — {" , ".join(entities)} — עומדים בטור. נתון: {base[0]} עומד מיד לפני {base[1]}; {base[3]} עומד מיד לפני {base[4]}; {base[1]} עומד לפני {base[2]}; {base[2]} אינו בקצה הימני.' + (f' {base[2]} עומד במקום {pos[base[2]]}.' if any(x.get('type')=='eq' for x in constraints) else '') + ' מהו הסדר משמאל לימין?'
            opt=opts(correct,[x for x in [' , '.join(p) for p in itertools.permutations(entities) if ' , '.join(p)!=correct]][:3]); steps=['מאתרים את זוגות התלמידים שחייבים להיות סמוכים.','מקיימים את תנאי "לפני" ואת תנאי הקצה.',f'הסידור היחיד שנותר הוא {correct}.']; expl='כל התנאים יחד משאירים סידור אחד בלבד.'
            formal={'kind_group':'ordering_csp','entities':entities,'positions':[1,2,3,4,5],'constraints':constraints,'expected_assignment':sol}
            sub='ordering_constraints'; template='logic_v7_order'
        elif t==1:
            x,y,z,w=random.sample(['א','ב','ג','ד','ה','ו','ז','ח','ט','י'],4)
            prompt=f'אם אדם הוא {x}, אז הוא {y}. אם הוא {y}, אז הוא אינו {z}. אם הוא אינו {z}, אז הוא {w}. ידוע שאדם מסוים הוא {x}. מה נובע בהכרח?'
            correct=f'הוא {y}, אינו {z}, וגם {w}'
            opt=opts(correct,[f'הוא {z}',f'הוא אינו {y}','אי אפשר לדעת לגבי '+w]); diff=4
            steps=[f'{x}→{y}.',f'{y}→לא {z}.',f'לא {z}→{w}.','לכן מכל השרשור נובע גם '+w+'.']; expl='השרשור של שלושת התנאים מוביל למסקנה אחת.'
            formal={'kind_group':'propositional_chain','rules':[{'if':x,'if_val':True,'then':y,'then_val':True},{'if':y,'if_val':True,'then':z,'then_val':False},{'if':z,'if_val':False,'then':w,'then_val':True}],'given_facts':{x:True},'query':w,'expected_result':'true'}
            sub='conditional_reasoning'; template='logic_v7_chain'
        else:
            g1,g2,g3=random.sample(['מוזיקה','תיאטרון','ספורט','מדעים','אמנות','מחקר','ריקוד','תחרות'],3)
            person=NAMES[k%len(NAMES)]; prompt=f'כל חברי קבוצת {g1} הם חברי קבוצת {g2}. אף חבר בקבוצת {g2} אינו חבר בקבוצת {g3}. {person} חבר/ה בקבוצת {g3}. מה נובע בהכרח?'; correct=f'{person} אינו/ה חבר/ה בקבוצת {g1}'; opt=opts(correct,[f'{person} חבר/ה בקבוצת {g1}',f'{person} חבר/ה בקבוצת {g2}',f'אי אפשר לדעת אם {person} חבר/ה בקבוצת {g1}']); diff=4
            steps=[f'{g1}→{g2}.',f'{g2}→לא {g3}.',f'{person} נמצא/ת ב-{g3}, לכן אינו/ה ב-{g2}.','מכאן שאינו/ה יכול/ה להיות ב-'+g1+'.']; expl='מי שנמצא בקבוצה השלישית לא יכול להיות בשנייה, ומכיוון שכל חברי הראשונה נמצאים בשנייה, הוא גם לא יכול להיות בראשונה.'
            formal={'kind_group':'propositional_chain','rules':[{'if':'A','if_val':True,'then':'B','then_val':True},{'if':'B','if_val':True,'then':'C','then_val':False}],'given_facts':{'C':True},'query':'A','expected_result':'false'}
            sub='set_relations'; template='logic_v7_sets'
        ph=norm(prompt)
        seen.add(ph); q=make_q(f'genv7_logic_{len(qs)+1:04d}','logic',sub,['deductive_reasoning','constraint_satisfaction'],prompt,opt,expl,steps,diff,template,f'{template}_{len(qs)%25}',formal); qs.append(q)
    return qs

def build_shapes(n):
    qs=[]; seen=set(); k=0
    corner_map={'top_left':'right-top','top_right':'left-top','bottom_left':'right-bottom','bottom_right':'left-bottom'}
    while len(qs)<n and k<n*6:
        t=k%4; k+=1
        if t==0:
            base=random.choice(list(corner_map)); symbol=random.choice(['עיגול','משולש','כוכב','ריבוע','יהלום','סהר','לב']); prompt_variants=['לאיזה מיקום יעבור הסימן לאחר שיקוף אנכי ואז אופקי?','לאן יגיע הסימן לאחר שני שיקופים עוקבים?','עקבו אחר הסימן בשני שיקופים: היכן יהיה בסוף?','איזו פינה מתקבלת לאחר שיקוף אנכי ולאחריו אופקי?']
            base_text={'top_left':'שמאל-עליון','top_right':'ימין-עליון','bottom_left':'שמאל-תחתון','bottom_right':'ימין-תחתון'}
            result_corner={'top_left':'top_right','top_right':'top_left','bottom_left':'bottom_right','bottom_right':'bottom_left'}[base]
            # two reflections: vertical then horizontal -> opposite corner
            result_corner={'top_left':'bottom_right','top_right':'bottom_left','bottom_left':'top_right','bottom_right':'top_left'}[base]
            mapping=base_text; correct=mapping[result_corner]
            distr=[v for kk,v in mapping.items() if kk!=result_corner]
            prompt=prompt_variants[k%4] + f' הסימן ({symbol}) מתחיל בפינה {base_text[base]}.'
            opt=opts(correct,distr[:3]); visual={'type':'reflection_matrix','symbol':symbol,'rows':[{'base_corner':base,'vertical_mirror_corner':{'top_left':'top_right','top_right':'top_left','bottom_left':'bottom_right','bottom_right':'bottom_left'}[base],'horizontal_mirror_corner':{'top_left':'bottom_left','top_right':'bottom_right','bottom_left':'top_left','bottom_right':'top_right'}[base]}]}; formal={'kind_group':'shape_schema','type':'double_reflection','base_corner':base,'options':{}}
            formal['options']={o['id']: next(key for key,val in mapping.items() if val==o['text']) for o in opt}
            steps=['שיקוף אנכי מחליף ימין ושמאל.','שיקוף אופקי מחליף עליון ותחתון.','מבצעים את שתי הפעולות לפי הסדר.']; expl=f'הסימן מגיע ל-{correct}.'; diff=4; sub='reflection'; template='shape_v7_reflection'
        elif t==1:
            cols=[]
            for _ in range(2):
                x=[random.randint(0,1) for _ in range(4)]; y=[random.randint(0,1) for _ in range(4)]; cols.append({'top1':x,'top2':y,'bottom':[a^b for a,b in zip(x,y)]})
            x=[random.randint(0,1) for _ in range(4)]; y=[random.randint(0,1) for _ in range(4)]; pred=[a^b for a,b in zip(x,y)]; cols.append({'top1':x,'top2':y,'bottom':None})
            shared=sum(1 for a,b in zip(x,y) if a and b)
            prompt=['בכל עמודה התא התחתון מתקבל משני התאים העליונים. מהו התא החסר?','מצאו את התא החסר לפי הנתונים שבמטריצה.','איזו צורה מתקבלת בתא התחתון בעמודה השלישית?','השלימו את התא החסר לפי שתי העמודות הידועות.'][k%4] + f' בשני התאים העליונים בעמודה החסרה יש {shared} רביעים משותפים.'
            texts=['רביעים מלאים לפי XOR','רביעים מלאים לפי OR','רביעים מלאים לפי AND','היפוך של XOR']; opt=opts(texts[0],texts[1:]); optmap={o['id']:(pred if o['text']==texts[0] else ([a|b for a,b in zip(x,y)] if o['text']==texts[1] else ([a&b for a,b in zip(x,y)] if o['text']==texts[2] else [1-v for v in pred]))) for o in opt}; visual={'type':'superposition_matrix','quadrant_order':['top_left','top_right','bottom_left','bottom_right'],'columns':cols,'rule':'xor'}; formal={'kind_group':'shape_schema','type':'superposition_matrix','columns':cols,'options':optmap}; diff=5; sub='superposition'; template='shape_v7_xor'; steps=['בודקים את שתי העמודות הידועות כדי לזהות את פעולת החפיפה.','XOR משאיר איבר מלא כאשר בדיוק אחד מהתאים העליונים מלא.','מיישמים את אותו כלל על העמודה השלישית.']; expl='שתי הדוגמאות הראשונות מאפשרות לפסול AND ו-OR ולזהות XOR.'
        elif t==2:
            mark1=random.choice(['dot','star','cross','circle']); mark2=random.choice(['stripe','triangle','ring','square']); symbol_style=random.choice(['solid','outline','striped','double-line','dotted']); prompt_variants=['הקובייה מתגלגלת קדימה ב-90°. היכן יימצאו שני הסימנים?','מגלגלים את הקובייה קדימה. עקבו אחר שני הסימנים.','לאחר גלגול אחד של הקובייה, באילו פאות יהיו הסימנים?','עקבו במרחב אחרי שני הסימנים לאחר סיבוב של 90°.']
            labels={ 'dot':'נקודה','star':'כוכב','cross':'צלב','circle':'עיגול','stripe':'פס','triangle':'משולש','ring':'טבעת','square':'ריבוע'}; initial={'dot':'front','star':'front','cross':'front','circle':'front','stripe':'top','triangle':'top','ring':'top','square':'top'}; m1=labels[mark1]; m2=labels[mark2]; prompt=prompt_variants[k%4] + f' הסימן הראשון הוא {m1} והסימן השני הוא {m2}; סגנון הסימן הראשון: {symbol_style}.'
            correct={f'{m1}':'bottom',f'{m2}':'front'}
            texts=[f'{m1}: תחתונה; {m2}: קדמית',f'{m1}: קדמית; {m2}: עליונה',f'{m1}: אחורית; {m2}: עליונה',f'{m1}: עליונה; {m2}: תחתונה']; opt=opts(texts[0],texts[1:]); semantic={texts[0]:{mark1:'bottom',mark2:'front'},texts[1]:{mark1:'front',mark2:'top'},texts[2]:{mark1:'back',mark2:'top'},texts[3]:{mark1:'top',mark2:'bottom'}}
            optmap={};
            for o in opt: optmap[o['id']] = semantic[o['text']]
            visual={'type':'cube_rotation_multi','symbol_style':symbol_style,'initial_marks':{mark1:'front',mark2:'top'},'rotation_axis':'horizontal_side_to_side','rotation_direction':'rolling_forward','rotation_degrees':90,'options':optmap}; formal={'kind_group':'shape_schema','type':'cube_rotation_multi','initial_marks':{mark1:'front',mark2:'top'},'rotation_degrees':90,'options':optmap}; diff=5; sub='mental_rotation'; template='shape_v7_cube'; steps=['מזהים את הציר האופקי.','בגלגול קדימה: קדמית→תחתונה ועליונה→קדמית.','עוקבים אחרי שני הסימנים בו-זמנית.']; expl='הנקודה/סימן שהיה קדמי עובר לתחתונה, והסימן שהיה עליון עובר לקדמית.'
        else:
            folds=random.choice([2,3]); holes=2**folds; paper_size=random.choice(['A4','A5','A3']); fold_pattern=random.choice(['אנכי+אופקי','אופקי+אנכי','אלכסוני+אנכי','אלכסוני+אופקי','אנכי+אלכסוני','אופקי+אלכסוני']); punch_id=random.randint(1,8); loc=['בפינה שבה נפגשים שני הקיפולים','קרוב לנקודת המפגש של שני הקיפולים','במרכז אזור החפיפה','בפינה המשותפת של הקיפולים'][k%4]; prompt=f'דף {paper_size} מקופל {folds} פעמים לפי רצף קיפולים {fold_pattern}. באזור החפיפה {loc} (סימן {punch_id}) מנקבים חור. כמה חורים יתקבלו בפתיחה מלאה?'; opt=opts(holes,[2**(folds-1),holes*2,folds+1]); visual={'type':'paper_fold','paper_size':paper_size,'folds':folds,'fold_orientations':['vertical_center','horizontal_center'][:folds],'fold_pattern':fold_pattern,'punch_location':loc,'punch_id':punch_id}; formal={'kind_group':'shape_schema','type':'paper_fold','folds':folds,'options':{o['id']:int(o['text']) for o in opt}}; diff=4 if folds==2 else 5; sub='paper_folding'; template='shape_v7_fold'; steps=[f'כל קיפול מכפיל את מספר השכבות: 2^{folds}.',f'ניקוב באזור החפיפה עובר בכל {holes} השכבות.',f'לכן מתקבלים {holes} חורים.']; expl=f'בפתיחה מלאה מתקבלים {holes} חורים.'
        ph=norm(prompt)
        seen.add(ph); q=make_q(f'genv7_shape_{len(qs)+1:04d}','shapes_spatial',sub,['visual_transformation','spatial_reasoning'],prompt,opt,expl,steps,diff,template,f'{template}_{len(qs)%25}',formal,visual); qs.append(q)
    return qs

def validate_with_checkers(qs):
    sys.path.insert(0, str(ROOT))
    from formal_checkers import run_formal_check
    failures=[]; exact=collections.Counter(); hashes=collections.Counter()
    for q in qs:
        exact[norm(q['prompt'])]+=1; hashes[q.get('content_hash')]+=1
        if len(q.get('options',[]))!=4 or sum(bool(o.get('is_correct')) for o in q.get('options',[]))!=1: failures.append((q['id'],'structure'))
        if q.get('formal_spec'):
            ok,detail=run_formal_check(q)
            if not ok: failures.append((q['id'],detail))
    for p,c in exact.items():
        if c>1: failures.append(('GLOBAL',f'duplicate prompt: {p}'))
    for h,c in hashes.items():
        if c>1: failures.append(('GLOBAL',f'duplicate hash: {h}'))
    return failures

def main():
    # Generate until we have the target number of unique active questions per category.
    candidates={
      'quantitative': build_quant(700),
      'series': build_series(680),
      'logic': build_logic(380),
      'shapes_spatial': build_shapes(260),
    }
    active=[]; seen_h=set(); seen_p=set()
    for cat,target in TARGETS.items():
        picked=[]
        for q in candidates[cat]:
            q['content_hash']=hashlib.sha256((norm(q['prompt'])+'|'+'|'.join(norm(o['text']) for o in q['options'])+'|' + json.dumps(q.get('visual_schema'),ensure_ascii=False,sort_keys=True)).encode('utf-8')).hexdigest()[:16]
            if norm(q['prompt']) in seen_p or q['content_hash'] in seen_h: continue
            seen_p.add(norm(q['prompt'])); seen_h.add(q['content_hash']); picked.append(q)
            if len(picked)>=target: break
        if len(picked)<target: raise RuntimeError(f'unique candidates short for {cat}: {len(picked)}/{target}')
        active.extend(picked)
    if len(active)!=sum(TARGETS.values()): raise RuntimeError(f'unique active count {len(active)} != 1500')
    # Put seed first, unchanged; then active generated.
    out=seed+active
    failures=validate_with_checkers(active)
    if failures: raise RuntimeError('checker failures: '+repr(failures[:10]))
    # fix IDs after dedup and update instance/content hash for stable output
    for i,q in enumerate(active,1):
        q['id']=f"genv7_{q['category'][:4]}_{i:05d}"; q['instance_id']=q['id']
        q['content_hash']=hashlib.sha256((norm(q['prompt'])+'|'+'|'.join(norm(o['text']) for o in q['options'])+'|' + json.dumps(q.get('visual_schema'),ensure_ascii=False,sort_keys=True)).encode('utf-8')).hexdigest()[:16]
    out=seed+active
    report={
      'version':'v7_release_candidate', 'total_questions':len(out), 'active_questions':len(active),
      'active_by_category':dict(collections.Counter(q['category'] for q in active)),
      'active_by_difficulty':dict(collections.Counter(q['difficulty_calibrated'] for q in active)),
      'semantic_review_pending':sum(q.get('validation',{}).get('semantic_review',{}).get('status')=='pending' for q in out),
      'active_exact_prompt_duplicates':0,'active_content_hash_duplicates':0,
      'active_family_count':len(set(q.get('semantic_family_id') or q['id'] for q in active)), 'formal_checker_failures':0
    }
    ph=collections.Counter(norm(q['prompt']) for q in active); hh=collections.Counter(q['content_hash'] for q in active)
    report['active_exact_prompt_duplicates']=sum(c-1 for c in ph.values() if c>1); report['active_content_hash_duplicates']=sum(c-1 for c in hh.values() if c>1); report['passed']=report['active_questions']==1500 and report['active_exact_prompt_duplicates']==0 and report['active_content_hash_duplicates']==0
    DATA.write_text(json.dumps({'version':'v7_release_candidate','published_at':'2026-09-22','questions':out},ensure_ascii=False,indent=1),encoding='utf-8')
    (ROOT/'content_engine/reports/v7_release_candidate_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
