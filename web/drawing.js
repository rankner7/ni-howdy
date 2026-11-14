import {$, $$, escape, glyphSVG} from './ui.js';
import {setupGuided} from './guided.js';

export class Drawing {
  constructor(root, prompt) {
    this.root=root; this.prompt=prompt; this.key='nihowdy:drawing:'+prompt.id;
    let saved={}; try {saved=JSON.parse(sessionStorage.getItem(this.key)||'{}');} catch {}
    this.index=saved.index||0; this.entries=saved.entries||[]; this.strokes=saved.strokes||[];
    this.placements=saved.placements||[]; this.selected=null;
    if (this.index >= prompt.characters.length) this.index=0;
    this.render();
  }
  persist() { sessionStorage.setItem(this.key, JSON.stringify({index:this.index,entries:this.entries,strokes:this.strokes,placements:this.placements})); }
  render() {
    this.dispose?.();
    const part=this.prompt.characters[this.index];
    const guided=this.prompt.level===1;
    this.root.innerHTML=`<div class="drawing-progress"><span>Character ${part.index+1} of ${this.prompt.total_characters}</span><div>${this.prompt.characters.map((c,i)=>`<i class="${i<this.index?'done':i===this.index?'current':''}"></i>`).join('')}</div></div>
      <div class="drawing-board ${this.prompt.level===0?'assembly':''}">
        <div class="board-grid"></div>${guided?`<svg class="template-glyph" viewBox="0 0 1024 1024" aria-hidden="true">${part.guide.strokes.map(d=>`<path d="${escape(d)}"/>`).join('')}</svg>`:glyphSVG(part.template,'template-glyph')}
        ${this.prompt.level===0 ? '<div class="component-slots"></div>' : '<canvas width="1024" height="1024" aria-label="Draw the character here"></canvas>'}
      </div>
      ${this.prompt.level===0 ? '<p class="fine-print center">Drag each piece into place, or select a piece and then a slot.</p><div class="component-palette"></div>' : `<div class="drawing-tools"><button type="button" class="text-button undo">↶ Undo stroke</button><button type="button" class="text-button clear">Clear</button>${guided?'<button type="button" class="text-button replay">↻ Show stroke</button>':''}</div>`}
      ${guided?`<p class="stroke-status fine-print center" role="status" aria-live="polite"></p><p class="fine-print center">Whole-word repetition ${Math.min(5,this.prompt.guided_completions+1)} of 5 · Taiwan stroke order</p><p class="fine-print center">Stroke source: <a href="https://stroke-order.learningweb.moe.edu.tw/" target="_blank" rel="noopener noreferrer">中華民國教育部</a></p>`:''}`;
    if (this.prompt.level===0) this.setupComponents(part); else if(guided)setupGuided(this,part);else this.setupCanvas();
    this.persist();
  }
  setupCanvas() {
    const canvas=$('canvas',this.root); const context=canvas.getContext('2d');
    const draw=()=>{
      context.clearRect(0,0,1024,1024); context.strokeStyle='#263f38'; context.lineWidth=20; context.lineCap='round'; context.lineJoin='round';
      for(const stroke of this.strokes) { if(!stroke.length)continue; context.beginPath(); context.moveTo(...stroke[0]); for(const p of stroke.slice(1))context.lineTo(...p); context.stroke(); }
    };
    let active=false;
    const point=e=>{const box=canvas.getBoundingClientRect(); return [Math.max(0,Math.min(1024,(e.clientX-box.left)/box.width*1024)),Math.max(0,Math.min(1024,(e.clientY-box.top)/box.height*1024))];};
    canvas.onpointerdown=e=>{ if(this.strokes.length>=80)return; active=true; canvas.setPointerCapture(e.pointerId); this.strokes.push([point(e)]); draw(); };
    canvas.onpointermove=e=>{if(!active)return; const s=this.strokes.at(-1); if(s.length<1000)s.push(point(e)); draw();};
    canvas.onpointerup=e=>{if(!active)return; this.strokes.at(-1).push(point(e)); active=false; this.persist(); draw();};
    canvas.onpointercancel=()=>{active=false;this.persist();};
    $('.undo',this.root).onclick=()=>{this.strokes.pop();this.persist();draw();};
    $('.clear',this.root).onclick=()=>{this.strokes=[];this.persist();draw();};
    draw();
  }
  setupComponents(part) {
    const palette=$('.component-palette',this.root), slots=$('.component-slots',this.root);
    palette.innerHTML=part.components.map((c,i)=>`<button type="button" draggable="true" class="component-piece ${this.placements.includes(c.id)?'placed':''}" data-piece="${escape(c.id)}" aria-label="Component ${i+1}">${glyphSVG(c.strokes)}<small>${i+1}</small></button>`).join('');
    slots.innerHTML=part.slots.map((s,i)=>`<button type="button" class="component-slot" data-slot="${i}" style="left:${s.center[0]/10.24}%;top:${s.center[1]/10.24}%" aria-label="Place component in slot ${i+1}">${this.placements[i] ? glyphSVG(part.components.find(c=>c.id===this.placements[i]).strokes) : `<span>${i+1}</span>`}</button>`).join('');
    // Crop each piece to its geometry so its original position is not the answer.
    $$('svg',palette).concat($$('svg',slots)).forEach(svg=>{const box=svg.getBBox();svg.setAttribute('viewBox',`${box.x-30} ${box.y-30} ${box.width+60} ${box.height+60}`);});
    const place=(index,id)=>{
      if(!id || !part.components.some(c=>c.id===id))return;
      this.placements=this.placements.map(p=>p===id?null:p); this.placements[index]=id;this.selected=null;this.persist();this.setupComponents(part);
    };
    $$('.component-piece',palette).forEach(button=>{
      button.ondragstart=e=>e.dataTransfer.setData('text/plain',button.dataset.piece);
      button.onclick=()=>{this.selected=button.dataset.piece;$$('.component-piece',palette).forEach(b=>b.classList.toggle('selected',b===button));};
    });
    $$('.component-slot',slots).forEach(button=>{
      button.ondragover=e=>{e.preventDefault();button.classList.add('over');};
      button.ondragleave=()=>button.classList.remove('over');
      button.ondrop=e=>{e.preventDefault();place(+button.dataset.slot,e.dataTransfer.getData('text/plain'));};
      button.onclick=()=>place(+button.dataset.slot,this.selected);
    });
  }
  saveCharacter() {
    const part=this.prompt.characters[this.index];
    if(this.prompt.level===1 && this.strokes.length!==part.guide.medians.length)throw new Error('Trace every stroke before continuing.');
    if(this.prompt.level===0 && part.slots.some((_,i)=>!this.placements[i])) throw new Error('Place every component before continuing.');
    this.entries[this.index]=this.prompt.level===0 ? {placements:[...this.placements]} : {strokes:this.strokes};
    if(this.index===this.prompt.characters.length-1) {this.persist();return this.entries;}
    this.index++;this.strokes=[];this.placements=[];this.render();return null;
  }
  isLast(){return this.index===this.prompt.characters.length-1;}
  clearSaved(){sessionStorage.removeItem(this.key);}
}
