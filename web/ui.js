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

export function toast(message) {
  const node = $('#toast'); node.textContent = message; node.classList.add('visible');
  clearTimeout(toast.timer); toast.timer = setTimeout(() => node.classList.remove('visible'), 5000);
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

export function showInfo(item, options={}) {
  const dialog = modal('A closer look', `
    ${options.penalty ? '<div class="notice amber">One incorrect attempt recorded. You can still finish this prompt for practice.</div>' : ''}
    <div class="entry-heading"><span lang="zh-Hant">${escape(item.text)}</span><div><p>${escape(item.pinyin)}</p><h3>${escape(item.english)}</h3></div></div>
    <p class="explanation">${escape(item.explanation)}</p>
    <p class="fine-print">${escape(item.explanation_origin)}</p>
    <div class="character-notes">${(item.characters||[]).map(c => `<article><span class="note-glyph" lang="zh-Hant">${escape(c.character)}</span><div><strong>${escape(c.definition)}</strong><p>${escape(c.note)}</p><small>Construction: ${escape(c.decomposition || 'Not available')}</small></div></article>`).join('')}</div>
    <div class="accepted"><span class="eyebrow">ACCEPTED ENGLISH</span><p>${item.answers.map(escape).join(' · ')}</p></div>
    <div class="source-links">${sourceLinks(item.sources)}</div>
    ${options.generate ? '<button class="secondary generate-explanation">Generate & cache a sourced explanation</button>' : ''}`, true);
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
