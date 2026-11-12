import {escape} from './ui.js';

// All coordinates come from the grader, including Hard's scale/translation
// alignment. Geometry is released only after an answer has been submitted.
export function drawingFeedback(details, characters, text){
  const glyphs=Array.from(text);
  const paths=list=>list.map(d=>`<path d="${escape(d)}"/>`).join('');
  const ink=(strokes,className)=>strokes.map(stroke=>{
    if(stroke.length===1)return `<circle class="${className}" cx="${stroke[0][0]}" cy="${stroke[0][1]}" r="10"/>`;
    return `<polyline class="${className}" points="${stroke.map(p=>p.join(',')).join(' ')}"/>`;
  }).join('');
  const drawings=details.flatMap((detail,i)=>{
    if(!detail.overlay||detail.correct)return [];
    const overlay=detail.overlay,index=characters[i].index,label=`Character ${index+1}: ${glyphs[index]}`;
    return [`<figure class="drawing-comparison"><figcaption>${escape(label)}</figcaption>
      <div class="drawing-board"><div class="board-grid"></div>
        <svg class="drawing-overlay" viewBox="0 0 1024 1024" role="img" aria-label="${escape(label)} — correct character overlaid with your drawing; red marks missing or misplaced strokes">
          <g class="comparison-reference" transform="translate(0 900) scale(1 -1)">${paths(overlay.reference)}</g>
          <g class="comparison-missing" transform="translate(0 900) scale(1 -1)">${paths(overlay.missing)}</g>
          ${ink(overlay.ink,'comparison-ink')}${ink(overlay.incorrect_ink,'comparison-incorrect')}
        </svg>
      </div></figure>`];
  }).join('');
  if(!drawings)return '';
  return `<section class="drawing-corrections" aria-label="Drawing corrections"><h3>Compare your strokes</h3>
    <p>Red marks show where your drawing differs from the correct shape.</p>
    <ul class="comparison-legend"><li class="legend-reference">Correct shape</li><li class="legend-ink">Your drawing</li><li class="legend-missing">Missing or incomplete stroke</li><li class="legend-incorrect">Extra or misplaced ink</li></ul>
    <div class="drawing-comparisons">${drawings}</div></section>`;
}
