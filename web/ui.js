export const $ = (selector, root=document) => root.querySelector(selector);
export const $$ = (selector, root=document) => [...root.querySelectorAll(selector)];
export const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

export async function api(path, body) {
  const response = await fetch('/api/'+path, body === undefined ? {} : {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The request could not be completed.');
  return data;
}

export function toast(message, action=null) {
  const node = $('#toast'); node.textContent = message; node.classList.add('visible');
  if(action){
    const button=document.createElement('button');button.className='toast-action';button.textContent=action.label;
    button.onclick=async()=>{button.disabled=true;try{await action.run();node.classList.remove('visible');}catch(error){toast(error.message);}};
    node.append(button);
  }
  const dialog=$('#dialog');
  if(dialog.open){
    let feedback=$('.dialog-message',dialog);
    if(!feedback){feedback=document.createElement('p');feedback.className='dialog-message notice';feedback.setAttribute('role','status');$('.dialog-heading',dialog).after(feedback);}
    feedback.textContent=message;
  }
  clearTimeout(toast.timer); toast.timer = setTimeout(() => node.classList.remove('visible'), action?15000:5000);
}

export function modal(title, content, wide=false) {
  const dialog = $('#dialog');
  dialog.className = wide ? 'wide' : '';
  dialog.innerHTML = `<div class="dialog-heading"><h2>${escape(title)}</h2><button class="icon-button close-dialog" aria-label="Close dialog">×</button></div>${content}`;
  $('.close-dialog', dialog).onclick = () => dialog.close();
  if (!dialog.open) dialog.showModal();
  return dialog;
}

export function sourceLinks(sources=[]) {
  return sources.filter(s => /^https:\/\//.test(s.url)).map(s => `<a href="${escape(s.url)}" target="_blank" rel="noopener noreferrer">${escape(s.title)} ↗</a>`).join('');
}

export function infoContent(item, options={}) {
  return `
    <section class="word-information">
    ${options.penalty ? '<div class="notice amber">One incorrect attempt recorded. You can still finish this prompt for practice.</div>' : ''}
    <div class="entry-heading"><span lang="zh-Hant">${escape(item.text)}</span><div><p>${escape(item.pinyin)}</p><h3>${escape(item.english)}</h3></div></div>
    <div class="info-columns"><div class="word-details">
    ${item.usage_note?`<p class="explanation">${escape(item.usage_note)}</p>`:''}
    <p class="explanation">${escape(item.explanation)}</p>
    <p class="fine-print">${escape(item.explanation_origin)}</p>
    <div class="character-notes">${(item.characters||[]).map(c => `<article><span class="note-glyph" lang="zh-Hant">${escape(c.character)}</span><div><strong>${escape(c.definition)}</strong><p>${escape(c.note)}</p><small>Construction: ${escape(c.decomposition || 'Not available')}</small></div></article>`).join('')}</div>
    <div class="accepted"><span class="eyebrow">ACCEPTED ENGLISH</span><p>${item.answers.map(escape).join(' · ')}</p></div>
    </div>
    ${item.kind==='word'? '<section class="context-examples"><h3>Example phrases</h3><p>Finding examples…</p></section>':''}
    </div>
    ${item.kind!=='word'?`<div class="source-links">${sourceLinks(item.sources)}</div>`:''}
    ${options.generate ? '<button class="secondary generate-explanation">Generate & cache a sourced explanation</button>' : ''}</section>`;
}

export async function loadExamples(item, root) {
  const section=$('.context-examples', root);
  if(!section)return;
  try {
    const {examples}=await api('word-examples',{id:item.id});
    if(!section.isConnected)return;
    try {
      const credits=JSON.parse(localStorage.getItem('example-credits') || '{}');
      for(const example of examples) credits[example.text]=example.sources;
      localStorage.setItem('example-credits', JSON.stringify(credits));
    } catch {}
    section.innerHTML='<h3>Example phrases</h3>'+(examples.length?examples.map(e=>`<article class="context-example"><p class="example-sentence" lang="zh-Hant">${escape(e.text)}</p><p class="example-pinyin">${escape(e.pinyin)}</p><p class="example-translation">${escape(e.english)}</p></article>`).join(''):'<p>No examples are available for this word yet.</p>');
  } catch { if(section.isConnected)section.innerHTML='<h3>Example phrases</h3><p>Examples are currently unavailable.</p>'; }
}

export function showInfo(item, options={}) {
  const dialog = modal('A closer look', infoContent(item, options), true);
  loadExamples(item, dialog);
  if (options.generate) $('.generate-explanation', dialog).onclick = async event => {
    const button = event.currentTarget; button.disabled = true; button.textContent = 'Preparing explanation…';
    try { const result = await api('explain',{id:item.id}); showInfo(result.item); toast('Explanation saved locally.'); }
    catch (error) { toast(error.message); button.disabled = false; button.textContent = 'Retry explanation'; }
  };
}

export function pageHeader(kicker, title, description, actions='') {
  return `<div class="page-heading"><div><p class="eyebrow">${escape(kicker)}</p><h1>${escape(title)}</h1><p class="page-description">${escape(description)}</p></div><div class="page-actions">${actions}</div></div>`;
}

export function glyphSVG(paths, className='') {
  return `<svg class="${className}" viewBox="0 0 1024 1024" aria-hidden="true"><g transform="translate(0 900) scale(1 -1)">${paths.map(d => `<path d="${escape(d)}"/>`).join('')}</g></svg>`;
}
