const state={
  questions:[], profile:null, profiles:[], activeProfileId:null,
  history:{shown:[],attempts:[],mistakes:[],sessions:[],daily:{date:null,ids:[],completed:false}},
  currentSession:null,
  view:'home'
};
const KEY='gifted_training_state_v15';
const LEGACY_KEYS=['gifted_training_state_v10','gifted_training_state_v9','gifted_training_state_v3'];
function emptyHistory(){return {shown:[],attempts:[],mistakes:[],sessions:[],daily:{date:null,ids:[],completed:false}}}
function normalizeHistory(h={}){const out={...emptyHistory(),...h};for(const k of ['shown','attempts','mistakes','sessions'])if(!Array.isArray(out[k]))out[k]=[];if(!out.daily||typeof out.daily!=='object')out.daily={date:null,ids:[],completed:false};return out}
function activeProfile(){return state.profiles.find(p=>p.id===state.activeProfileId)||null}
function syncActiveProfile(){const p=activeProfile();state.profile=p?{display_name:p.display_name,username:p.username||'',requiresPin:!!p.pinHash}:null;state.history=p?normalizeHistory(p.history):emptyHistory();if(p)p.history=state.history}
function persistProfiles(){localStorage.setItem(KEY,JSON.stringify({version:15,activeProfileId:state.activeProfileId,profiles:state.profiles}))}
async function hashText(text){const data=new TextEncoder().encode(String(text||''));const buf=await crypto.subtle.digest('SHA-256',data);return Array.from(new Uint8Array(buf)).map(b=>b.toString(16).padStart(2,'0')).join('')}
function normalizeProfile(p,i=0){return {id:p.id||uid(),display_name:p.display_name||`שחקן/ית ${i+1}`,username:p.username||'',pinHash:p.pinHash||'',createdAt:p.createdAt||Date.now(),history:normalizeHistory(p.history),resumeSession:p.resumeSession||null}}
const catLabels={logic:'היגיון והסקה',analogies:'אנלוגיות',quantitative:'חשיבה כמותית',series:'סדרות וחוקיות',shapes_spatial:'צורות ומרחב',sentence_completion:'השלמת משפטים',vocabulary:'אוצר מילים',odd_one_out:'יוצא מן הכלל',nonword_context:'מילת תפל',reading_comprehension:'הבנת הנקרא'};
const catIcons={logic:'🧠',analogies:'🔗',quantitative:'🔢',series:'📈',shapes_spatial:'🔷',sentence_completion:'✍️',vocabulary:'📚',odd_one_out:'🧩',nonword_context:'🪄',reading_comprehension:'📖'};
const letter=['א','ב','ג','ד'];

function loadStore(){
  try{
    const current=localStorage.getItem(KEY);
    if(current){
      const x=JSON.parse(current||'{}');
      state.profiles=(Array.isArray(x.profiles)?x.profiles:[]).map((p,i)=>normalizeProfile(p,i));
      state.activeProfileId=x.activeProfileId||state.profiles[0]?.id||null;
      syncActiveProfile(); return;
    }
    let legacyRaw=null;
    for(const k of LEGACY_KEYS){if(localStorage.getItem(k)){legacyRaw=localStorage.getItem(k);break}}
    if(legacyRaw){
      const x=JSON.parse(legacyRaw||'{}');
      const migrated=normalizeProfile({id:uid(),display_name:x.profile?.display_name||'שחקן/ית 1',createdAt:Date.now(),history:normalizeHistory(x.history)},0);
      state.profiles=[migrated];state.activeProfileId=migrated.id;syncActiveProfile();persistProfiles();
    }
  }catch(e){state.profiles=[];state.activeProfileId=null;syncActiveProfile()}
}
function saveStore(){const p=activeProfile();if(p){p.display_name=state.profile?.display_name||p.display_name;p.history=state.history}persistProfiles();}
function uid(){return Math.random().toString(36).slice(2)+Date.now().toString(36)}
function questionIsPublished(q){return q?.validation?.approved_for_pool===true;}
function approvedPool(sim=false){return state.questions.filter(q=>questionIsPublished(q)&&(!sim||(q.mode_compatibility||[]).includes('simulation')));}
function activePool(){return approvedPool(false)}
function recentIds(windowSize=80){return new Set(state.history.shown.slice(-windowSize));}
function familyKey(q){return q.semantic_family_id||q.template_id||q.id;}
function recentFamilies(windowSize=40){
  const ids=recentIds(windowSize*2), families=new Set();
  for(const q of state.questions) if(ids.has(q.id)) families.add(familyKey(q));
  return families;
}
function statsBySkill(){
  const by={}, now=Date.now();
  for(const a of state.history.attempts){
    const ageDays=Math.max(0,(now-(a.timestamp||now))/86400000);
    const recencyWeight=Math.max(.35,Math.exp(-ageDays/21));
    for(const sk of (a.skills||[])){
      const x=by[sk]||(by[sk]={n:0,c:0,time:0,weightedN:0,weightedC:0,lastSeen:0,wrong:0});
      x.n++; if(a.correct)x.c++; else x.wrong++; x.time+=a.time||0;
      x.weightedN+=recencyWeight; if(a.correct)x.weightedC+=recencyWeight;
      x.lastSeen=Math.max(x.lastSeen,a.timestamp||0);
    }
  }
  return by;
}
function masteryForSkill(sk){
  const x=statsBySkill()[sk];
  if(!x||!x.n) return .5;
  const accuracy=x.weightedN?x.weightedC/x.weightedN:x.c/x.n;
  const evidence=Math.min(1,x.n/8);
  return .5*(1-evidence)+accuracy*evidence;
}
function reviewUrgency(q){
  const attempts=state.history.attempts.filter(a=>a.questionId===q.id);
  if(!attempts.length)return 0;
  const last=attempts[attempts.length-1], days=(Date.now()-(last.timestamp||Date.now()))/86400000;
  if(last.correct)return days>=14?12:0;
  return days>=3?28:days>=1?18:4;
}
function weakestSkills(limit=4){
  return Object.entries(statsBySkill()).filter(([,x])=>x.n>=2).map(([sk,x])=>({sk,mastery:masteryForSkill(sk),n:x.n})).sort((a,b)=>a.mastery-b.mastery).slice(0,limit);
}
function targetDifficultyForQuestion(q){
  const vals=(q.skills||[]).map(masteryForSkill);
  const mastery=vals.length?vals.reduce((a,b)=>a+b,0)/vals.length:0.5;
  const base=Number(q.difficulty_calibrated||q.difficulty_prior||3);
  return mastery>=.88?Math.min(5,base+1):mastery<=.55?Math.max(1,base-1):base;
}
function scoreAdaptive(q){
  const skills=statsBySkill();
  const unseen=state.history.attempts.some(a=>a.questionId===q.id)?0:30;
  const freshFamily=recentFamilies(30).has(familyKey(q))?-35:15;
  const recent=recentIds(60).has(q.id)?-100:0;
  const target=targetDifficultyForQuestion(q);
  const d=Number(q.difficulty_calibrated||q.difficulty_prior||3);
  const difficultyFit=Math.max(0,20-Math.abs(target-d)*10);
  let skillNeed=0;
  for(const sk of (q.skills||[])){
    const s=skills[sk];
    if(!s) skillNeed+=28;
    else skillNeed+=Math.max(0,1-s.c/s.n)*45;
  }
  return unseen+freshFamily+recent+difficultyFit+skillNeed+reviewUrgency(q)+Math.random()*8;
}
function shuffle(a){return [...a].sort(()=>Math.random()-0.5)}
function pickQuestions(count,{category='all',difficulty='all',simulation=false,smart=false,subcategory=null,skills=[]}={}){
  let pool=approvedPool(simulation).filter(q=>category==='all'||q.category===category).filter(q=>difficulty==='all'||String(q.difficulty_calibrated||q.difficulty_prior)===String(difficulty)).filter(q=>!subcategory||q.subcategory===subcategory);
  if(skills.length) pool=pool.filter(q=>(q.skills||[]).some(s=>skills.includes(s)));
  const rec=recentIds(100), fam=recentFamilies(50);
  let fresh=pool.filter(q=>!rec.has(q.id)&&!fam.has(familyKey(q)));
  if(fresh.length<count) fresh=pool.filter(q=>!rec.has(q.id));
  if(fresh.length<count) fresh=pool;
  return (smart?fresh.sort((a,b)=>scoreAdaptive(b)-scoreAdaptive(a)):shuffle(fresh)).slice(0,count);
}
function action(icon,title,sub,fn,badge=''){return `<button class="card action-card" onclick="${fn}"><div class="emoji">${icon}</div><div class="action-title">${title}${badge?` <span class="tag">${badge}</span>`:''}</div><div class="action-sub">${sub}</div></button>`}
function miniMetric(t,v,sub=''){return `<div class="card"><div class="muted">${t}</div><div class="stat-big" style="font-size:32px">${v}</div>${sub?`<div class="muted">${sub}</div>`:''}</div>`}
function calcStreak(){
  let s=0; for(let i=state.history.attempts.length-1;i>=0;i--){if(state.history.attempts[i].correct)s++;else break} return s;
}
function todayKey(){const d=new Date();const y=d.getFullYear();const m=String(d.getMonth()+1).padStart(2,'0');const day=String(d.getDate()).padStart(2,'0');return `${y}-${m}-${day}`}
function ensureDaily(){
  const t=todayKey();
  if(state.history.daily.date!==t){
    const pool=activePool();
    const ids=shuffle(pool.map(q=>q.id)).slice(0,5);
    state.history.daily={date:t,ids,completed:false}; saveStore();
  }
}
function dailyQuestions(){ensureDaily();return state.history.daily.ids.map(id=>state.questions.find(q=>q.id===id)).filter(Boolean)}
function updateTopUser(){const el=document.querySelector('#topUserName');if(el)el.textContent=state.profile?.display_name||'משתמש'}
function renderHome(){
  updateTopUser();
  const pool=activePool(); const att=state.history.attempts; const correct=att.filter(a=>a.correct).length; const rate=att.length?Math.round(correct/att.length*100):0;
  const pendingSemantic=state.questions.filter(q=>q.validation?.semantic_review?.status==='pending').length;
  const name=state.profile?.display_name||'אלוף/ת'; const dqs=dailyQuestions();
  document.querySelector('#view').innerHTML=`
  <section class="hero">
    <div class="hero-card"><div class="eyebrow">האימון שלך למבחן כיתה ז׳</div><h1>היי ${esc(name)} 👋<br>מוכן/ה לאתגר?</h1><p>תרגול קצר, חכם ומדורג. האפליקציה מתאימה את הקושי לפי הביצועים שלך ושומרת על גיוון.</p><div class="row"><button class="btn btn-accent" onclick="startQuick()">⚡ 10 שאלות</button><button class="btn btn-primary" onclick="startAdaptive()">🧠 אדפטיבי</button></div></div>
    <div class="hero-stat"><div class="muted">התקדמות עד עכשיו</div><div class="stat-big">${rate}%</div><div class="muted">${correct} נכונות מתוך ${att.length}</div><div class="space"></div><div class="row"><span class="pill">${pool.length} שאלות פעילות</span><span class="pill">🔥 רצף ${calcStreak()}</span></div><div class="footer-note">הצגת שאלות מתבצעת מתוך מאגר מאושר בלבד.</div></div>
  </section>
  ${pendingSemantic?`<div class="notice" style="margin:18px 0">🔎 ${pendingSemantic} שאלות נמצאות בבדיקת איכות סמנטית ולא יוצגו באימון עד שיאושרו.</div>`:''}
  <div class="mode-banner practice-banner"><div><b>🎯 תרגול ולמידה</b><div class="muted">משוב, רמזים והסברים תוך כדי</div></div></div>
  <section class="grid grid-3">
    ${action('⚡','אימון מהיר','10 שאלות מעורבות','startQuick()')}
    ${action('🧠','אדפטיבי','המערכת מזהה מה כדאי לתרגל','startAdaptive()')}
    ${action('🎯','לפי נושא','בחירת תחום לתרגול','showPracticePicker()')}
    ${action('⏱️','אימון 20','20 שאלות · 15 דקות','startFixed(20,true,false)')}
    ${action('📚','אימון 40','40 שאלות מעורבות · ללא לחץ','startFixed(40,false,false)')}
    ${action('🔥','אתגר 5 דקות','כמה שאלות תפתור/י בזמן?','startTimedChallenge()')}
    ${activeProfile()?.resumeSession?action('▶️','המשך תרגול','להמשיך בדיוק מאיפה שעצרת','resumeSession()'):''}
  </section>
  <div class="mode-banner exam-banner"><div><b>📝 סימולציית מבחן מלא</b><div class="muted">90 שאלות · 90 דקות · ללא רמזים או משוב עד הסיום</div></div><button class="btn btn-primary" onclick="showSimulationIntro()">התחלת סימולציה</button></div>
  <div class="section-title"><h2>אתגר יומי</h2><button class="btn btn-ghost" onclick="startDaily()">${state.history.daily.completed?'השלמת היום':'להתחיל'}</button></div>
  <div class="card daily-card"><div><div class="action-title">5 שאלות יומיות</div><div class="muted">${dqs.length===5?'משימה קבועה להיום · '+(state.history.daily.completed?'הושלמה ✅':'עוד לא הושלמה'): 'טוען...'}</div></div><div class="daily-dots">${dqs.map((q,i)=>`<span class="daily-dot ${state.history.attempts.some(a=>a.questionId===q.id)?'done':''}">${i+1}</span>`).join('')}</div></div>
  <div class="section-title"><h2>התקדמות</h2><button class="btn btn-ghost" onclick="renderProgress()">דוח מלא</button></div>
  <section class="grid grid-3">${miniMetric('דיוק',rate+'%')}${miniMetric('רצף',calcStreak(),'תשובות נכונות רצופות')}${miniMetric('טעויות',state.history.mistakes.filter(m=>!m.resolved).length,'לחזרה')}</section>`;
}
function showPracticePicker(){
  const cards=Object.entries(catLabels).map(([k,v])=>{
    const n=activePool().filter(q=>q.category===k).length;
    if(!n) return `<div class="card action-card disabled-card"><div class="emoji">${catIcons[k]}</div><div class="action-title">${v}</div><div class="action-sub">התוכן עובר כרגע בדיקת איכות</div><span class="tag">בקרוב</span></div>`;
    return `<button class="card action-card" onclick="startCategory('${k}')"><div class="emoji">${catIcons[k]}</div><div class="action-title">${v}</div><div class="action-sub">${n} שאלות פעילות</div></button>`;
  }).join('');
  document.querySelector('#view').innerHTML=`<div class="section-title"><h2>בחר תחום</h2><button class="btn btn-ghost" onclick="renderHome()">חזרה</button></div><div class="grid grid-3">${cards}</div>`;
}
function startQuick(){startFixed(10,false,false)}
function adaptiveQuestions(count=10){
  const pool=activePool(), rec=recentIds(100), fam=recentFamilies(50);
  const categories=Object.keys(catLabels).filter(c=>pool.some(q=>q.category===c));
  const attempts=state.history.attempts;
  const categoryNeed=Object.fromEntries(categories.map(c=>{
    const a=attempts.filter(x=>x.category===c).slice(-20);
    const acc=a.length?a.filter(x=>x.correct).length/a.length:.65;
    const exposure=Math.min(1,a.length/12);
    return [c,(1-acc)*55+(1-exposure)*30];
  }));
  let candidates=pool.filter(q=>!rec.has(q.id)&&!fam.has(familyKey(q)));
  if(candidates.length<count) candidates=pool.filter(q=>!rec.has(q.id));
  if(candidates.length<count) candidates=pool;
  candidates.sort((a,b)=>(scoreAdaptive(b)+(categoryNeed[b.category]||0))-(scoreAdaptive(a)+(categoryNeed[a.category]||0)));
  const chosen=[], catCounts={}, usedFamilies=new Set();
  const softCap=Math.max(2,Math.ceil(count/Math.max(4,categories.length))+1);
  for(const q of candidates){
    if(chosen.length>=count) break;
    if(usedFamilies.has(familyKey(q))) continue;
    if((catCounts[q.category]||0)>=softCap) continue;
    chosen.push(q); usedFamilies.add(familyKey(q)); catCounts[q.category]=(catCounts[q.category]||0)+1;
  }
  for(const q of candidates){
    if(chosen.length>=count) break;
    if(!chosen.includes(q)&&!usedFamilies.has(familyKey(q))){chosen.push(q);usedFamilies.add(familyKey(q));}
  }
  return chosen.slice(0,count);
}
function startAdaptive(){startSession(adaptiveQuestions(10),{mode:'adaptive',timed:false,timeLimit:0,adaptive:true})}
function startCategory(cat){startSession(pickQuestions(10,{category:cat,smart:true}),{mode:'topic',timed:false,timeLimit:0})}
function startFixed(n,timed=false,fast=false){startSession(pickQuestions(n,{smart:fast}),{mode:fast?'5 דקות':String(n),timed,timeLimit:fast?5*60:(timed?15*60:0),fast})}
function startTimedChallenge(){
  const qs=pickQuestions(Math.max(12,activePool().length),{smart:true});
  startSession(qs,{mode:'5 דקות',timed:true,timeLimit:5*60,fast:true,challenge:true});
}
function simulationQuestions(count=90){
  const pool=approvedPool(true).filter(q=>!recentIds(120).has(q.id));
  const fallback=approvedPool(true);
  const categoryPlan={logic:15,quantitative:20,series:20,shapes_spatial:15,analogies:10,sentence_completion:2,vocabulary:2,odd_one_out:2,nonword_context:2,reading_comprehension:2};
  const difficultyPlan={4:54,5:36};
  const chosen=[], usedFamilies=new Set(), usedIds=new Set(), diffCount={1:0,2:0,3:0,4:0,5:0};
  const take=(cat,n,source)=>{
    const candidates=shuffle(source.filter(q=>q.category===cat&&!usedIds.has(q.id)&&!usedFamilies.has(familyKey(q))));
    for(let k=0;k<n;k++){
      let best=null,bestPenalty=1e9;
      for(const q of candidates){
        if(usedIds.has(q.id)||usedFamilies.has(familyKey(q)))continue;
        const d=Number(q.difficulty_calibrated||q.difficulty_prior||3);
        const over=Math.max(0,(diffCount[d]||0)-(difficultyPlan[d]||0));
        const remaining=(difficultyPlan[d]||0)-(diffCount[d]||0);
        const penalty=over*100-(remaining>0?remaining*5:0)+Math.random();
        if(penalty<bestPenalty){best=q;bestPenalty=penalty;}
      }
      if(!best)break;
      chosen.push(best);usedIds.add(best.id);usedFamilies.add(familyKey(best));
      const d=Number(best.difficulty_calibrated||best.difficulty_prior||3);diffCount[d]=(diffCount[d]||0)+1;
    }
  };
  for(const [cat,n] of Object.entries(categoryPlan))take(cat,n,pool);
  for(const [cat,n] of Object.entries(categoryPlan)){
    const have=chosen.filter(q=>q.category===cat).length;
    if(have<n)take(cat,n-have,fallback);
  }
  for(const q of shuffle(fallback)){
    if(chosen.length>=count)break;
    if(!usedIds.has(q.id)&&!usedFamilies.has(familyKey(q))){chosen.push(q);usedIds.add(q.id);usedFamilies.add(familyKey(q));}
  }
  return shuffle(chosen).slice(0,count);
}
function showSimulationIntro(){
  const ready=approvedPool(true).filter(q=>[4,5].includes(Number(q.difficulty_calibrated||q.difficulty_prior))).length;
  document.querySelector('#view').innerHTML=`<div class="exam-intro">
    <div class="exam-intro-card card">
      <div class="exam-icon">📝</div>
      <div class="eyebrow">סימולציית מבחן מלא</div>
      <h1>כאן עובדים כמו במבחן</h1>
      <p class="lead">הסימולציה מיועדת לתרגול תנאי מבחן, ולא ללמידה תוך כדי.</p>
      <div class="exam-rules grid grid-3">
        <div class="rule"><b>90</b><span>שאלות</span></div>
        <div class="rule"><b>90:00</b><span>דקות</span></div>
        <div class="rule"><b>0</b><span>רמזים ומשוב</span></div>
      </div>
      <div class="exam-check">✅ התשובות נבדקות רק בסיום<br/>✅ אפשר לדלג ולחזור לשאלות<br/>✅ השעון ממשיך לרוץ גם כשחוזרים לשאלה קודמת</div>
      <div class="notice">במאגר כרגע ${ready} שאלות שאושרו למסלול הסימולציה. הסימולציה תיבנה מתוך מאגר זה תוך שמירה על גיוון בין תחומים ורמות קושי.</div>
      <div class="row exam-actions"><button class="btn btn-ghost" onclick="renderHome()">חזרה</button><button class="btn btn-primary" onclick="startSimulation()">🚀 להתחיל מבחן</button></div>
    </div>
  </div>`;
}
function startSimulation(){
  const qs=simulationQuestions(90);
  if(qs.length<90){alert('כרגע אין מספיק שאלות מאושרות ומגוונות לסימולציה מלאה.');return}
  startSession(qs,{mode:'simulation',kind:'simulation',timed:true,timeLimit:90*60,fast:false,simulation:true});
}
function startDaily(){const qs=dailyQuestions();if(!qs.length){alert('אין כרגע שאלות יומיות זמינות.');return}startSession(qs,{mode:'אתגר יומי',timed:false,timeLimit:0,daily:true})}
function startSession(qs,opt){
  if(!qs.length){alert('אין כרגע מספיק שאלות מאושרות במאגר.');return}
  state.currentSession={id:uid(),qs,idx:0,answers:[],start:Date.now(),questionTime:{},questionOpenedAt:Date.now(),hintUsed:false,simReview:false,kind:opt.kind||'practice',...opt};
  renderSession();
}
function sessionAnswered(q){return state.currentSession?.answers.find(a=>a.questionId===q.id)}
function renderSession(){
  const s=state.currentSession,q=s.qs[s.idx]; if(!q){finishSession();return}
  const answered=sessionAnswered(q); const pct=Math.round(((s.idx+(answered?1:0))/s.qs.length)*100); const remain=s.timed?Math.max(0,s.timeLimit-Math.floor((Date.now()-s.start)/1000)):null; const qElapsed=(s.questionTime[q.id]||0)+(!answered?Math.max(0,Math.floor((Date.now()-(s.questionOpenedAt||Date.now()))/1000)):0); const qClock=s.mode==='simulation'?(qElapsed<=60?`00:${String(Math.max(0,60-qElapsed)).padStart(2,'0')}`:`+${formatTime(qElapsed-60)}`):formatTime(qElapsed);
  const label=s.mode==='simulation'?'מצב מבחן':s.mode==='adaptive'?'אדפטיבי':s.mode;
  const palette=s.mode==='simulation'?`<div class="sim-palette">${s.qs.map((qq,i)=>{const aa=sessionAnswered(qq);return `<button class="sim-dot ${aa?'answered':''} ${i===s.idx?'current':''}" onclick="gotoQuestion(${i})" title="שאלה ${i+1}">${i+1}</button>`}).join('')}</div>`:'';
  const controls=s.mode==='simulation'?`<div class="sim-controls"><div class="sim-status">${s.answers.length} נענו · ${s.qs.length-s.answers.length} לא נענו</div><button class="btn btn-ghost" onclick="prevQuestion()" ${s.idx===0?'disabled':''}>← הקודמת</button>${!answered&&s.idx<s.qs.length-1?`<button class="btn btn-ghost" onclick="skipQuestion()">דלג</button>`:''}<button class="btn btn-primary" onclick="nextQuestion()">${s.idx===s.qs.length-1?'סיום סימולציה':'המשך'}</button></div>`:(answered?`<div class="row" style="justify-content:space-between;margin-top:14px"><button class="btn btn-ghost" onclick="prevQuestion()" ${s.idx===0?'disabled':''}>חזרה</button><button class="btn btn-primary" onclick="nextQuestion()">${s.idx===s.qs.length-1?'סיום':'המשך'}</button></div>`:'');
  document.querySelector('#view').innerHTML=`<div class="session"><div class="session-head"><div><div class="q-num">שאלה ${s.idx+1} מתוך ${s.qs.length}</div><div class="muted">${catLabels[q.category]||''} · רמה ${q.difficulty_calibrated||q.difficulty_prior||'-'}</div></div><div class="row"><button class="btn btn-danger btn-exit" onclick="exitSession()">יציאה</button><span class="pill">${label}</span>${s.timed?`<span class="pill" id="timer">כללי ${formatTime(remain)}</span>`:''}<span class="pill question-timer-pill ${s.mode==='simulation'&&qElapsed>60?'overtime':''}" id="questionTimer">${s.mode==='simulation'?'⏱️ שאלה '+qClock:'⏱️ '+qClock}</span></div></div><div class="progress"><div style="width:${pct}%"></div></div>${palette}<div class="card question-card"><div class="q-meta"><div class="difficulty">${(q.skills||[]).slice(0,3).join(' · ')}</div>${q.prerequisite_knowledge?.length?`<div class="tag">דורש ידע קודם</div>`:''}</div><div class="prompt">${esc(q.prompt)}</div>${renderVisual(q)}<div class="option-grid">${(q.options||[]).map((o,i)=>optionHtml(q,o,i,answered,s.mode==='simulation')).join('')}</div>${answered&&s.mode!=='simulation'?feedbackHtml(q,answered):''}${!answered&&q.hint&&s.mode!=='simulation'?`<div class="row" style="margin-top:14px"><button class="btn btn-ghost" onclick="showHint()">💡 רמז</button><span id="hintBox"></span></div>`:''}</div>${controls}</div>`;
  if(s.timed)startTimerTick();
}
function optionHtml(q,o,i,answered,sim){let cls='option';if(answered){if(o.id===q.correct_option_id)cls+=' correct';if(o.id===answered.chosenOptionId&&!answered.correct)cls+=' wrong';if(sim)cls+=' disabled'}return `<button class="${cls}" ${sim&&answered?'disabled':''} onclick="answer('${q.id}','${o.id}')"><span class="letter">${letter[i]||i+1}</span>${esc(o.text)}</button>`}
function answer(qid,optId){
  const s=state.currentSession,q=s.qs[s.idx]; if(!q||s.answers.some(a=>a.questionId===qid))return;
  commitCurrentQuestionTime(); const time=Math.max(1,Math.round(s.questionTime[qid]||1)); const correct=optId===q.correct_option_id;
  const a={questionId:qid,chosenOptionId:optId,correct,time,skills:q.skills||[],difficulty:q.difficulty_calibrated||q.difficulty_prior,category:q.category,subcategory:q.subcategory,semantic_family_id:familyKey(q),sessionId:s.id,kind:s.kind||'practice',timestamp:Date.now()};
  s.answers.push(a);s.perQuestionStart=Date.now();state.history.attempts.push(a);state.history.shown.push(qid);
  if(!correct&&!state.history.mistakes.some(m=>m.questionId===qid))state.history.mistakes.push({questionId:qid,skills:q.skills||[],category:q.category,subcategory:q.subcategory,createdAt:Date.now(),resolved:false});
  if(correct){const m=state.history.mistakes.find(m=>m.questionId===qid);if(m){m.resolved=true;m.resolvedAt=Date.now();}}
  saveStore();
  if(s.daily&&s.answers.length===s.qs.length)state.history.daily.completed=true;
  renderSession();
}
function showHint(){const q=state.currentSession.qs[state.currentSession.idx];const el=document.querySelector('#hintBox');if(el){el.innerHTML=`<span class="hint-text">${esc(q.hint||'נסו לזהות קודם את סוג החוקיות או היחס המבוקש.')}</span>`;state.currentSession.hintUsed=true;}}
function feedbackHtml(q,a){return `<div class="feedback ${a.correct?'good':'bad'}"><h3>${a.correct?'✅ נכון!':'❌ לא הפעם'}</h3><div class="explain">${esc(q.explanation||'')}</div>${q.reasoning_steps?.length?`<details style="margin-top:10px"><summary><b>איך לחשוב על זה</b></summary><ol class="steps">${q.reasoning_steps.map(x=>`<li>${esc(x)}</li>`).join('')}</ol></details>`:''}</div>`}
function commitCurrentQuestionTime(){const s=state.currentSession;if(!s)return;const q=s.qs[s.idx];if(!q||sessionAnswered(q))return;const delta=Math.max(0,Math.floor((Date.now()-(s.questionOpenedAt||Date.now()))/1000));s.questionTime[q.id]=(s.questionTime[q.id]||0)+delta;s.questionOpenedAt=Date.now();}
function nextQuestion(){const s=state.currentSession;if(!s)return;if(s.idx>=s.qs.length-1){finishSession();return}commitCurrentQuestionTime();s.idx++;s.questionOpenedAt=Date.now();saveResumeSession();renderSession()}
function skipQuestion(){const s=state.currentSession;if(!s||s.mode!=='simulation')return;commitCurrentQuestionTime();if(s.idx<s.qs.length-1){s.idx++;s.questionOpenedAt=Date.now();saveResumeSession();renderSession()}else finishSession()}
function prevQuestion(){const s=state.currentSession;if(!s||s.idx<=0)return;commitCurrentQuestionTime();s.idx--;s.questionOpenedAt=Date.now();saveResumeSession();renderSession()}
function gotoQuestion(i){const s=state.currentSession;if(!s||s.mode!=='simulation')return;if(i>=0&&i<s.qs.length){commitCurrentQuestionTime();s.idx=i;s.questionOpenedAt=Date.now();saveResumeSession();renderSession()}}
function saveResumeSession(){const p=activeProfile();if(!p||!state.currentSession)return;p.resumeSession={...state.currentSession};saveStore()}
function clearResumeSession(){const p=activeProfile();if(p){p.resumeSession=null;saveStore()}}
function prevQuestion(){const s=state.currentSession;if(s.idx>0){s.idx--;s.perQuestionStart=Date.now();renderSession()}}
function exitSession(){
  const s=state.currentSession;if(!s)return;
  commitCurrentQuestionTime();
  saveResumeSession();
  const what=s.mode==='simulation'?'הסימולציה':'התרגול';
  if(!confirm(`לצאת מ${what}? התשובות שכבר נענו יישמרו, אבל ${what} יסומן כלא הושלם.`))return;
  state.history.sessions.push({id:s.id,userId:state.activeProfileId,mode:s.mode,kind:s.kind||'practice',status:'abandoned',questionCount:s.qs.length,answered:s.answers.length,correct:s.answers.filter(a=>a.correct).length,score:null,duration:Math.round((Date.now()-s.start)/1000),timestamp:Date.now()});
  saveStore();state.currentSession=null;clearTimeout(window._timer);renderHome();
}
function renderProfilePicker(){
  updateTopUser();
  const cards=state.profiles.map(p=>`<button class="card profile-card" onclick="selectProfile('${p.id}')"><div class="profile-avatar">${esc((p.display_name||'?').trim().charAt(0)||'?')}</div><div class="action-title">${esc(p.display_name)} ${p.pinHash?'🔒':''}</div><div class="action-sub">${p.username?`@${esc(p.username)} · `:''}${p.history?.sessions?.filter(x=>x.status==='completed').length||0} פעילויות שהושלמו${p.resumeSession?' · ▶ יש פעילות להמשך':''}</div></button>`).join('');
  document.querySelector('#view').innerHTML=`<div class="profile-picker"><div class="section-title"><h2>מי מתרגל/ת עכשיו?</h2></div><div class="grid grid-3">${cards}<button class="card profile-card add-profile" onclick="addProfile()"><div class="profile-avatar">＋</div><div class="action-title">הוספת משתמש</div><div class="action-sub">התקדמות נפרדת לכל ילד/ה</div></button></div></div>`;
}
async function selectProfile(id){if(state.currentSession)return;const p=state.profiles.find(x=>x.id===id);if(!p)return;if(p.pinHash){const pin=prompt(`קוד כניסה עבור ${p.display_name}`);if(pin===null)return;const hash=await hashText(pin);if(hash!==p.pinHash){alert('קוד כניסה שגוי.');return}}state.activeProfileId=id;syncActiveProfile();saveStore();ensureDaily();renderHome();} 
function addProfile(){document.querySelector('#view').innerHTML=`<div class="profile-picker"><div class="section-title"><h2>הוספת משתמש</h2><button class="btn btn-ghost" onclick="renderProfilePicker()">חזרה</button></div><div class="card auth-card"><label>שם הילד/ה<input id="newName" autocomplete="name" placeholder="למשל: יואב"></label><label>שם משתמש<input id="newUsername" autocomplete="username" placeholder="למשל: yoav"></label><label>קוד כניסה (4–8 ספרות)<input id="newPin" inputmode="numeric" pattern="[0-9]{4,8}" maxlength="8" placeholder="****"></label><div class="notice">הקוד נשמר במכשיר בצורה מוצפנת (hash). זהו מנגנון מקומי; לסנכרון בין מכשירים נצטרך חשבון ענן.</div><div class="row"><button class="btn btn-primary" onclick="createProfileFromForm()">יצירת משתמש</button></div></div></div>`}
async function createProfileFromForm(){const name=document.querySelector('#newName')?.value.trim();const username=document.querySelector('#newUsername')?.value.trim();const pin=document.querySelector('#newPin')?.value.trim();if(!name||!username||!/^[0-9]{4,8}$/.test(pin||'')){alert('יש למלא שם, שם משתמש וקוד של 4–8 ספרות.');return}if(state.profiles.some(p=>(p.username||'').toLowerCase()===username.toLowerCase())){alert('שם המשתמש כבר קיים.');return}const p={id:uid(),display_name:name,username,pinHash:await hashText(pin),createdAt:Date.now(),history:emptyHistory(),resumeSession:null};state.profiles.push(p);state.activeProfileId=p.id;syncActiveProfile();saveStore();ensureDaily();renderHome()}
function switchProfile(){if(state.currentSession){alert('יש לצאת מהתרגול לפני החלפת משתמש.');return}renderProfilePicker()}
function finishSession(){
  const s=state.currentSession;if(!s)return;
  commitCurrentQuestionTime();
  const completed=s.answers.length,correct=s.answers.filter(a=>a.correct).length;
  state.history.sessions.push({id:s.id,userId:state.activeProfileId,mode:s.mode,kind:s.kind||'practice',status:'completed',questionCount:s.qs.length,answered:completed,correct,score:s.qs.length?Math.round(correct/s.qs.length*100):0,duration:Math.round((Date.now()-s.start)/1000),timestamp:Date.now()});
  if(s.daily&&completed===s.qs.length)state.history.daily.completed=true;
  clearResumeSession(); saveStore();renderResults(s);state.currentSession=null;clearTimeout(window._timer);
}
function renderResults(s){
  const correct=s.answers.filter(a=>a.correct).length,answered=s.answers.length,rate=s.qs.length?Math.round(correct/s.qs.length*100):0;
  const by={};s.qs.forEach(q=>{by[q.category] ||= {n:0,c:0};by[q.category].n++;if(s.answers.find(x=>x.questionId===q.id)?.correct)by[q.category].c++});
  const mins=Math.floor((Date.now()-s.start)/60000), secs=Math.floor((Date.now()-s.start)/1000)%60;
  document.querySelector('#view').innerHTML=`<div class="results-hero card"><div class="eyebrow">${s.mode==='simulation'?'📝 סימולציית מבחן מלאה':s.mode+' הסתיים'}</div><div class="score-ring">${rate}%</div><div class="muted">${correct} נכונות מתוך ${answered} שאלות שנענו · ${s.mode==='simulation'?`${s.qs.length-answered} שאלות לא נענו · `:''}זמן ${mins}:${String(secs).padStart(2,'0')}</div>${s.mode==='simulation'?`<div class="exam-result-note">הציון הוא תוצאה של הסימולציה בלבד ואינו ציון רשמי של משרד החינוך.</div>`:''}<div class="space"></div><div class="row" style="justify-content:center"><button class="btn btn-primary" onclick="renderHome()">חזרה לבית</button><button class="btn btn-ghost" onclick="renderMistakes()">תרגול טעויות</button><button class="btn btn-ghost" onclick="startAdaptive()">אימון המשך</button><button class="btn btn-ghost" onclick="renderTimeStats()">⏱️ סטטיסטיקת זמנים</button></div></div><div class="section-title"><h2>פירוט לפי תחום</h2></div><div class="grid grid-3">${Object.entries(by).map(([k,v])=>`<div class="card"><div class="muted">${catLabels[k]||k}</div><div style="font-size:28px;font-weight:800">${v.n?Math.round(v.c/v.n*100):0}%</div><div class="barline"><div class="track"><div class="fill" style="width:${v.n?Math.round(v.c/v.n*100):0}%"></div></div></div></div>`).join('')}</div><div class="section-title"><h2>מה כדאי לתרגל עכשיו?</h2></div><div class="card">${weakestSkills(3).length?weakestSkills(3).map(x=>`<div class="skill-row"><b>${esc(skillLabel(x.sk))}</b><span class="pill">שליטה ${Math.round(x.mastery*100)}%</span></div>`).join(''):'<div class="muted">עוד כמה אימונים ונוכל לתת המלצה אישית מדויקת יותר.</div>'}</div>`;
}
function renderProgress(){
  const att=state.history.attempts; const cats=Object.keys(catLabels).map(k=>{const a=att.filter(x=>x.category===k);return [k,a.length?Math.round(a.filter(x=>x.correct).length/a.length*100):0,a.length]});
  const skills=statsBySkill(); const top=Object.entries(skills).sort((a,b)=>a[1].c/b[1].n-a[1].c/b[1].n).slice(0,6);
  const sims=state.history.sessions.filter(x=>x.kind==='simulation'&&x.status==='completed');
  const simHtml=sims.length?sims.slice().reverse().slice(0,6).map((x,i)=>`<div class="card"><div class="muted">סימולציה ${sims.length-i}</div><div style="font-size:30px;font-weight:800">${x.score}%</div><div class="muted">${x.correct}/${x.questionCount} · ${Math.round(x.duration/60)} דקות</div></div>`).join(''):'<div class="notice">עדיין לא הושלמה סימולציית מבחן מלאה.</div>';
  document.querySelector('#view').innerHTML=`<div class="section-title"><h2>ההתקדמות שלי</h2><button class="btn btn-ghost" onclick="renderHome()">חזרה</button></div><div class="section-title"><h2>סימולציות מבחן</h2></div><div class="grid grid-3">${simHtml}</div><div class="section-title"><h2>תרגול לפי תחום</h2></div><div class="grid grid-3">${cats.map(([k,r,n])=>`<div class="card"><div class="muted">${catLabels[k]}</div><div style="font-size:30px;font-weight:800">${r}%</div><div class="muted">${n} ניסיונות</div><div class="barline"><div class="track"><div class="fill" style="width:${r}%"></div></div></div></div>`).join('')}</div><div class="section-title"><h2>מיומנויות שכדאי לחזק</h2></div><div class="card">${top.length?top.map(([sk,s])=>`<div class="skill-row"><div><b>${esc(skillLabel(sk))}</b><div class="muted">${s.n} ניסיונות</div></div><span class="pill">${Math.round(s.c/s.n*100)}%</span></div>`).join(''):'<div class="muted">עדיין אין מספיק נתונים.</div>'}</div><div class="section-title"><h2>זמן פתרון</h2><button class="btn btn-ghost" onclick="renderTimeStats()">פירוט לפי סוג שאלה</button></div><div class="card"><div class="muted">זמן ממוצע לכל תשובה</div><div class="stat-big" style="font-size:34px">${att.length?formatTime(Math.round(att.reduce((a,x)=>a+(x.time||0),0)/att.length)):'00:00'}</div><div class="muted">כולל תרגול וסימולציות</div></div><div class="section-title"><h2>רצף</h2></div><div class="card"><div class="stat-big" style="font-size:42px">${calcStreak()} 🔥</div><div class="muted">תשובות נכונות רצופות</div></div>`;
}
function renderTimeStats(){
  const attempts=state.history.attempts.filter(a=>a.time>0);
  const groups={};
  for(const a of attempts){const key=a.subcategory||a.category||'אחר';const x=groups[key]||(groups[key]={n:0,total:0,correct:0,wrongTime:0,wrongN:0});x.n++;x.total+=a.time||0;if(a.correct)x.correct++;else{x.wrongTime+=a.time||0;x.wrongN++}}
  const rows=Object.entries(groups).sort((a,b)=>b[1].n-a[1].n).map(([k,x])=>{const avg=Math.round(x.total/x.n);const ca=x.correct?Math.round((x.total-x.wrongTime)/x.correct):0;const wa=x.wrongN?Math.round(x.wrongTime/x.wrongN):0;return `<tr><td>${esc(catLabels[k]||k)}</td><td>${x.n}</td><td>${formatTime(avg)}</td><td>${formatTime(ca)}</td><td>${x.wrongN?formatTime(wa):'—'}</td><td>${Math.round(x.correct/x.n*100)}%</td></tr>`}).join('');
  document.querySelector('#view').innerHTML=`<div class="section-title"><h2>⏱️ סטטיסטיקת זמן פתרון</h2><button class="btn btn-ghost" onclick="renderProgress()">חזרה להתקדמות</button></div><div class="notice">הזמן נמדד לכל שאלה בנפרד ונשמר לפי המשתמש. בסימולציה היעד הוא עד 60 שניות לשאלה; בתרגול אין מגבלת זמן.</div><div class="card"><table class="table"><thead><tr><th>סוג/תחום</th><th>ניסיונות</th><th>ממוצע</th><th>נכון</th><th>שגוי</th><th>דיוק</th></tr></thead><tbody>${rows||`<tr><td colspan="6" class="muted">עדיין אין מספיק נתוני זמן.</td></tr>`}</tbody></table></div>`;
}
function skillLabel(sk){return String(sk||'').replaceAll('_',' ')}
function renderMistakes(){
  const rows=state.history.mistakes.filter(m=>!m.resolved).slice().reverse().map(m=>{const q=state.questions.find(x=>x.id===m.questionId);return q?`<tr><td>${esc(q.prompt.slice(0,110))}${q.prompt.length>110?'…':''}</td><td>${catLabels[q.category]}</td><td>${q.difficulty_calibrated||q.difficulty_prior}</td><td><button class="btn btn-ghost" onclick="practiceSkill('${q.category}','${q.subcategory||''}')">תרגל מיומנות</button></td></tr>`:''}).join('');
  document.querySelector('#view').innerHTML=`<div class="section-title"><h2>הטעויות שלי</h2><button class="btn btn-ghost" onclick="renderHome()">חזרה</button></div>${rows?`<div class="card"><table class="table"><thead><tr><th>שאלה</th><th>תחום</th><th>רמה</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`:`<div class="notice">אין כאן טעויות עדיין.</div>`}`;
}
function practiceSkill(cat,sub){const qs=pickQuestions(8,{category:cat,subcategory:sub,smart:true});startSession(qs,{mode:'חיזוק skill',timed:false,timeLimit:0})}
function renderParent(){
  const att=state.history.attempts,correct=att.filter(x=>x.correct).length,rate=att.length?Math.round(correct/att.length*100):0;
  const days=new Set(state.history.sessions.map(s=>new Date(s.timestamp).toISOString().slice(0,10))).size;
  document.querySelector('#view').innerHTML=`<div class="section-title"><h2>לוח הורה</h2><button class="btn btn-ghost" onclick="renderHome()">חזרה</button></div><div class="notice">הנתונים נשמרים כרגע במכשיר בלבד. אין כאן תחזית קבלה או ציון רשמי.</div><div class="space"></div><div class="grid grid-4">${miniMetric('דיוק כולל',rate+'%')}${miniMetric('שאלות',att.length)}${miniMetric('אימונים',state.history.sessions.length)}${miniMetric('ימי אימון',days)}</div><div class="section-title"><h2>מה כדאי לחזק?</h2></div><div class="card">${weakAreaHtml()}</div><div class="section-title"><h2>מיומנויות חלשות</h2></div><div class="card">${weakestSkills(5).map(x=>`<div class="skill-row"><span>${esc(skillLabel(x.sk))}</span><span class="pill">${Math.round(x.mastery*100)}%</span></div>`).join('')||'<span class="muted">אין עדיין מספיק נתונים.</span>'}</div>`;
}
function weakAreaHtml(){
  const out=Object.keys(catLabels).map(k=>{const a=state.history.attempts.filter(x=>x.category===k);return {k,n:a.length,r:a.length?a.filter(x=>x.correct).length/a.length:1}}).sort((a,b)=>a.r-b.r);
  return out.map(z=>`<div class="row" style="justify-content:space-between;padding:10px 0"><span>${catIcons[z.k]} ${catLabels[z.k]}</span><span class="pill">${z.n?Math.round(z.r*100):0}%</span></div>`).join('');
}
function countByDifficulty(pool){const out={1:0,2:0,3:0,4:0,5:0};for(const q of pool){const d=Number(q.difficulty_calibrated||q.difficulty_prior||0);if(out[d]!=null)out[d]++;}return out;}
function familyDiversity(pool){return new Set(pool.map(familyKey)).size;}
function renderAdmin(){
  const qs=state.questions; const active=qs.filter(questionIsPublished); const byCat=Object.keys(catLabels).map(k=>[k,active.filter(q=>q.category===k).length]);
  const pub=active.length, sim=approvedPool(true).length, pending=qs.filter(q=>q.validation?.semantic_review?.status==='pending').length;
  const diff=countByDifficulty(active);
  document.querySelector('#view').innerHTML=`<div class="section-title"><h2>Admin · מאגר תוכן</h2><button class="btn btn-ghost" onclick="renderHome()">חזרה</button></div><div class="notice">זהו מסך בקרה. שאלות שלא פורסמו נשארות זמינות לבדיקות פיתוח בלבד.</div><div class="grid grid-4">${miniMetric('סה״כ במאגר',qs.length)}${miniMetric('פעילות',pub)}${miniMetric('מוכנות לסימולציה',sim)}${miniMetric('Semantic Review',pending)}</div><div class="section-title"><h2>כיסוי הפעילות</h2></div><div class="grid grid-4">${byCat.map(([k,n])=>miniMetric(catLabels[k],n)).join('')}</div><div class="section-title"><h2>פיזור רמות קושי</h2></div><div class="grid grid-5">${[1,2,3,4,5].map(d=>miniMetric('רמה '+d,diff[d])).join('')}</div><div class="section-title"><h2>גיוון</h2></div><div class="card"><div class="row" style="justify-content:space-between"><span>Semantic families פעילות</span><span class="pill">${familyDiversity(active)}</span></div></div><div class="space"></div><div class="card"><table class="table"><thead><tr><th>ID</th><th>תחום</th><th>תת-תחום</th><th>רמה</th><th>סטטוס</th></tr></thead><tbody>${qs.slice(0,240).map(q=>`<tr><td>${q.id}</td><td>${catLabels[q.category]||q.category}</td><td>${esc(q.subcategory||'-')}</td><td>${q.difficulty_calibrated||q.difficulty_prior||'-'}</td><td>${questionIsPublished(q)?'<span class="pill">פעילה</span>':'<span class="tag">seed-only</span>'}</td></tr>`).join('')}</tbody></table></div>`;
}
function renderSettings(){updateTopUser();const p=activeProfile();document.querySelector('#view').innerHTML=`<div class="section-title"><h2>הגדרות</h2><button class="btn btn-ghost" onclick="renderHome()">חזרה</button></div><div class="card"><h3>פרופיל נוכחי</h3><p class="muted">לכל משתמש נשמרים התרגולים, הסימולציות והטעויות בנפרד במכשיר.</p><div class="row"><input id="nameInput" value="${esc(state.profile?.display_name||'')}" placeholder="שם הילד/ה" style="flex:1;padding:12px 14px;border:1px solid var(--line);border-radius:12px;font:inherit"><button class="btn btn-primary" onclick="saveProfile()">שמור</button><button class="btn btn-ghost" onclick="switchProfile()">החלפת משתמש</button></div></div><div class="space"></div><div class="card"><h3>כניסה למשתמש</h3><p class="muted">שם משתמש: <b>${esc(p?.username||'לא הוגדר')}</b></p><div class="row"><input id="pinInput" inputmode="numeric" pattern="[0-9]{4,8}" maxlength="8" placeholder="קוד חדש 4–8 ספרות" style="flex:1;padding:12px 14px;border:1px solid var(--line);border-radius:12px;font:inherit"><button class="btn btn-primary" onclick="setPin()">הגדר/החלף קוד</button></div><div class="muted" style="margin-top:8px">הקוד נשמר כ־hash מקומי. זה לא חשבון ענן.</div></div><div class="space"></div><div class="card"><h3>איפוס התקדמות של ${esc(state.profile?.display_name||'המשתמש')}</h3><p class="muted">מוחק רק את ההיסטוריה של המשתמש הנוכחי.</p><button class="btn btn-danger" onclick="resetProgress()">איפוס</button></div>`}
function saveProfile(){const p=activeProfile();if(!p)return;const name=document.querySelector('#nameInput').value.trim()||'אלוף/ת';p.display_name=name;state.profile={display_name:name};saveStore();renderHome()}
async function setPin(){const p=activeProfile();const pin=document.querySelector('#pinInput')?.value.trim();if(!p||!/^[0-9]{4,8}$/.test(pin||'')){alert('יש להזין קוד בן 4–8 ספרות.');return}p.pinHash=await hashText(pin);syncActiveProfile();saveStore();alert('קוד הכניסה עודכן.');renderSettings()}
function resetProgress(){if(confirm('למחוק את כל ההתקדמות של המשתמש הנוכחי?')){state.history=emptyHistory();const p=activeProfile();if(p)p.history=state.history;saveStore();ensureDaily();renderSettings()}}
function svgArrow(deg=0,reflected=false){
  const sx=reflected?-1:1;
  return `<svg viewBox="0 0 80 80" width="70" height="70" aria-hidden="true"><g transform="translate(40 40) rotate(${Number(deg)||0}) scale(${sx} 1) translate(-40 -40)"><path d="M16 40 H58" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><path d="M48 25 L64 40 L48 55" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/></g></svg>`;
}
function svgPolygon(n=5,filled=[]){
  const pts=[]; for(let i=0;i<n;i++){const a=-Math.PI/2+i*2*Math.PI/n;pts.push([40+28*Math.cos(a),40+28*Math.sin(a)])}
  return `<svg viewBox="0 0 80 80" width="72" height="72"><polygon points="${pts.map(p=>p.join(',')).join(' ')}" fill="none" stroke="currentColor" stroke-width="2"/>${pts.map((p,i)=>`<circle cx="${p[0]}" cy="${p[1]}" r="5" fill="${filled.includes(i)||filled.includes(i+1)?'currentColor':'white'}" stroke="currentColor"/>`).join('')}</svg>`;
}
function renderVisual(q){
  const s=q.visual_schema;if(!s)return'';
  try{
    if(s.type==='superposition_matrix'||s.type==='superposition_pair'){
      const cols=s.columns||[]; return `<div class="visual"><div class="visual-title">מטריצת חפיפה</div><div class="visual-columns">${cols.map(col=>`<div class="visual-column"><div class="quad">${(col.top1||s.new_pair?.shape1||[]).map(v=>`<div class="${v?'on':''}"></div>`).join('')}</div><div class="op">+</div><div class="quad">${(col.top2||s.new_pair?.shape2||[]).map(v=>`<div class="${v?'on':''}"></div>`).join('')}</div><div class="op">→</div><div class="quad">${(col.bottom||[null,null,null,null]).map(v=>`<div class="${v===null?'question-cell':v?'on':''}">${v===null?'?':''}</div>`).join('')}</div></div>`).join('')}</div><div class="visual-caption">מצאו את החוק הקבוע בין הצורות</div></div>`;
    }
    if(s.type==='matrix3x3'||s.type==='hidden_dual_rule_matrix'||s.type==='matrix3x3_fill'){
      const cells=Array.isArray(s.cells)?s.cells.flat():Object.keys(s.cells||{}).sort((a,b)=>{const [ra,ca]=a.split(',').map(Number),[rb,cb]=b.split(',').map(Number);return ra-rb||ca-cb}).map(k=>s.cells[k]);
      return `<div class="visual"><div class="matrix">${cells.slice(0,9).map(c=>{if(c===null)return '<div class="matrix-cell"><span class="question-mark">?</span></div>';const fill=c.fill==='solid';return `<div class="matrix-cell"><div class="shape-count">${c.count??''}</div><div class="square-fill ${fill?'solid':'empty'}"></div></div>`}).join('')}</div></div>`;
    }
    if(s.type==='matrix3x3_rotation'){
      const cells=(s.cells_degrees||[]).flat();return `<div class="visual"><div class="matrix">${cells.map(c=>`<div class="matrix-cell">${c===null?'<span class="question-mark">?</span>':svgArrow(c)}</div>`).join('')}</div></div>`;
    }
    if(s.type==='linear_sequence_degrees'||s.type==='cyclic_sequence'){
      const vals=s.cells_degrees||s.degrees||s.sequence||[];return `<div class="visual"><div class="visual-seq">${vals.map(v=>`<div class="glyph-card">${v===null?'?':svgArrow(typeof v==='object'?v.rotation:v,typeof v==='object'&&v.reflected)}</div>`).join('')}</div></div>`;
    }
    if(s.type==='combined_transform_sequence'){
      const cells=s.cells||[];return `<div class="visual"><div class="visual-seq">${cells.map(c=>`<div class="glyph-card ${c===null?'missing':''}">${c===null?'?':svgArrow(c.rotation,c.reflected)}</div>`).join('')}</div></div>`;
    }
    if(s.type==='element_addition_polygon'){
      const filled=s.vertices_filled_after_step4||[];return `<div class="visual"><div class="glyph-card">${svgPolygon(s.polygon_sides||5,filled)}</div><div class="visual-caption">איזה קודקוד/אלמנט יתווסף בשלב הבא?</div></div>`;
    }
    if(s.type==='cube_rotation'||s.type==='cube_rotation_multi'){
      const multi=s.initial_marks||{};return `<div class="visual"><div class="cube-net"><div></div><div class="cube-face top">${multi.stripe?'▤':'▲'}</div><div></div><div class="cube-face front">${multi.dot?'●':'◆'}</div><div class="cube-face side">◀</div><div class="cube-face right">▶</div></div><div class="visual-caption">סיבוב ${s.rotation_degrees||90}° · עקבו אחר הפאות</div></div>`;
    }
    if(s.type==='paper_fold')return `<div class="visual"><div class="paper"><span class="fold-v"></span><span class="fold-h"></span><span class="punch"></span></div><div class="visual-caption">קיפול וניקוב — דמיינו את פתיחת הדף</div></div>`;
    if(s.type==='reflection_matrix'||s.type==='single_reflection')return `<div class="visual"><div class="reflect-demo"><span class="tri"></span><span class="mirror"></span><span style="transform:scaleX(-1)"><span class="tri"></span></span></div><div class="visual-caption">שיקוף ביחס לציר</div></div>`;
    if(s.type==='position_matrix')return `<div class="visual"><div class="visual-seq">${(s.cells_position||[1,2,3,4,null]).flat().map(v=>`<div class="glyph-card ${v===null?'missing':''}">${v===null?'?':v}</div>`).join('')}</div></div>`;
    if(s.type==='net_diagram')return `<div class="visual"><div class="cube-net"><div class="cube-face top">1</div><div class="cube-face front">2</div><div class="cube-face side">3</div><div class="cube-face right">4</div></div><div class="visual-caption">פריסה — דמיינו את הקיפול לגוף תלת־ממדי</div></div>`;
    if(s.type==='cross_section')return `<div class="visual"><div class="svg-stage"><svg viewBox="0 0 220 150" width="300"><path d="M55 35 L145 35 L175 65 L85 65 Z M55 35 V115 L85 140 V65 M85 140 H175 V65 M145 35 V115 L175 140 M55 75 L145 75 L175 100 L85 100 Z" fill="none" stroke="currentColor" stroke-width="2"/><path d="M55 75 L145 75 L175 100 L85 100 Z" fill="rgba(0,0,0,.08)" stroke="currentColor" stroke-dasharray="5 4"/></svg></div><div class="visual-caption">חתך במישור המסומן</div></div>`;
    return `<div class="visual"><span class="pill">שאלה חזותית</span></div>`;
  }catch(e){return `<div class="visual"><span class="muted">תצוגה חזותית</span></div>`}
}
function startTimerTick(){clearTimeout(window._timer);window._timer=setTimeout(()=>{const s=state.currentSession;if(!s)return;const elapsed=Math.floor((Date.now()-(s.questionOpenedAt||Date.now()))/1000)+(s.questionTime[s.qs[s.idx]?.id]||0);const qel=document.querySelector('#questionTimer');if(qel){if(s.mode==='simulation'){qel.textContent=elapsed<=60?`⏱️ שאלה 00:${String(Math.max(0,60-elapsed)).padStart(2,'0')}`:`⏱️ שאלה +${formatTime(elapsed-60)}`;qel.classList.toggle('overtime',elapsed>60)}else qel.textContent=`⏱️ ${formatTime(elapsed)}`;}if(s.timed){const remain=s.timeLimit-Math.floor((Date.now()-s.start)/1000);if(remain<=0){finishSession();return}const el=document.querySelector('#timer');if(el)el.textContent=`כללי ${formatTime(remain)}`}startTimerTick()},500)}
function formatTime(sec){const m=Math.floor(sec/60),s=sec%60;return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`}
function esc(x=''){return String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function boot(){
  loadStore();
  try{const r=await fetch('data/questions.json');const d=await r.json();state.questions=d.questions||[];renderProfilePicker();if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js').catch(()=>{});}
  catch(e){document.querySelector('#view').innerHTML='<div class="card"><h2>לא הצלחתי לטעון את המאגר</h2><p class="muted">בדקו שהאפליקציה רצה דרך שרת מקומי ולא בפתיחה ישירה של הקובץ.</p></div>';}
}
document.querySelector('#parentBtn').onclick=renderParent;document.querySelector('#settingsBtn').onclick=renderSettings;
window.renderHome=renderHome; window.createProfileFromForm=createProfileFromForm; window.resumeSession=resumeSession; window.renderTimeStats=renderTimeStats; window.setPin=setPin; window.showSimulationIntro=showSimulationIntro;window.renderProfilePicker=renderProfilePicker;window.selectProfile=selectProfile;window.addProfile=addProfile;window.switchProfile=switchProfile;window.exitSession=exitSession;window.startQuick=startQuick;window.startAdaptive=startAdaptive;window.showPracticePicker=showPracticePicker;window.startFixed=startFixed;window.startSimulation=startSimulation;window.startTimedChallenge=startTimedChallenge;window.startDaily=startDaily;window.startCategory=startCategory;window.answer=answer;window.nextQuestion=nextQuestion;window.prevQuestion=prevQuestion;window.renderProgress=renderProgress;window.renderMistakes=renderMistakes;window.practiceSkill=practiceSkill;window.renderParent=renderParent;window.renderAdmin=renderAdmin;window.renderSettings=renderSettings;window.saveProfile=saveProfile;window.resetProgress=resetProgress;window.showHint=showHint;
boot();
if(location.hash==='#admin')setTimeout(renderAdmin,200);
