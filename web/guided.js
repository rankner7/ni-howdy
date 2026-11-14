// Match the server's ordered trace check; later levels remain shape-only.
const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
const length=points=>points.slice(1).reduce((sum,p,i)=>sum+distance(points[i],p),0);
function resample(points){
  const out=[];
  for(let i=1;i<points.length;i++){
    const a=points[i-1],b=points[i],steps=Math.max(1,Math.ceil(distance(a,b)/16));
    for(let j=0;j<steps;j++)out.push([a[0]+(b[0]-a[0])*j/steps,a[1]+(b[1]-a[1])*j/steps]);
  }
  if(points.length)out.push(points.at(-1));
  return out;
}
export function guidedStrokeCorrect(stroke,target){
  if(stroke.length<2||target.length<2)return false;
  if(distance(stroke[0],target[0])>85||distance(stroke.at(-1),target.at(-1))>85)return false;
  if([0,1].reduce((sum,i)=>sum+(stroke.at(-1)[i]-stroke[0][i])*(target.at(-1)[i]-target[0][i]),0)<=0)return false;
  const targetLength=length(target),inkLength=length(stroke);
  if(inkLength<.65*targetLength||inkLength>1.6*targetLength)return false;
  const ink=resample(stroke),guide=resample(target);
  let previous=Array(guide.length).fill(Infinity);
  for(let i=0;i<ink.length;i++){
    const current=[];
    for(let j=0;j<guide.length;j++){
      const best=i===0&&j===0?0:Math.min(previous[j],j?previous[j-1]:Infinity,j?current[j-1]:Infinity);
      current.push(Math.max(distance(ink[i],guide[j]),best));
    }
    previous=current;
  }
  return previous.at(-1)<=75;
}

export function setupGuided(drawing,part){
  const root=drawing.root,canvas=root.querySelector('canvas'),ctx=canvas.getContext('2d');
  const status=root.querySelector('.stroke-status'),replay=root.querySelector('.replay');
  const guides=part.guide.medians,shapes=part.guide.strokes.map(path=>new Path2D(path));
  let active=null,ink=[],failed=[],frame=0,timer=0,started=0;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const point=e=>{const b=canvas.getBoundingClientRect();return [Math.max(0,Math.min(1024,(e.clientX-b.left)/b.width*1024)),Math.max(0,Math.min(1024,(e.clientY-b.top)/b.height*1024))];};
  const line=(points,color,width=20)=>{
    if(!points.length)return;
    ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.lineCap='round';ctx.lineJoin='round';
    ctx.moveTo(...points[0]);for(const p of points.slice(1))ctx.lineTo(...p);ctx.stroke();
  };
  function draw(now=performance.now()){
    ctx.clearRect(0,0,1024,1024);
    ctx.fillStyle='#172c55';for(let i=0;i<drawing.strokes.length;i++)ctx.fill(shapes[i]);
    const guide=guides[drawing.strokes.length];
    if(guide){
      ctx.fillStyle='#d6e1f2';ctx.fill(shapes[drawing.strokes.length]);
      ctx.setLineDash([10,14]);line(guide,'#375b98',9);ctx.setLineDash([]);
      const samples=resample(guide),fraction=reduced?1:Math.min(1,(now-started)/1000);
      if(active===null)line(samples.slice(0,Math.max(1,Math.ceil(samples.length*fraction))),'#375b98',20);
      ctx.beginPath();ctx.arc(...guide[0],22,0,Math.PI*2);ctx.fillStyle='#375b98';ctx.fill();
      const end=guide.at(-1),before=guide.at(-2),angle=Math.atan2(end[1]-before[1],end[0]-before[0]);
      ctx.beginPath();ctx.moveTo(...end);ctx.lineTo(end[0]-32*Math.cos(angle-.5),end[1]-32*Math.sin(angle-.5));ctx.lineTo(end[0]-32*Math.cos(angle+.5),end[1]-32*Math.sin(angle+.5));ctx.closePath();ctx.fill();
      if(!reduced&&active===null&&fraction<1&&root.isConnected)frame=requestAnimationFrame(draw);
    }
    line(failed,'#b45b47');line(ink,'#172c55');
  }
  function update(message){
    const count=drawing.strokes.length;
    status.textContent=message||(count===guides.length?'Character complete. Continue to save it.':`Stroke ${count+1} of ${guides.length} · Start at the dot and follow the arrow.`);
    replay.disabled=count===guides.length||active!==null;
    canvas.setAttribute('aria-label',count===guides.length?'Character complete':`Trace stroke ${count+1} of ${guides.length}`);
  }
  function animate(){cancelAnimationFrame(frame);started=performance.now();draw();}
  function reset(){
    if(active!==null&&canvas.hasPointerCapture(active))canvas.releasePointerCapture(active);
    active=null;ink=[];failed=[];clearTimeout(timer);drawing.persist();update();animate();
  }
  replay.onclick=()=>{failed=[];update();animate();};
  canvas.onpointerdown=e=>{
    if(active!==null||e.button!==0||drawing.strokes.length===guides.length)return;
    e.preventDefault();cancelAnimationFrame(frame);clearTimeout(timer);failed=[];
    active=e.pointerId;canvas.setPointerCapture(active);ink=[point(e)];update();draw();
  };
  canvas.onpointermove=e=>{if(e.pointerId!==active)return;if(ink.length<1000)ink.push(point(e));draw();};
  canvas.onpointerup=e=>{
    if(e.pointerId!==active)return;
    if(ink.length<1000)ink.push(point(e));
    const accepted=guidedStrokeCorrect(ink,guides[drawing.strokes.length]);
    if(accepted)drawing.strokes.push(ink);else failed=ink;
    active=null;ink=[];drawing.persist();
    update(accepted?undefined:'Try this stroke again, from the dot to the arrow. Your progress is saved.');animate();
    if(!accepted)timer=setTimeout(()=>{failed=[];if(root.isConnected)animate();},900);
  };
  canvas.onpointercancel=e=>{if(e.pointerId===active)reset();};
  canvas.onlostpointercapture=e=>{if(e.pointerId===active)reset();};
  root.querySelector('.undo').onclick=()=>{drawing.strokes.pop();reset();};
  root.querySelector('.clear').onclick=()=>{drawing.strokes=[];reset();};
  drawing.dispose=()=>{cancelAnimationFrame(frame);clearTimeout(timer);};
  update();animate();
}
