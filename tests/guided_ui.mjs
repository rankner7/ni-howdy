// Isolated canvas event/state checks; run with `node tests/guided_ui.mjs`.
// A real browser remains necessary to check layout and animation appearance.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {gunzipSync} from 'node:zlib';
import {Drawing} from '../web/drawing.js';
import {guidedStrokeCorrect} from '../web/guided.js';

const data=JSON.parse(gunzipSync(readFileSync(new URL('../nihowdy/assets/taiwan-strokes.json.gz',import.meta.url))));
const saved=new Map();
globalThis.sessionStorage={getItem:key=>saved.get(key),setItem:(key,value)=>saved.set(key,value),removeItem:key=>saved.delete(key)};
globalThis.matchMedia=()=>({matches:true});
globalThis.Path2D=class{constructor(path){this.path=path;}};
globalThis.requestAnimationFrame=()=>1;
globalThis.cancelAnimationFrame=()=>{};
function root(){
  const calls=[];
  const ctx=new Proxy({}, {get:(o,key)=>o[key]??((...args)=>calls.push([key,...args]))});
  const canvas={getContext:()=>ctx,getBoundingClientRect:()=>({left:0,top:0,width:1024,height:1024}),
    setPointerCapture(){},hasPointerCapture:()=>false,releasePointerCapture(){},setAttribute(){}};
  const nodes={'canvas':canvas,'.stroke-status':{},'.replay':{},'.undo':{},'.clear':{}};
  return {querySelector:key=>nodes[key],isConnected:true,calls};
}
const prompt={id:'guided-fixture',level:1,total_characters:2,guided_completions:2,
  characters:[...'我木'].map((ch,index)=>({index,guide:data.characters[ch],template:[]}))};
let area=root(),drawing=new Drawing(area,prompt);
const status=()=>area.querySelector('.stroke-status').textContent;
function trace(points,pointerId=1){
  const canvas=area.querySelector('canvas');
  const event=p=>({pointerId,button:0,clientX:p[0],clientY:p[1],preventDefault(){}});
  canvas.onpointerdown(event(points[0]));
  for(const p of points.slice(1))canvas.onpointermove(event(p));
  canvas.onpointerup(event(points.at(-1)));
}
assert.match(area.innerHTML,/repetition 3 of 5/);
assert.throws(()=>drawing.saveCharacter(),/every stroke/);
const first=prompt.characters[0].guide.medians;
trace([...first[0]].reverse());
assert.equal(drawing.strokes.length,0);
assert.match(status(),/Try this stroke again/);
trace(first[0]);
assert.equal(drawing.strokes.length,1);
assert.match(status(),/Stroke 2 of 7/);
assert.ok(area.calls.some(([method,path])=>method==='fill'&&path?.path===prompt.characters[0].guide.strokes[0]),'accepted ink snaps to the outline');

// Page recovery retains accepted ink and the current stroke.
drawing.dispose();area=root();drawing=new Drawing(area,prompt);
assert.equal(drawing.strokes.length,1);
assert.match(status(),/Stroke 2 of 7/);
const canvas=area.querySelector('canvas'),p=first[1][0];
canvas.onpointerdown({pointerId:1,button:0,clientX:p[0],clientY:p[1],preventDefault(){}});
canvas.onpointerdown({pointerId:2,button:0,clientX:0,clientY:0,preventDefault(){}});
canvas.onpointerup({pointerId:2,clientX:0,clientY:0});
canvas.onpointercancel({pointerId:1});
assert.equal(drawing.strokes.length,1,'a cancelled stroke and second pointer do not remove accepted strokes');
area.querySelector('.undo').onclick();
assert.equal(drawing.strokes.length,0);
for(const stroke of first)trace(stroke);
assert.match(status(),/Character complete/);
assert.equal(area.querySelector('.replay').disabled,true);
assert.equal(drawing.saveCharacter(),null);
assert.equal(drawing.index,1);
assert.equal(drawing.entries.length,1);
assert.equal(drawing.strokes.length,0);
drawing.dispose();area=root();drawing=new Drawing(area,prompt);
assert.equal(drawing.index,1,'reload recovers the second character');
assert.throws(()=>drawing.saveCharacter(),/every stroke/);
const second=prompt.characters[1].guide.medians;
trace(second[0]);area.querySelector('.clear').onclick();
assert.equal(drawing.strokes.length,0);
assert.equal(drawing.entries.length,1,'clearing affects only the current character');
for(const stroke of second)trace(stroke);
const entries=drawing.saveCharacter();
assert.equal(entries.length,2);
assert.deepEqual(entries[0].strokes,first.map(s=>[...s,s.at(-1)]));
assert.deepEqual(entries[1].strokes,second.map(s=>[...s,s.at(-1)]));
assert.equal(prompt.guided_completions,2,'only the server awards whole-word repetitions');
drawing.clearSaved();assert.equal(saved.size,0);drawing.dispose();

for(const entry of Object.values(data.characters))for(const stroke of entry.medians){
  assert.equal(guidedStrokeCorrect(stroke,stroke),true);
  assert.equal(guidedStrokeCorrect([...stroke].reverse(),stroke),false);
  assert.equal(guidedStrokeCorrect(stroke.map(([x,y])=>[x+20,y-15]),stroke),true);
}
const bend=[[100,100],[800,100],[800,800],[650,700]];
const dot=[[100,100],[130,135]];
assert.equal(guidedStrokeCorrect(dot,dot),true);
assert.equal(guidedStrokeCorrect(dot.toReversed(),dot),false);
assert.equal(guidedStrokeCorrect([bend[0],bend.at(-1)],bend),false);
assert.equal(guidedStrokeCorrect([...bend,...bend.toReversed(),...bend],bend),false);
console.log('PASS: ordered tracing, tolerance, snapping, retries, cancellation, multiple pointers, undo/clear, reload recovery, whole-word completion.');
