import {$, $$, api, escape, modal, toast, showInfo, pageHeader} from './ui.js';
import {practice} from './practice.js';

let state, routeVersion=0;
let topics=[], collections=[];
const topicLabel=id=>[...topics,...collections].find(t=>t[0]===id)?.[1]||(id==='custom'?'Unclassified':id);
const labels={home:'My learning',flashcards:'Flashcards',drawing:'Character drawing',phrases:'Phrases & grammar',library:'Word library',mastered:'Mastered bin',settings:'Settings'};

async function refresh(){state=await api('state');topics=state.topics;collections=state.collections;$('#mastered-count').textContent=state.stats.mastered;}
async function route(){
  const revision=++routeVersion;
  const page=location.hash.slice(1)||'home';
  $('#main').dataset.route=page;
  $$('.sidebar nav a').forEach(a=>{const active=a.dataset.route===page;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  $('#breadcrumb').textContent=labels[page]||labels.home;
  try{
    await refresh();
    if(revision!==routeVersion)return;
    if(['flashcards','drawing','phrases'].includes(page))return await practice(page,state,refresh,addExample);
    if(page==='library'||page==='mastered')return library(page);
    if(page==='settings')return settings();
    home();
  }catch(error){$('#main').innerHTML=`<div class="empty-state"><h1>Let’s reconnect.</h1><p>${escape(error.message)}</p><button class="primary retry-load">Try again</button></div>`;$('.retry-load').onclick=route;}
}

function home(){
  const words=state.items.filter(i=>i.kind==='word'&&i.enrolled);
  const greeting=new Intl.DateTimeFormat('en',{weekday:'long',month:'long',day:'numeric',timeZone:state.settings.timezone}).format(new Date());
  $('#main').innerHTML=`<div class="home-date"><span class="status-dot"></span> ${escape(greeting)} <span>YOUR OWN PACE. YOUR OWN PATH.</span></div>
    <section class="hero"><div><p class="eyebrow">你好, LET’S LEARN SOMETHING.</p><h1>Small steps.<br><em>Real understanding.</em></h1><p>Learn the Mandarin that matters to you.<br>One word, one character, one connection at a time.</p><a href="#flashcards" class="primary">Continue learning <span>↗</span></a></div><div class="hero-art" aria-hidden="true"><span class="orbit orbit-one"></span><span class="orbit orbit-two"></span><span class="art-note">every word has a story</span><div class="art-tile"><small>hǎo</small><span lang="zh-Hant">好</span><small>good · well</small></div><span class="art-spark">✳</span><span class="art-dot"></span></div></section>
    <section class="stats" aria-label="Your progress"><article><span class="stat-icon green">▤</span><div><strong>${words.length}</strong><p>Words in your world</p></div></article><article><span class="stat-icon purple">✧</span><div><strong>${state.stats.mastered}</strong><p>Words mastered</p></div></article><article><span class="stat-icon peach">↻</span><div><strong>${state.stats.reviews}</strong><p>Ready to revisit</p></div></article><article><span class="stat-icon yellow">✓</span><div><strong>${state.stats.attempts?Math.round(state.stats.correct/state.stats.attempts*100)+'%':'—'}</strong><p>${state.stats.attempts} attempts · all time</p></div></article></section>
    <div class="section-heading"><div><p class="eyebrow">THREE WAYS TO GROW</p><h2>Find your rhythm.</h2></div><span>Different skills. Shared understanding.</span></div>
    <section class="practice-cards"><a class="mode-card green-card" href="#flashcards"><div class="mode-card-top"><span class="card-icon">▣</span><span>01 / RECALL</span></div><div class="mini-flash" aria-hidden="true"><span>茶</span><small>chá</small></div><h3>Flashcards</h3><p>See it. Hear it. Know it.<br>Build a vocabulary that sticks.</p><div class="card-bottom"><span>3 difficulty levels</span><b>↗</b></div></a><a class="mode-card purple-card" href="#drawing"><div class="mode-card-top"><span class="card-icon">✎</span><span>02 / CREATE</span></div><div class="mini-drawing" aria-hidden="true"><span>木</span></div><h3>Character drawing</h3><p>Get to know every stroke.<br>Understand the parts behind the whole.</p><div class="card-bottom"><span>5 difficulty levels</span><b>↗</b></div></a><a class="mode-card peach-card" href="#phrases"><div class="mode-card-top"><span class="card-icon">☷</span><span>03 / CONNECT</span></div><div class="mini-phrase" aria-hidden="true"><span>我</span><span>喜歡</span><span>茶</span></div><h3>Phrases & grammar</h3><p>Turn your words into ideas.<br>Make meaningful connections.</p><div class="card-bottom"><span>3 difficulty levels</span><b>↗</b></div></a></section>
    <section class="interests-section"><div><span class="eyebrow">MAKE IT YOURS</span><h2>A world of things<br>you care about.</h2><p>Your interests help shape your vocabulary.<br>What would you like to talk about?</p><button class="text-button edit-interests">Personalise my topics ↗</button></div><div class="topic-cloud">${[...collections,...topics].map(([id,label,glyph,description])=>`<button title="${escape(description)}" class="topic-pill ${state.settings.interests.includes(id)?'selected':''}" data-topic="${id}"><span lang="zh-Hant">${glyph}</span>${label}${state.settings.interests.includes(id)?' ✓':' ＋'}</button>`).join('')}<button class="topic-pill add-custom">＋ Something else</button></div></section>
    <section class="daily-note"><span lang="zh-Hant">電 + 腦 = 電腦</span><div><span class="eyebrow">A CONNECTION TO REMEMBER</span><h3>Electricity + brain. Meet your computer.</h3><p>Characters carry meaning into the words they build. Explore the story behind yours.</p></div><button class="round-button computer-story" aria-label="Read about the word for computer">↗</button></section>`;
  $('.edit-interests').onclick=editInterests;$('.add-custom').onclick=editInterests;
  $$('.topic-pill[data-topic]').forEach(b=>b.onclick=async()=>{const interests=state.settings.interests.includes(b.dataset.topic)?state.settings.interests.filter(t=>t!==b.dataset.topic):[...state.settings.interests,b.dataset.topic];try{await api('settings',{interests,onboarded:true});await refresh();home();toast('Your topics are saved. New words are ready in your library.');}catch(e){toast(e.message);}});
  $('.computer-story').onclick=()=>showInfo(state.items.find(i=>i.id==='電腦'));
}

function editInterests(){
  const d=modal('What’s your world?',`<p>Choose subjects or the Everyday essentials beginner collection, describe your interests, or add a specific word.</p><form id="interests-form"><div class="topic-options">${[...collections,...topics].map(([id,label,glyph,description])=>`<label title="${escape(description)}"><input type="checkbox" name="topic" value="${id}" ${state.settings.interests.includes(id)?'checked':''}><span>${glyph}</span>${label}</label>`).join('')}</div><label for="interest-text">Tell us what you enjoy</label><textarea id="interest-text" rows="3" maxlength="2000" placeholder="Coffee, computers, train travel…">${escape(state.settings.interest_text)}</textarea><p class="fine-print">We match these interests against the local catalog. You can also search the full dictionary for specific vocabulary.</p><button class="primary full">Save my interests →</button></form>`);
  $('#interests-form',d).onsubmit=async e=>{e.preventDefault();try{await api('settings',{interests:$$('input:checked',d).map(i=>i.value),interest_text:$('#interest-text',d).value,onboarded:true});d.close();await route();}catch(error){toast(error.message);}};
}

function wordReadiness(item){
  if(item.kind!=='word')return '';
  const count=item.frequency_count||0;
  const frequency=`<p class="fine-print corpus-frequency">Taiwan text corpus: ${count?count.toLocaleString()+' occurrences':'not attested'}</p>`;
  return frequency;
}

function entryActions(item){
  if(item.can_delete)return `<div class="library-entry-actions"><label><input type="checkbox" class="select-entry" data-id="${escape(item.id)}" aria-label="Select ${escape(item.text)} for deletion"> Select</label><button class="text-button delete-entry" data-id="${escape(item.id)}" aria-label="Delete ${escape(item.text)}">Delete</button></div>`;
  if(item.kind==='word'&&item.progress.some(p=>['mastered','review'].includes(p.status)))return `<button class="text-button generate-related" data-id="${escape(item.id)}">Generate related entries ↗</button>`;
  return '';
}

function library(page){
  const bin=page==='mastered';
  const selected=new Set();
  $('#main').innerHTML=pageHeader(bin?'A LITTLE SPACE TO REST':'WORDS THAT MATTER',bin?'You’ve made these yours.':'Your growing word collection.',bin?`Mastered skills rest here. Each unchecked day has a ${state.settings.probability*100}% chance of bringing an item back.`:'Explore meanings, discover connections, and build your own vocabulary.','<button class="primary add-word">＋ Add an example</button>')+
    `<div class="library-toolbar"><div class="search-wrap"><span>⌕</span><input id="library-search" aria-label="Search your library" placeholder="Find a word, meaning, or pinyin…"></div><label for="status-filter">Status</label><select id="status-filter" aria-label="Filter by status">${bin?'<option value="mastered">Mastered & returning</option>':'<option value="enrolled">In my deck</option><option value="all">Discover all</option><option value="mastered">Mastered & returning</option><option value="unmastered">Not yet mastered</option>'}</select><label for="category-filter">Category</label><select id="category-filter" aria-label="Filter by category or collection"><option value="all">All categories</option>${topics.map(([id,label])=>`<option value="${id}">${label}</option>`).join('')}<option value="custom">Unclassified</option><optgroup label="Beginner collection">${collections.map(([id,label])=>`<option value="${id}">${label}</option>`).join('')}</optgroup></select></div>
    <div class="library-selection" ${bin?'hidden':''}><label><input type="checkbox" id="select-visible"> Select visible unmastered entries</label><button class="secondary delete-selected" disabled>Delete selected (0)</button></div><div id="library-results"></div>`;
  $('.add-word').onclick=addExample;
  $('.page-actions').insertAdjacentHTML('afterbegin','<button class="secondary generate-entries">Generate entries ✧</button>');
  $('.generate-entries').onclick=()=>generateEntries();
  async function removeEntries(ids){
    try{
      const result=await api('delete-entries',{ids});
      ids.forEach(id=>selected.delete(id));await refresh();
      if($('#main').dataset.route===page)render();
      toast(result.message,{label:'Undo',run:async()=>{await api('restore-entries',{ids:result.deleted});await route();}});
    }catch(error){toast(error.message);}
  }
  function updateSelection(){
    const button=$('.delete-selected');button.disabled=!selected.size;button.textContent=`Delete selected (${selected.size})`;
    const checkboxes=$$('.select-entry');
    $('#select-visible').checked=checkboxes.length>0&&checkboxes.every(c=>c.checked);
    $('#select-visible').disabled=!checkboxes.length;
  }
  function render(){
    const query=$('#library-search').value.toLowerCase();const status=$('#status-filter').value;const category=$('#category-filter').value;
    const items=state.items.filter(i=>i.kind==='word'&&(category==='all'||i.topic===category||i.collections?.includes(category))&&(status==='all'||status==='enrolled'&&i.enrolled||status==='mastered'&&i.progress.some(p=>['mastered','review'].includes(p.status))||status==='unmastered'&&i.enrolled&&!i.progress.some(p=>['mastered','review'].includes(p.status)))&&[i.text,i.pinyin,i.english].join(' ').toLowerCase().includes(query));
    $('#library-results').innerHTML=`<p class="result-count">${items.length} ${items.length===1?'entry':'entries'} · progress is tracked separately for each skill</p><div class="library-grid">${items.map(i=>`<article class="word-card"><div class="word-card-heading"><span class="pill">${escape(topicLabel(i.topic))}</span><button class="icon-button word-info" data-id="${escape(i.id)}" aria-label="Read about ${escape(i.text)}">ⓘ</button></div><div class="word-glyph" lang="zh-Hant">${escape(i.text)}</div><p class="pinyin">${escape(i.pinyin)}</p><h3>${escape(i.english)}</h3><div class="word-progress">${i.progress.map(p=>`<span class="${p.status==='mastered'?'mastered':p.status==='review'?'review':''}">${p.mode==='drawing'?'✎ Drawing':'▣ Cards'} <b>${p.status==='mastered'?'✓ Mastered':p.status==='review'?'↻ Review':(p.mode==='drawing'?['Components','Guided','Easy','Medium','Hard']:['Easy','Medium','Hard'])[p.level]}</b></span>`).join('')}</div>${wordReadiness(i)}${!i.enrolled?`<button class="secondary full enroll" data-id="${escape(i.id)}">Add to my deck ＋</button>`:''}${entryActions(i)}</article>`).join('')}</div>${items.length?'':'<div class="empty-state"><span class="empty-symbol">✧</span><h2>Room for your next discovery.</h2><p>Master the hardest level of a skill to see it here, or adjust your filters.</p></div>'}`;
    $$('.delete-entry').forEach(b=>b.onclick=()=>removeEntries([b.dataset.id]));
    $$('.select-entry').forEach(box=>{box.checked=selected.has(box.dataset.id);box.onchange=()=>{if(box.checked){if(selected.size>=100){box.checked=false;toast('Select up to 100 entries at a time.');}else selected.add(box.dataset.id);}else selected.delete(box.dataset.id);updateSelection();};});
    $$('.generate-related').forEach(b=>b.onclick=()=>generateEntries(b.dataset.id));
    $$('.word-info').forEach(b=>b.onclick=()=>showInfo(state.items.find(i=>i.id===b.dataset.id),{generate:state.services.llm}));
    $$('.enroll').forEach(b=>b.onclick=async()=>{try{const result=await api('add',{source:'catalog',id:b.dataset.id});await refresh();render();toast(result.message);}catch(e){toast(e.message);}});
    updateSelection();
  }
  $('.delete-selected').onclick=()=>removeEntries([...selected]);
  $('#select-visible').onchange=event=>{
    const boxes=$$('.select-entry').slice(0,100);
    boxes.forEach(box=>{box.checked=event.target.checked&&(selected.has(box.dataset.id)||selected.size<100);if(box.checked)selected.add(box.dataset.id);else selected.delete(box.dataset.id);});
    updateSelection();
  };
  $('#library-search').oninput=render;$('#status-filter').onchange=render;$('#category-filter').onchange=render;render();
}

async function generateEntries(seedId=null){
  try{await refresh();}catch(error){toast(error.message);return;}
  const mastered=state.items.filter(i=>i.kind==='word'&&i.progress.some(p=>['mastered','review'].includes(p.status)));
  const d=modal('Generate new entries',`<p>Choose a mastered word or a category. New vocabulary follows corpus frequency, and joins your practice shuffle immediately.</p>
    <p class="fine-print">Taiwan frequency table: ${state.corpus_forms.toLocaleString()} word forms. The available pool also needs dictionary and drawing support.</p>
    <form id="generator-form"><label for="generator-source">Generate from</label><select id="generator-source"><option value="category">A category or collection</option><option value="word" ${mastered.length?'':'disabled'}>A mastered word${mastered.length?'':' · master a word first'}</option></select>
    <div id="generator-word-group"><label for="generator-word">Mastered word</label><select id="generator-word">${mastered.map(i=>`<option value="${escape(i.id)}">${escape(i.text)} · ${escape(i.pinyin)} · ${escape(i.english)}</option>`).join('')}</select></div>
    <div id="generator-category-group"><label for="generator-category">Category or collection</label><select id="generator-category"><optgroup label="Subject categories">${topics.map(([id,label])=>`<option value="${id}">${label}</option>`).join('')}</optgroup><optgroup label="Beginner collection">${collections.map(([id,label])=>`<option value="${id}">${label}</option>`).join('')}</optgroup><option value="custom">Another category…</option></select><div id="generator-custom-group"><label for="generator-custom">Category in English</label><input id="generator-custom" maxlength="80" placeholder="For example: animals, gardening, coffee"></div></div>
    <label for="generator-count">How many new entries?</label><input id="generator-count" type="number" min="1" max="20" value="2" required>
    <button class="primary full generator-submit" type="submit">Generate entries ✧</button><p class="error generator-error" role="alert"></p></form>
    <div id="generator-results" aria-live="polite"></div>`,true);
  const form=$('#generator-form',d),source=$('#generator-source',d),word=$('#generator-word',d),category=$('#generator-category',d),custom=$('#generator-custom',d);
  if(seedId&&mastered.some(i=>i.id===seedId)){source.value='word';word.value=seedId;}
  function updateFields(){
    const byWord=source.value==='word',other=category.value==='custom';
    $('#generator-word-group',d).hidden=!byWord;word.disabled=!byWord;word.required=byWord;
    $('#generator-category-group',d).hidden=byWord;category.disabled=byWord;
    $('#generator-custom-group',d).hidden=byWord||!other;custom.disabled=byWord||!other;custom.required=!byWord&&other;
  }
  source.onchange=updateFields;category.onchange=updateFields;updateFields();
  d.addEventListener('close',()=>route(),{once:true});
  form.onsubmit=async event=>{
    event.preventDefault();const button=$('.generator-submit',d),error=$('.generator-error',d),results=$('#generator-results',d);
    button.disabled=true;button.textContent='Finding eligible words…';error.textContent='';
    const body={source:source.value,count:Number($('#generator-count',d).value)};
    if(source.value==='word')body.id=word.value;else body.category=category.value==='custom'?custom.value:category.value;
    try{
      const result=await api('generate-entries',body);await refresh();
      results.innerHTML=`<div class="notice">${escape(result.message)}${result.added<result.requested&&result.added?` Only ${result.added} currently meet the frequency and drawing-support rules.`:''}</div><div class="generated-list">${result.items.map(i=>`<article><strong lang="zh-Hant">${escape(i.text)}</strong><span>${escape(i.pinyin)}</span><p>${escape(i.english)}</p></article>`).join('')}</div>`;
      button.textContent='Generate more ✧';
    }catch(e){error.textContent=e.message;button.textContent='Try again';}
    finally{button.disabled=false;}
  };
}

function addExample(){
  const d=modal('Add something you want to say',`<p>Search by Traditional Chinese, English, or pinyin. Choose a dictionary meaning before adding it.</p><label for="entry-search">Word or phrase</label><div class="search-wrap"><span>⌕</span><input id="entry-search" placeholder="Try coffee, 電腦, or dian nao…" autocomplete="off"></div><div id="entry-results" aria-live="polite"><p class="fine-print">Your local dictionary is ready to explore.</p></div><div class="manual-add"><p>Can’t find your phrase? Custom phrases need more than three words and strictly more than 80% mastered vocabulary. They are stored privately and only appear in practice.</p><button class="secondary save-pending">${state.services.llm?'Validate and add phrase':'Save phrase for validation'}</button></div>`,true);
  let timer,results=[];const input=$('#entry-search',d);
  input.oninput=()=>{clearTimeout(timer);const query=input.value;timer=setTimeout(async()=>{try{const data=await api('search?q='+encodeURIComponent(query));if(input.value!==query)return;results=data.results;$('#entry-results',d).innerHTML=results.map((r,index)=>`<div class="search-result"><div><strong lang="zh-Hant">${escape(r.text)}</strong><span>${escape(r.pinyin)}</span><p>${escape(r.english)}</p>${r.usage_note?`<p class="fine-print">${escape(r.usage_note)}</p>`:''}${r.meanings?.length>1?`<select aria-label="Choose meaning for ${escape(r.text)}" data-sense="${index}">${r.meanings.map(m=>`<option value="${escape(m)}">${escape(m)}</option>`).join('')}</select>`:''}</div><button class="secondary add-result" data-index="${index}">${r.deleted?'Restore ＋':'Add ＋'}</button></div>`).join('')||'<p class="notice">No validated match. Try a shorter word, or save this phrase for validation.</p>';$$('.add-result',d).forEach(b=>b.onclick=async()=>{const row=results[+b.dataset.index];b.disabled=true;b.textContent='Adding…';try{const sense=$(`[data-sense="${b.dataset.index}"]`,d)?.value;const result=await api('add',{id:row.id,source:row.source,meaning:sense});toast(result.message);await refresh();b.textContent='Added ✓';}catch(e){toast(e.message);b.disabled=false;b.textContent='Retry';}});}catch(e){toast(e.message);}},250);};
  $('.save-pending',d).onclick=async()=>{const button=$('.save-pending',d);button.disabled=true;try{let result=await api('add',{text:input.value});if(result.pending&&state.services.llm)result=await api('validate',{id:result.id});toast(result.message);d.close();await route();}catch(e){toast(e.message);}finally{button.disabled=false;}};
  input.focus();
}

function settings(){
  $('#main').innerHTML=pageHeader('YOUR SPACE, YOUR PACE','Make yourself at home.','Adjust your review rhythm and keep your learning safe.')+
    `<div class="settings-grid"><section class="settings-card"><h2>Learning rhythm</h2><form id="settings-form"><label for="probability">Daily review probability</label><div class="number-input"><input id="probability" type="number" min="0" max="100" step="0.1" value="${state.settings.probability*100}" required><span>% per mastered item, per day</span></div><p class="fine-print">Every missed calendar day is checked once when you return. Reopening the app never rerolls a day.</p><label for="timezone">Your timezone</label><input id="timezone" value="${escape(state.settings.timezone)}" required><p class="fine-print">For example: America/New_York, Asia/Taipei, or Europe/London.</p><button class="primary">Save settings</button></form></section>
    <section class="settings-card"><h2>Your interests</h2><p>${state.settings.interests.length?state.settings.interests.map(t=>topicLabel(t)).map(escape).join(' · '):'Choose the things you’d like to talk about.'}</p><p>${escape(state.settings.interest_text)}</p><button class="secondary edit-topics">Edit my interests ↗</button></section>
    <section class="settings-card"><h2>Local tools</h2><div class="service-row"><span>Mandarin pronunciation</span><span class="pill ${state.services.audio?'ready':'waiting'}">${state.services.audio?'Installed · offline':'Setup needed'}</span></div><p class="fine-print">Prepared Taiwan character recordings and a local Mandarin voice play offline. Audio is cached on your machine.</p><div class="service-row"><span>Character shape checker</span><span class="pill ready">Embedded · offline</span></div><p class="fine-print">Compares shape against character templates. Stroke order and direction are not graded.</p><div class="service-row"><span>One-time explanations</span><span class="pill ${state.services.llm?'ready':'waiting'}">${state.services.llm?'Configured':'Optional'}</span></div><p class="fine-print">The starter explanations are included. Set up an optional provider to generate and cache new explanations or validate custom phrases. See the README for configuration.</p></section>
    <section class="settings-card"><h2>A copy of your progress</h2><p>Export your library, settings, and learning history. Keep a backup somewhere you trust.</p><a href="/api/backup" class="secondary" download>↓ Export backup</a><hr><label for="restore-file">Restore a 你howdy backup</label><input id="restore-file" type="file" accept="application/json,.json"><p class="fine-print">Restoring replaces your current local learning data.</p><button class="secondary restore-button" disabled>Restore selected backup</button><p id="restore-message" role="status"></p></section></div>`;
  $('#settings-form').onsubmit=async e=>{e.preventDefault();try{await api('settings',{probability:Number($('#probability').value)/100,timezone:$('#timezone').value});await refresh();toast('Settings saved.');}catch(error){toast(error.message);}};
  $('.edit-topics').onclick=editInterests;
  $('#restore-file').onchange=()=>$('.restore-button').disabled=!$('#restore-file').files.length;
  $('.restore-button').onclick=async()=>{try{const file=$('#restore-file').files[0];const backup=JSON.parse(await file.text());const d=modal('Restore this backup?',`<p>This will replace your current library and learning progress with <strong>${escape(file.name)}</strong>.</p><p>Export a backup first if you want to keep your current progress.</p><button class="primary confirm-restore">Replace local data</button>`);$('.confirm-restore',d).onclick=async()=>{try{await api('restore',backup);d.close();toast('Backup restored.');await route();}catch(e){toast(e.message);}};}catch(e){toast('Could not read this backup: '+e.message);}};
}

window.addEventListener('hashchange',route);
window.addEventListener('unhandledrejection',event=>{toast(event.reason?.message||'Something went wrong. Please retry.');});
// Catch up calendar-day review trials while the app stays open, without disrupting a prompt.
setInterval(()=>refresh().catch(()=>{}),60_000);
route();
