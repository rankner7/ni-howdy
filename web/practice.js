import {$, $$, api, escape, toast, showInfo, infoContent, loadExamples} from './ui.js';
import {Drawing} from './drawing.js';
import {drawingFeedback} from './drawing-feedback.js';

const TITLES={flashcards:'Flashcards',drawing:'Character drawing',phrases:'Phrases'};

export async function practice(mode, state, onUpdate, addExample) {
  const main=$('#main');
  main.innerHTML=`<div class="page-heading"><h1>${TITLES[mode]}</h1><div class="page-actions"><button class="secondary add-example">＋ Add example</button></div></div><div class="practice-layout practice-simple"><section id="practice-card" class="practice-card"><div class="loading">Loading…</div></section></div>`;
  $('.add-example').onclick=addExample;
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

  }
  function render(){
    const card=$('#practice-card');
    if(prompt.empty){card.innerHTML=`<div class="empty-state"><h2>No prompts available</h2><p>${escape(prompt.message)}</p><a class="primary" href="${mode==='phrases'?'#flashcards':'#mastered'}">${mode==='phrases'?'Practise vocabulary':'Visit your mastered bin'} →</a></div>`;return;}
    if(prompt.introduction){
      drawing?.dispose?.();drawing=null;
      card.innerHTML=`<div class="notice"><strong>New word</strong></div>${infoContent(prompt.item)}<button type="button" class="audio-button" aria-label="Play Mandarin pronunciation"><span>▶</span> Listen</button><p class="audio-status" role="status"></p><form id="introduction-form"><button class="primary full continue-introduction" type="submit">Continue <span>↵</span></button><p id="practice-error" class="error" role="alert"></p></form>`;
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
        ${prompt.text?`<div class="prompt-hanzi" lang="zh-Hant">${escape(prompt.text)}</div>`:''}
        ${prompt.english?`<div class="prompt-english">${escape(prompt.english)}</div>`:''}
        ${prompt.pinyin?`<p class="pinyin">${escape(prompt.pinyin)}</p>`:''}
        ${((mode==='phrases'||mode==='flashcards')&&prompt.level<2)?`<button class="audio-button" aria-label="${mode==='phrases'?'Play phrase pronunciation':'Play Mandarin pronunciation'}"><span>▶</span> Listen${mode==='phrases'?' to the phrase':''}</button><p class="audio-status" role="status"></p>`:''}
      </div>
      ${prompt.hint?'<div class="notice amber">Information opened · this prompt counts as one miss.</div>':''}
      <form id="answer-form">
        ${mode==='drawing'?'<div id="drawing-area"></div>':`
          <input id="answer" name="answer" aria-label="${isChinese?'Chinese translation':mode==='phrases'?'English translation':'English meaning'}" autocomplete="off" spellcheck="${!isChinese}" placeholder="${isChinese?'Type Chinese translation…':mode==='phrases'?'Type English translation…':'Type English meaning…'}" ${isChinese?'lang="zh-Hant"':''}>
          ${isChinese?'<div class="ime"><label for="pinyin-input">Pinyin keyboard</label><div class="ime-row"><input id="pinyin-input" aria-label="Pinyin composition" placeholder="Type pinyin, e.g. wo" autocomplete="off" spellcheck="false"><button class="secondary" type="button" id="ime-clear">Clear</button></div><div id="candidates" aria-live="polite"></div><div class="punctuation"><button type="button">。</button><button type="button">，</button><button type="button">？</button><button type="button">！</button></div></div>':'<div id="proofreading" aria-live="polite"></div>'}
          `}
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

        audio.clipStart=Number(r.headers.get('X-Audio-Start')||0);
      }
      if(!isCurrent(button))return;
      audio.currentTime=audio.clipStart;await audio.play();status.textContent='';
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
    input.onkeydown=e=>{if(e.isComposing)return;if(e.key==='Enter'&&!input.value.trim()){e.preventDefault();$('#answer-form').requestSubmit();}else if(e.key==='Enter'||e.key===' '){e.preventDefault();if(candidates[0])choose(candidates[0].text);}else if(/^[1-9]$/.test(e.key)&&candidates[+e.key-1]){e.preventDefault();choose(candidates[+e.key-1].text);}};
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
      $('#feedback').innerHTML=`<div class="feedback ${result.correct?'success':'retry'}"><span class="feedback-symbol">${result.correct?'✓':'↻'}</span><div><h3>${result.correct?'Correct':result.hint?'Hint used':'Incorrect'}</h3><p>${escape(result.message)}</p><div class="answer-reveal"><span lang="zh-Hant">${escape(result.item.text)}</span> <small>${escape(result.item.pinyin)}</small><p>${result.item.answers.map(escape).join(' / ')}</p></div>${result.details.length?`<p class="fine-print">${result.details.map((d,i)=>`Character ${prompt.characters[i].index+1}: ${d.correct?'✓ recognised':'try again'}`).join(' · ')}</p>`:''}${result.added.length?`<p>Added to your shuffle: <strong>${result.added.map(escape).join(' · ')}</strong></p>`:''}<button class="text-button after-info">Word information</button></div></div><button class="primary next-prompt">Next prompt →</button>`;
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
