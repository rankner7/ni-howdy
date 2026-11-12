import {$, $$, api, escape, modal, toast, showInfo, infoContent, loadExamples, pageHeader, glyphSVG} from './ui.js';
import {Drawing} from './drawing.js';
import {drawingFeedback} from './drawing-feedback.js';

const COPY={
  flashcards:['RECOGNISE & RECALL','A word at a time.','Connect what you see and hear with what it means.'],
  drawing:['NOTICE & CREATE','Make your mark.','Build characters from their parts, then draw them from memory.'],
  phrases:['CONNECT & EXPRESS','Put it into words.','Bring familiar vocabulary together in useful, everyday sentences.']
};

export async function practice(mode, state, onUpdate, addExample) {
  const main=$('#main'); const [kicker,title,description]=COPY[mode];
  main.innerHTML=pageHeader(kicker,title,description,'<button class="secondary add-example">＋ Add example</button>')+'<div class="practice-layout"><section id="practice-card" class="practice-card"><div class="loading">Choosing your next prompt…</div></section><aside class="practice-aside"></aside></div>';
  $('.add-example').onclick=addExample;
  $('.practice-aside').innerHTML=`<div class="side-note"><span class="eyebrow">HOW YOU GROW</span><h3>A little challenge.<br>A little more confidence.</h3><ol><li>${mode==='drawing'?'Guided drawing takes five whole-word repetitions, spread across random practice. Other levels take one correct answer.':'One correct answer moves you up a level.'}</li><li>Three consecutive misses move you down.</li><li>Pass the hardest level to master it.</li></ol><button class="text-button example-button">See a worked example ↗</button></div><div class="side-note muted-note"><span class="tiny-symbol">✧</span><h4>Understanding is part of learning.</h4><p>New words open with a free introduction. During practice, opening the information icon counts as one miss.</p></div><p class="fine-print">Newly discovered words join your shuffle automatically.</p>`;
  $('.example-button').onclick=()=>example(mode);
  let prompt, drawing, busy=false, audio, autoplayTimer;
  const practiceCard=$('#practice-card');
  const isCurrent=card=>main.dataset.route===mode&&practiceCard.isConnected&&card.isConnected;
  async function load(){
    clearTimeout(autoplayTimer);
    const next=await api('prompt',{mode});
    if(!isCurrent(practiceCard))return;
    if(prompt?.id!==next.id&&audio){audio.pause();audio.dispose?.();URL.revokeObjectURL(audio.src);audio=null;}
    prompt=next;
    render();
    if(!prompt.empty&&mode==='phrases'){
      const key=`nihowdy:example:${mode}:${prompt.level}`;
      if(!localStorage.getItem(key)){localStorage.setItem(key,'yes');await example(mode);}
    }
  }
  function render(){
    const card=$('#practice-card');
    if(prompt.empty){card.innerHTML=`<div class="empty-state"><span class="empty-symbol">${mode==='phrases'?'語':'✧'}</span><h2>${mode==='phrases'?'First, give your words a foundation.':'A good place to pause.'}</h2><p>${escape(prompt.message)}</p><a class="primary" href="${mode==='phrases'?'#flashcards':'#mastered'}">${mode==='phrases'?'Practise vocabulary':'Visit your mastered bin'} →</a></div>`;return;}
    if(prompt.introduction){
      drawing?.dispose?.();drawing=null;
      card.innerHTML=`<div class="notice"><strong>✧ New word added</strong><p>Meet this word before practising ${mode==='drawing'?'drawing':'flashcards'}. Take your time with its meaning and construction.</p></div>${infoContent(prompt.item)}<button type="button" class="audio-button" aria-label="Play Mandarin pronunciation"><span>▶</span> Listen</button><p class="audio-status" role="status"></p><form id="introduction-form"><button class="primary full continue-introduction" type="submit">Continue <span>↵</span></button><p class="fine-print">Press Enter to continue · no answer needed</p><p id="practice-error" class="error" role="alert"></p></form>`;
      setupAudio(card);
      loadExamples(prompt.item, card);
      $('#introduction-form',card).onsubmit=async event=>{
        event.preventDefault();if(busy)return;
        busy=true;const button=$('.continue-introduction',card);button.disabled=true;
        try{await api('answer',{id:prompt.id,continue:true});await load();}
        catch(error){$('#practice-error',card).textContent=error.message;button.disabled=false;}
        finally{busy=false;}
      };
      $('.continue-introduction',card).focus({preventScroll:true});
      return;
    }
    const isChinese=mode==='phrases'&&prompt.level===2;
    card.innerHTML=`<div class="practice-top"><span class="pill">${prompt.review?'↻ Review · ':''}${escape(prompt.level_name)}</span><span class="attempt-counter">${prompt.failures} / 3 misses</span><button class="icon-button prompt-info" aria-label="Show explanation and count one incorrect attempt">ⓘ</button></div>
      <div class="level-track">${prompt.levels.map((l,i)=>`<span class="${i<=prompt.level?'filled':''}" title="${escape(l)}"></span>`).join('')}</div>
      <div class="prompt-content ${mode}">
        <p class="eyebrow">${mode==='drawing'?'DRAW THE MEANING':isChinese?'SAY THIS IN CHINESE':'WHAT DOES THIS MEAN?'}</p>
        ${prompt.text?`<div class="prompt-hanzi" lang="zh-Hant">${escape(prompt.text)}</div>`:''}
        ${prompt.english?`<div class="prompt-english">${escape(prompt.english)}</div>`:''}
        ${prompt.pinyin?`<p class="pinyin">${escape(prompt.pinyin)}</p>`:''}
        ${((mode==='phrases'||mode==='flashcards')&&prompt.level<2)?`<button class="audio-button" aria-label="${mode==='phrases'?'Play phrase pronunciation':'Play Mandarin pronunciation'}"><span>▶</span> Listen${mode==='phrases'?' to the phrase':''}</button><p class="audio-status" role="status"></p>`:''}
      </div>
      ${prompt.hint?'<div class="notice amber">Information opened · this prompt counts as one miss.</div>':''}
      <form id="answer-form">
        ${mode==='drawing'?'<div id="drawing-area"></div>':`<label for="answer">${isChinese?'Your Chinese translation':'Your English '+(mode==='phrases'?'translation':'meaning')}</label>
          <input id="answer" name="answer" autocomplete="off" spellcheck="${!isChinese}" placeholder="${isChinese?'Choose characters using pinyin below…':'Type your answer…'}" ${isChinese?'lang="zh-Hant"':''}>
          ${isChinese?'<div class="ime"><label for="pinyin-input">Pinyin keyboard</label><div class="ime-row"><input id="pinyin-input" aria-label="Pinyin composition" placeholder="Type pinyin, e.g. wo" autocomplete="off" spellcheck="false"><button class="secondary" type="button" id="ime-clear">Clear</button></div><div id="candidates" aria-live="polite"></div><div class="punctuation"><button type="button">。</button><button type="button">，</button><button type="button">？</button><button type="button">！</button></div><p class="fine-print">Type a syllable or word, then select a candidate. Your system’s Chinese keyboard works too.</p></div>':'<div id="proofreading" aria-live="polite"></div>'}
          <p class="answer-rule">${isChinese?'Enter the Chinese characters. Ending punctuation is optional.':mode==='phrases'?'Use a complete sentence with punctuation. Capitalization doesn’t matter.':'Use the dictionary meaning. Capitalization doesn’t matter; punctuation does.'}</p>`}
        <button class="primary check-answer" type="submit">Check answer <span>↵</span></button>
        <p id="practice-error" class="error" role="alert"></p>
      </form><div id="feedback" aria-live="polite"></div>`;
    $('.prompt-info',card).onclick=async()=>{try{const result=await api('info',{id:prompt.id});prompt.hint=true;showInfo(result.item,{penalty:true});await onUpdate();$('.attempt-counter').textContent='Hint used';}catch(e){toast(e.message);}};
    if(mode==='drawing'){
      drawing?.dispose?.();drawing=new Drawing($('#drawing-area'),prompt);updateDrawingButton();
    }else{
      const input=$('#answer');input.value=sessionStorage.getItem('nihowdy:answer:'+prompt.id)||'';
      let timer;
      input.oninput=()=>{sessionStorage.setItem('nihowdy:answer:'+prompt.id,input.value);if(!isChinese){clearTimeout(timer);timer=setTimeout(()=>proofread(input.value),600);}};
      if(isChinese)setupIME();
    }
    setupAudio(card);
    $('#answer-form').onsubmit=submit;
  }
  function setupAudio(card){
    const audioButton=$('.audio-button',card);
    if(audioButton){
      audioButton.onclick=()=>play(audioButton);
      autoplayTimer=setTimeout(()=>{if(isCurrent(audioButton))play(audioButton);},500);
    }
  }
  async function play(button){
    clearTimeout(autoplayTimer);
    if(!isCurrent(button)||button.disabled)return;
    const status=$('.audio-status',practiceCard),error=$('#practice-error',practiceCard);
    button.disabled=true;status.textContent='Preparing local audio…';
    try{
      if(!audio){
        const r=await fetch('/api/audio?prompt='+encodeURIComponent(prompt.id));
        if(!r.ok)throw new Error((await r.json()).error);
        const blob=await r.blob();
        if(!isCurrent(button))return;
        const src=URL.createObjectURL(blob);
        if(r.headers.has('X-Audio-End')){
          const context=new AudioContext();
          const buffer=await context.decodeAudioData(await blob.arrayBuffer());
          if(!isCurrent(button)){context.close();URL.revokeObjectURL(src);return;}
          let playing=null;
          const start=Number(r.headers.get('X-Audio-Start')||0),end=Number(r.headers.get('X-Audio-End'));
          audio={src,pause(){if(playing){try{playing.stop();}catch{}playing=null;}},dispose(){context.close();},
            async play(){await context.resume();this.pause();playing=context.createBufferSource();playing.buffer=buffer;playing.connect(context.destination);playing.start(0,start,end-start);}};
        }else audio=new Audio(src);
        audio.sourceLabel=r.headers.get('X-Audio-Source')||'Local pronunciation';
        audio.clipStart=Number(r.headers.get('X-Audio-Start')||0);
      }
      if(!isCurrent(button))return;
      audio.currentTime=audio.clipStart;await audio.play();status.textContent=audio.sourceLabel;
    }catch(e){if(isCurrent(button)){error.textContent=e.message;status.textContent=e.name==='NotAllowedError'?'Select Listen to play pronunciation.':'Audio unavailable. This does not count as a miss.';}}
    finally{button.disabled=false;}
  }
  async function proofread(text){
    if(!text.trim()){if($('#proofreading'))$('#proofreading').innerHTML='';return;}
    try{const data=await api('proofread',{text,phrase:mode==='phrases'});const node=$('#proofreading');if(node&&$('#answer')?.value===text)node.innerHTML=data.messages.map(m=>`<p>✎ ${escape(m)}</p>`).join('');}catch{/* Grading never depends on this helper. */}
  }
  function setupIME(){
    const input=$('#pinyin-input'), target=$('#answer');let timer;let candidates=[];
    const choose=value=>{const start=target.selectionStart??target.value.length,end=target.selectionEnd??start;target.value=target.value.slice(0,start)+value+target.value.slice(end);target.setSelectionRange(start+value.length,start+value.length);target.dispatchEvent(new Event('input'));input.value='';$('#candidates').innerHTML='';input.focus();};
    input.oninput=()=>{clearTimeout(timer);const query=input.value;timer=setTimeout(async()=>{try{const result=await api('ime?q='+encodeURIComponent(query));if(input.value!==query)return;candidates=result.candidates;$('#candidates').innerHTML=candidates.map((c,i)=>`<button type="button" data-index="${i}" title="${escape(c.pinyin)}"><span>${escape(c.text)}</span><small>${i<9?i+1:''}</small></button>`).join('')||'<p class="fine-print">No candidates. Try one syllable or a complete word.</p>';$$('#candidates button').forEach(b=>b.onclick=()=>choose(candidates[+b.dataset.index].text));}catch(e){toast(e.message);}},180);};
    input.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();if(candidates[0])choose(candidates[0].text);}else if(/^[1-9]$/.test(e.key)&&candidates[+e.key-1]){e.preventDefault();choose(candidates[+e.key-1].text);}};
    $('#ime-clear').onclick=()=>{input.value='';candidates=[];$('#candidates').innerHTML='';input.focus();};
    $$('.punctuation button').forEach(b=>b.onclick=()=>choose(b.textContent));
  }
  function updateDrawingButton(){ $('.check-answer').innerHTML=drawing.isLast()?'Check entry <span>↵</span>':'Save character & continue <span>→</span>'; }
  async function submit(event){
    event.preventDefault();if(busy)return;
    $('#practice-error').textContent='';
    let payload={id:prompt.id};
    try{
      if(mode==='drawing'){const entries=drawing.saveCharacter();if(!entries){updateDrawingButton();return;}payload.drawings=entries;}
      else {payload.text=$('#answer').value;if(!payload.text.trim())throw new Error('Enter an answer before checking.');}
      if(mode==='flashcards'&&prompt.level===1&&!state.services.audio)throw new Error('Install local audio with ./setup.sh before practising this level.');
      busy=true;$('.check-answer').disabled=true;$('.check-answer').textContent='Checking…';
      const result=await api('answer',payload);
      $('#answer-form').hidden=true;
      $('#feedback').innerHTML=`<div class="feedback ${result.correct?'success':'retry'}"><span class="feedback-symbol">${result.correct?'✓':'↻'}</span><div><h3>${result.correct?'That’s right.':result.hint?'A little context goes a long way.':'Keep going. You’re learning.'}</h3><p>${escape(result.message)}</p><div class="answer-reveal"><span lang="zh-Hant">${escape(result.item.text)}</span> <small>${escape(result.item.pinyin)}</small><p>${result.item.answers.map(escape).join(' / ')}</p></div>${result.details.length?`<p class="fine-print">${result.details.map((d,i)=>`Character ${prompt.characters[i].index+1}: ${d.correct?'✓ recognised':'try again'}`).join(' · ')}</p>`:''}${result.added.length?`<p>Added to your shuffle: <strong>${result.added.map(escape).join(' · ')}</strong></p>`:''}<button class="text-button after-info">Explore the meaning ↗</button></div></div><button class="primary next-prompt">Next prompt →</button>`;
      if(mode==='drawing'&&prompt.level>=2){
        $('.next-prompt').insertAdjacentHTML('beforebegin',drawingFeedback(result.details,prompt.characters,result.item.text));
      }
      $('.after-info').onclick=()=>showInfo(result.item);
      $('.prompt-info').onclick=()=>showInfo(result.item);
      $('.next-prompt').onclick=async()=>{audio?.pause();audio?.dispose?.();if(audio?.src)URL.revokeObjectURL(audio.src);audio=null;await load();};
      if(drawing){drawing.dispose?.();drawing.clearSaved();}sessionStorage.removeItem('nihowdy:answer:'+prompt.id);await onUpdate();$('.next-prompt').focus();
    }catch(e){$('#practice-error').textContent=e.message;$('.check-answer').disabled=false;if(drawing)updateDrawingButton();else $('.check-answer').textContent='Check answer ↵';}
    finally{busy=false;}
  }
  await load();
}

async function example(mode){
  const e=await api('example');
  const content=mode==='phrases'?`<div class="example-hanzi" lang="zh-Hant">${e.phrase}</div><p class="pinyin center">${e.phrase_pinyin}</p><p class="center">${e.phrase_english}</p><p>Start by translating characters with pinyin. Later, read just the characters. At the hardest level, use the pinyin keyboard to compose the Chinese sentence. Ending punctuation is optional, and audio is unavailable.</p>`:mode==='drawing'?`${glyphSVG(e.strokes,'example-glyph')}<p class="center"><strong>${e.text}</strong> · ${e.pinyin} · ${e.english}</p><p>Place components into the character’s layout. Next, trace each stroke in Taiwan order. Complete the whole word five times across random practice appearances, then practise adding missing strokes. At the hardest level, draw the full shape from its English meaning. Guided practice checks stroke order and direction; later levels grade shape.</p>`:`<div class="example-hanzi" lang="zh-Hant">${e.text}</div><p class="pinyin center">${e.pinyin}</p><p>Type <strong>wood</strong> for this example. At Medium, pinyin is replaced by audio. At Hard, you see only the characters, without pinyin or sound.</p>`;
  const d=modal('A quick example',`<span class="pill">Ungraded · just for learning</span>${content}<button class="primary full example-done">Got it. Let’s practise →</button>`);
  $('.example-done',d).onclick=()=>d.close();
}
