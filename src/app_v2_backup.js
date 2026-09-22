const state={
  questions:[], profile:null,
  history:{shown:[],attempts:[],mistakes:[],sessions:[]},
  currentSession:null,
  view:'home'
};
const KEY='gifted_training_state_v2';
const catLabels={logic:'היגיון והסקה',analogies:'אנלוגיות',quantitative:'חשיבה כמותית',series:'סדרות וחוקיות',shapes_spatial:'צורות ומרחבי'};
const letter=['א','ב','ג','ד'];

function loadStore(){
  try{
    const x=JSON.parse(localStorage.getItem(KEY)||'{}');
    if(x.profile)state.profile=x.profile;
    if(x.history)state.history={...state.history,...x.history};
    for(const k of ['shown','attempts','mistakes','sessions']) if(!Array.isArray(state.history[k])) state.history[k]=[];
  }catch(e){/* fresh store */}
}
function saveStore(){localStorage.setItem(KEY,JSON.stringify({profile:state.profile,history:state.history}));}
function uid(){return Math.random().toString(36).slice(2)+Date.now().toString(36)}
function questionIsPublished(q){return q?.validation?.approved_for_pool===true;}
function approvedPool(sim=false){return state.questions.filter(q=>questionIsPublished(q)&&(!sim||(q.mode_compatibility||[]).includes('simulation')));}
function recentIds(windowSize=80){return new Set(state.history.shown.slice(-windowSize));}
function familyKey(q){return q.semantic_family_id||`${q.category}:${q.subcategory||'general'}`;}
function recentFamilies(windowSize=40){
  const ids=recentIds(windowSize*2), families=new Set();
  for(const q of state.questions){if(ids.has(q.id))families.add(familyKey(q))}
  return families;
}
function attemptStats(){
  const bySkill={};
  for(const a of state.history.attempts){
    for(const skill of (a.skills||[])){
      const s=bySkill[skill]||(bySkill[skill]={n:0,c:0,time:0}); s.n++; if(a.correct)s.c++; s.time+=a.time||0;
    }
  }
  return bySkill;
}
function scoreAdaptive(q){
  const relevant=state.history.attempts.filter(a=>a.questionId===q.id);
  const skills=attemptStats();
  let unseenBonus=relevant.length?0:25;
  let need=0;
  for(const sk of (q.skills||[])){
    const s=skills[sk];
    if(!s) need+=18;
    else need+=Math.max(0,1-s.c/s.n)*35;
  }
  const recentPenalty=recentIds(50).has(q.id)?-100:0;
  const familyPenalty=recentFamilies(30).has(familyKey(q))?-20:0;
  const difficultyFit=(q.difficulty_calibrated||q.difficulty_prior||3)*2;
  return unseenBonus+need+difficultyFit+recentPenalty+familyPenalty;
}
function pickQuestions(count,{category='all',difficulty='all',simulation=false,smart=false,subcategory=null}={}){
  const pool=approvedPool(simulation).filter(q=>category==='all'||q.category===category).filter(q=>difficulty==='all'||String(q.difficulty_calibrated||q.difficulty_prior)===String(difficulty)).filter(q=>!subcategory||q.subcategory===subcategory);
  const rec=recentIds(); const fam=recentFamilies();
  let fresh=pool.filter(q=>!rec.has(q.id)&&!fam.has(familyKey(q)));
  if(fresh.length<count) fresh=pool.filter(q=>!rec.has(q.id));
  if(fresh.length<count) fresh=pool;
  fresh=smart?fresh.sort((a,b)=>scoreAdaptive(b)-scoreAdaptive(a)):fresh.sort(()=>Math.random()-0.5);
  return fresh.slice(0,count);
}
function action(icon,title,sub,fn){return `<button class="card action-card" onclick="${fn}"><div class="emoji">${icon}</div><div class="action-title">${title}</div><div class="action-sub">${sub}</div></button>`}
function miniMetric(t,v,sub=''){return `<div class="card"><div class="muted">${t}</div><div class="stat-big" style="font-size:32px">${v}</div>${sub?`<div class="muted">${sub}</div>`:''}</div>`}
function calcStreak(){
  let s=0;
  for(let i=state.history.attempts.length-1;i>=0;i--){if(state.history.attempts[i].correct)s++;else break}
  return s;
}
function renderHome(){
  const pool=approvedPool(); const att=state.history.attempts; const correct=att.filter(a=>a.correct).length; const rate=att.length?Math.round(correct/att.length*100):0;
  const name=state.profile?.display_name||'אלוף/ת';
  document.querySelector('#view').innerHTML=`
  <section class="hero">
    <div class="hero-card"><div class="eyebrow">האימון שלך למבחן כיתה ז׳</div><h1>היי ${esc(name)} 👋<br>מוכן/ה לאתגר?</h1><p>תרגול קצר, חכם ומדורג. האפליקציה לומדת מהביצועים שלך ובוחרת מה לתרגל הלאה.</p><div class="row"><button class="btn btn-accent" onclick="startQuick()">⚡ 10 שאלות</button><button class="btn btn-primary" onclick="startAdaptive()">🧠 אימון אדפטיבי</button></div></div>
    <div class="hero-stat"><div class="muted">התקדמות עד עכשיו</div><div class="stat-big">${rate}%</div><div class="muted">${correct} נכונות מתוך ${att.length}</div><div class="space"></div><div class="pill">${pool.length} שאלות פעילות</div><div class="footer-note">רק שאלות שעברו תנאי פרסום מוצגות לילד.</div></div>
  </section>
  <div class="section-title"><h2>איך בא לך להתאמן?</h2></div>
  <section class="grid grid-3">
    ${action('⚡','אימון מהיר','10 שאלות מעורבות','startQuick()')}
    ${action('🎯','לפי נושא','בחר תחום ותת-תחום','showPracticePicker()')}
    ${action('🧠','אדפטיבי','המנוע בוחר לפי הביצועים','startAdaptive()')}
    ${action('⏱️','אימון 20','20 שאלות עם 15 דקות','startFixed(20,true,false)')}
    ${action('📝','סימולציה','מצב מבחן עם 20 שאלות','startSimulation()')}
    ${action('🔥','5 דקות','כמה שיותר נכון ב-5 דקות','startFixed(6,true,true)')}
  </section>
  <div class="section-title"><h2>התקדמות</h2><button class="btn btn-ghost" onclick="renderProgress()">דוח מלא</button></div>
  <section class="grid grid-3">
    ${miniMetric('נכונות',rate+'%')}
    ${miniMetric('רצף',calcStreak(),'תשובות נכונות רצופות')}
    ${miniMetric('טעויות לחזרה',state.history.mistakes.length)}
  </section>`;
}
function showPracticePicker(){
  const cards=Object.entries(catLabels).map(([k,v])=>{const n=approvedPool().filter(q=>q.category===k).length;return `<button class="card action-card" onclick="startCategory('${k}')"><div class="action-title">${v}</div><div class="action-sub">${n} שאלות פעילות</div></button>`}).join('');
  document.querySelector('#view').innerHTML=`<div class="section-title"><h2>בחר תחום</h2><button class="btn btn-ghost" onclick="renderHome()">חזרה</button></div><div class="grid grid-3">${cards}</div>`;
}
function startQuick(){startFixed(10,false,false)}
function startAdaptive(){startSession(pickQuestions(10,{smart:true}),{mode:'adaptive',timed:false,timeLimit:0})}
function startCategory(cat){startSession(pickQuestions(10,{category:cat,smart:true}),{mode:'topic',timed:false,timeLimit:0})}
function startFixed(n,timed=false,fast=false){startSession(pickQuestions(n),{mode:fast?'5 דקות':String(n),timed,timeLimit:fast?5*60:(timed?15*60:0),fast})}
function startSimulation(){const qs=pickQuestions(20,{simulation:true,smart:false});if(qs.length<10){alert('כרגע אין מספיק שאלות שאושרו לסימולציה. אפשר לתרגל במצב רגיל עד שהמאגר יורחב.');return}startSession(qs,{mode:'simulation',timed:true,timeLimit:25*60,fast:false})}
function startSession(qs,opt){
  if(!qs.length){alert('אין כרגע מספיק שאלות מאושרות במאגר.');return}
  state.currentSession={id:uid(),qs,idx:0,answers:[],start:Date.now(),perQuestionStart:Date.now(),hintUsed:false,...opt};
  renderSession();
}
function sessionAnswered(q){return state.currentSession?.answers.find(a=>a.questionId===q.id)}
function renderSession(){
  const s=state.currentSession,q=s.qs[s.idx]; if(!q){finishSession();return}
  const answered=sessionAnswered(q); const pct=Math.round(((s.idx+(answered?1:0))/s.qs.length)*100); const remain=s.timed?Math.max(0,s.timeLimit-Math.floor((Date.now()-s.start)/1000)):null;
  document.querySelector('#view').innerHTML=`<div class="session"><div class="session-head"><div><div class="q-num">שאלה ${s.idx+1} מתוך ${s.qs.length}</div><div class="muted">${catLabels[q.category]||''} · רמה ${q.difficulty_calibrated||q.difficulty_prior||'-'}</div></div><div class="row"><span class="pill">${s.mode==='simulation'?'מצב מבחן':s.mode}</span>${s.timed?`<span class="pill" id="timer">${formatTime(remain)}</span>`:''}</div></div><div class="progress"><div style="width:${pct}%"></div></div><div class="card question-card"><div class="q-meta"><div class="difficulty">${(q.skills||[]).slice(0,3).join(' · ')}</div>${q.prerequisite_knowledge?.length?`<div class="tag">דורש ידע קודם</div>`:''}</div><div class="prompt">${esc(q.prompt)}</div>${renderVisual(q)}<div class="option-grid">${(q.options||[]).map((o,i)=>optionHtml(q,o,i,answered,s.mode==='simulation')).join('')}</div>${answered&&s.mode!=='simulation'?feedbackHtml(q,answered):''}${!answered&&q.hint&&s.mode!=='simulation'?`<div class="row" style="margin-top:14px"><button class="btn btn-ghost" onclick="showHint()">💡 רמז</button><span id="hintBox"></span></div>`:''}</div>${answered?`<div class="row" style="justify-content:space-between;margin-top:14px"><button class="btn btn-ghost" onclick="prevQuestion()" ${s.idx===0?'disabled':''}>חזרה</button><button class="btn btn-primary" onclick="nextQuestion()">${s.idx===s.qs.length-1?'סיום':'המשך'}</button></div>`:''}</div>`;
  if(s.timed)startTimerTick();
}
function optionHtml(q,o,i,answered,sim){let cls='option';if(answered){if(o.id===q.correct_option_id)cls+=' correct';if(o.id===answered.chosenOptionId&&!answered.correct)cls+=' wrong';if(sim)cls+=' disabled'}return `<button class="${cls}" onclick="answer('${q.id}','${o.id}')"><span class="letter">${letter[i]||i+1}</span>${esc(o.text)}</button>`}
function answer(qid,optId){
  const s=state.currentSession,q=s.qs[s.idx]; if(s.answers.some(a=>a.questionId===qid))return;
  const time=Math.max(1,Math.round((Date.now()-s.perQuestionStart)/1000)); const correct=optId===q.correct_option_id;
  const a={questionId:qid,chosenOptionId:optId,correct,time,skills:q.skills||[],difficulty:q.difficulty_calibrated||q.difficulty_prior,category:q.category,subcategory:q.subcategory,semantic_family_id:familyKey(q),timestamp:Date.now()};
  s.answers.push(a);s.perQuestionStart=Date.now();state.history.attempts.push(a);state.history.shown.push(qid);
  if(!correct&&!state.history.mistakes.some(m=>m.questionId===qid))state.history.mistakes.push({questionId:qid,skills:q.skills||[],category:q.category,subcategory:q.subcategory,createdAt:Date.now()});
  saveStore();renderSession();
}
function showHint(){const q=state.currentSession.qs[state.currentSession.idx];const el=document.querySelector('#hintBox');if(el){el.innerHTML=`<span class="hint-text">${esc(q.hint)}</span>`;state.currentSession.hintUsed=true;}}
function feedbackHtml(q,a){return `<div class="feedback ${a.correct?'good':'bad'}"><h3>${a.correct?'✅ נכון!':'❌ לא הפעם'}</h3><div class="explain">${esc(q.explanation||'')}</div>${q.reasoning_steps?.length?`<details style="margin-top:10px"><summary><b>איך לחשוב על זה</b></summary><ol class="steps">${q.reasoning_steps.map(x=>`<li>${esc(x)}</li>`).join('')}</ol></details>`:''}</div>`}
function nextQuestion(){const s=state.currentSession;if(s.idx>=s.qs.length-1){finishSession();return}s.idx++;s.perQuestionStart=Date.now();renderSession()}
function prevQuestion(){const s=state.currentSession;if(s.idx>0){s.idx--;s.perQuestionStart=Date.now();renderSession()}}
function finishSession(){const s=state.currentSession;if(!s)return;const completed=s.answers.length;const correct=s.answers.filter(a=>a.correct).length;state.history.sessions.push({id:s.id,mode:s.mode,questionCount:s.qs.length,answered:completed,correct,score:s.qs.length?Math.round(correct/s.qs.length*100):0,duration:Math.round((Date.now()-s.start)/1000),timestamp:Date.now()});saveStore();renderResults(s);state.currentSession=null;}
function renderResults(s){
  const correct=s.answers.filter(a=>a.correct).length, answered=s.answers.length, rate=s.qs.length?Math.round(correct/s.qs.length*100):0;
  const by={};s.qs.forEach(q=>{by[q.category] ||= {n:0,c:0};by[q.category].n++;if(s.answers.find(x=>x.questionId===q.id)?.correct)by[q.category].c++});
  document.querySelector('#view').innerHTML=`<div class="results-hero card"><div class="eyebrow">${s.mode==='simulation'?'סימולציה':'אימון'} הסתיים</div><div class="score-ring">${rate}%</div><div class="muted">${correct} נכונות מתוך ${answered} שאלות שנענו · ${s.qs.length-answered} ללא תשובה</div><div class="space"></div><div class="row" style="justify-content:center"><button class="btn btn-primary" onclick="renderHome()">חזרה לבית</button><button class="btn btn-ghost" onclick="renderMistakes()">תרגול טעויות</button></div></div><div class="section-title"><h2>פירוט לפי תחום</h2></div><div class="grid grid-3">${Object.entries(by).map(([k,v])=>`<div class="card"><div class="muted">${catLabels[k]||k}</div><div style="font-size:28px;font-weight:800">${v.n?Math.round(v.c/v.n*100):0}%</div><div class="barline"><div class="track"><div class="fill" style="width:${v.n?Math.round(v.c/v.n*100):0}%"></div></div></div></div>`).join('')}</div>`;
}
function renderProgress(){
  const att=state.history.attempts; const cats=Object.keys(catLabels).map(k=>{const a=att.filter(x=>x.category===k);return [k,a.length?Math.round(a.filter(x=>x.correct).length/a.length*100):0,a.length]});
  document.querySelector('#view').innerHTML=`<div class="section-title"><h2>ההתקדמות שלי</h2><button class="btn btn-ghost" onclick="renderHome()">חזרה</button></div><div class="grid grid-3">${cats.map(([k,r,n])=>`<div class="card"><div class="muted">${catLabels[k]}</div><div style="font-size:32px;font-weight:800">${r}%</div><div class="muted">${n} ניסיונות</div><div class="barline"><div class="track"><div class="fill" style="width:${r}%"></div></div></div></div>`).join('')}</div><div class="section-title"><h2>רצף</h2></div><div class="card"><div class="stat-big" style="font-size:42px">${calcStreak()} 🔥</div><div class="muted">תשובות נכונות רצופות</div></div>`;
}
function renderMistakes(){
  const rows=state.history.mistakes.slice().reverse().map(m=>{const q=state.questions.find(x=>x.id===m.questionId);return q?`<tr><td>${esc(q.prompt.slice(0,110))}${q.prompt.length>110?'…':''}</td><td>${catLabels[q.category]}</td><td>${q.difficulty_calibrated||q.difficulty_prior}</td><td><button class="btn btn-ghost" onclick="practiceSkill('${q.category}','${q.subcategory||''}')">תרגל skill דומה</button></td></tr>`:''}).join('');
  document.querySelector('#view').innerHTML=`<div class="section-title"><h2>הטעויות שלי</h2><button class="btn btn-ghost" onclick="renderHome()">חזרה</button></div>${rows?`<div class="card"><table class="table"><thead><tr><th>שאלה</th><th>תחום</th><th>רמה</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`:`<div class="notice">אין כאן טעויות עדיין.</div>`}`;
}
function practiceSkill(cat,sub){const qs=pickQuestions(6,{category:cat,subcategory:sub,smart:true});startSession(qs,{mode:'חיזוק skill',timed:false,timeLimit:0})}
function renderParent(){
  const att=state.history.attempts,correct=att.filter(x=>x.correct).length,rate=att.length?Math.round(correct/att.length*100):0;
  document.querySelector('#view').innerHTML=`<div class="section-title"><h2>לוח הורה</h2><button class="btn btn-ghost" onclick="renderHome()">חזרה</button></div><div class="notice">הנתונים נשמרים כרגע במכשיר בלבד. אין כאן תחזית קבלה או ציון רשמי.</div><div class="space"></div><div class="grid grid-3">${miniMetric('דיוק כולל',rate+'%')}${miniMetric('שאלות',att.length)}${miniMetric('טעויות',state.history.mistakes.length)}</div><div class="section-title"><h2>מה כדאי לחזק?</h2></div><div class="card">${weakAreaHtml()}</div>`;
}
function weakAreaHtml(){
  const out=Object.keys(catLabels).map(k=>{const a=state.history.attempts.filter(x=>x.category===k);return {k,n:a.length,r:a.length?a.filter(x=>x.correct).length/a.length:1}}).sort((a,b)=>a.r-b.r);
  return out.map(z=>`<div class="row" style="justify-content:space-between;padding:8px 0"><span>${catLabels[z.k]}</span><span class="pill">${z.n?Math.round(z.r*100):0}%</span></div>`).join('');
}
function renderAdmin(){
  const qs=state.questions; const byCat=Object.keys(catLabels).map(k=>[k,qs.filter(q=>q.category===k).length]);
  document.querySelector('#view').innerHTML=`<div class="section-title"><h2>Admin · מאגר תוכן</h2><button class="btn btn-ghost" onclick="renderHome()">חזרה</button></div><div class="notice">מסך פיתוח. seed יכול להישאר במאגר גם אם אינו מפורסם.</div><div class="grid grid-4">${miniMetric('סה״כ seed',qs.length)}${miniMetric('פעילות',approvedPool().length)}${miniMetric('seed בלבד',qs.filter(q=>!questionIsPublished(q)).length)}${miniMetric('צורניות',qs.filter(q=>q.content_type==='visual'||q.category==='shapes_spatial').length)}</div><div class="section-title"><h2>התפלגות</h2></div><div class="grid grid-4">${byCat.map(([k,n])=>miniMetric(catLabels[k],n)).join('')}</div><div class="space"></div><div class="card"><table class="table"><thead><tr><th>ID</th><th>תחום</th><th>רמה</th><th>פרסום</th></tr></thead><tbody>${qs.slice(0,160).map(q=>`<tr><td>${q.id}</td><td>${catLabels[q.category]||q.category}</td><td>${q.difficulty_calibrated||q.difficulty_prior||'-'}</td><td>${questionIsPublished(q)?'<span class="pill">פעילה</span>':'<span class="tag">seed-only</span>'}${q.category==='analogies'&&q.validation?.semantic_review?.required?'<span class="tag">semantic review</span>':''}</td></tr>`).join('')}</tbody></table></div>`;
}
function renderSettings(){document.querySelector('#view').innerHTML=`<div class="section-title"><h2>הגדרות</h2><button class="btn btn-ghost" onclick="renderHome()">חזרה</button></div><div class="card"><h3>פרופיל</h3><p class="muted">השם נשמר מקומית במכשיר.</p><div class="row"><input id="nameInput" value="${esc(state.profile?.display_name||'')}" placeholder="שם הילד/ה" style="flex:1;padding:12px 14px;border:1px solid var(--line);border-radius:12px;font:inherit"><button class="btn btn-primary" onclick="saveProfile()">שמור</button></div></div><div class="space"></div><div class="card"><h3>איפוס התקדמות</h3><p class="muted">מוחק את ההיסטוריה המקומית בלבד.</p><button class="btn btn-danger" onclick="resetProgress()">איפוס</button></div>`}
function saveProfile(){state.profile={display_name:document.querySelector('#nameInput').value.trim()||'אלוף/ת'};saveStore();renderHome()}
function resetProgress(){if(confirm('למחוק את כל ההתקדמות המקומית?')){state.history={shown:[],attempts:[],mistakes:[],sessions:[]};saveStore();renderSettings()}}
function renderVisual(q){
  const s=q.visual_schema;if(!s)return'';
  try{
    if(s.type==='superposition_matrix'){
      return `<div class="visual"><div class="visual-title">מטריצה של חפיפות</div><div class="visual-columns">${s.columns.map(col=>`<div class="visual-column"><div class="quad">${(col.top1||[]).map(v=>`<div class="${v?'on':''}"></div>`).join('')}</div><div class="op">⊕</div><div class="quad">${(col.top2||[]).map(v=>`<div class="${v?'on':''}"></div>`).join('')}</div><div class="op">=</div><div class="quad">${(col.bottom||[null,null,null,null]).map(v=>`<div class="${v===null?'question-cell':v?'on':''}">${v===null?'?':''}</div>`).join('')}</div></div>`).join('')}</div></div>`;
    }
    if(s.type==='matrix3x3'||s.type==='hidden_dual_rule_matrix'){
      const cells=Array.isArray(s.cells)?s.cells.flat():Object.keys(s.cells||{}).sort((a,b)=>{const [ra,ca]=a.split(',').map(Number),[rb,cb]=b.split(',').map(Number);return ra-rb||ca-cb}).map(k=>s.cells[k]);
      return `<div class="visual"><div class="matrix">${cells.slice(0,9).map(c=>{if(c===null)return '<div class="matrix-cell"><span class="question-mark">?</span></div>';const fill=c.fill==='solid';return `<div class="matrix-cell"><div class="shape-count">${c.count??''}</div><div class="square-fill ${fill?'solid':'empty'}"></div></div>`}).join('')}</div></div>`;
    }
    if(s.type==='cube_rotation'||s.type==='cube_rotation_multi'){
      const multi=s.initial_marks||{};return `<div class="visual"><div class="cube-net"><div></div><div class="cube-face top">${multi.stripe?'▤':'▲'}</div><div></div><div class="cube-face front">${multi.dot?'●':'◆'}</div><div class="cube-face side">◀</div><div class="cube-face right">▶</div></div><div class="muted" style="margin-top:10px">סיבוב ${s.rotation_degrees||90}°</div></div>`;
    }
    if(s.type==='paper_fold')return `<div class="visual"><div class="paper"><span class="fold-v"></span><span class="fold-h"></span><span class="punch"></span></div><div class="muted">קיפול וניקוב</div></div>`;
    if(s.type==='reflection_matrix'||s.type==='single_reflection')return `<div class="visual"><div class="reflect-demo"><span class="tri"></span><span class="mirror"></span></div><div class="muted">שיקוף</div></div>`;
    if(s.type==='combined_transform_sequence')return `<div class="visual"><div class="transform-demo"><span>↻</span><span>↔</span><span>↻</span><span>↔</span><span>?</span></div></div>`;
    return `<div class="visual"><span class="pill">שאלה חזותית</span></div>`;
  }catch(e){return `<div class="visual"><span class="muted">תצוגה חזותית</span></div>`}
}
function startTimerTick(){clearTimeout(window._timer);window._timer=setTimeout(()=>{const s=state.currentSession;if(!s||!s.timed)return;const remain=s.timeLimit-Math.floor((Date.now()-s.start)/1000);if(remain<=0){finishSession();return}const el=document.querySelector('#timer');if(el){el.textContent=formatTime(remain)}startTimerTick()},500)}
function formatTime(sec){const m=Math.floor(sec/60),s=sec%60;return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`}
function esc(x=''){return String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function boot(){loadStore();try{const r=await fetch('data/questions.json');const d=await r.json();state.questions=d.questions||[];renderHome();if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js').catch(()=>{});}catch(e){document.querySelector('#view').innerHTML='<div class="card"><h2>לא הצלחתי לטעון את המאגר</h2><p class="muted">בדקו שהאפליקציה רצה דרך שרת מקומי ולא בפתיחה ישירה של הקובץ.</p></div>';}}
document.querySelector('#parentBtn').onclick=renderParent;document.querySelector('#settingsBtn').onclick=renderSettings;
window.renderHome=renderHome;window.startQuick=startQuick;window.startAdaptive=startAdaptive;window.showPracticePicker=showPracticePicker;window.startFixed=startFixed;window.startSimulation=startSimulation;window.startCategory=startCategory;window.answer=answer;window.nextQuestion=nextQuestion;window.prevQuestion=prevQuestion;window.renderProgress=renderProgress;window.renderMistakes=renderMistakes;window.practiceSkill=practiceSkill;window.renderParent=renderParent;window.renderAdmin=renderAdmin;window.renderSettings=renderSettings;window.saveProfile=saveProfile;window.resetProgress=resetProgress;window.showHint=showHint;
boot();
if(location.hash==='#admin')setTimeout(renderAdmin,200);
