import {escape} from './ui.js';

const milestones = [
  [100, 'Foundation (Baby)'],
  [500, 'Beginner (Kindergartner)'],
  [1000, 'Everyday (2nd grader)'],
  [2500, 'Intermediate (6th grader)'],
  [5000, 'Proficient (High schooler)'],
  [8000, 'Advanced (Adult)'],
];

export function masteryChart(history) {
  const points = history || [];
  if (!points.length) return '';
  const width=1000, height=560, left=58, right=710, top=24, bottom=510;
  // Keep earlier peaks visible after demotion, and leave room for the next goal.
  const peak=Math.max(...points.map(p=>p.mastered));
  const maximum=milestones.find(([count])=>count>peak)?.[0] || (Math.floor(peak/1000)+1)*1000;
  const start=Date.parse(points[0].date+'T00:00:00Z');
  const end=Date.parse(points.at(-1).date+'T00:00:00Z');
  const x=day=>left+(Date.parse(day+'T00:00:00Z')-start)/Math.max(86400000,end-start)*(right-left);
  const y=count=>bottom-count/maximum*(bottom-top);
  const number=value=>value.toLocaleString('en');
  const dateLabel=day=>new Intl.DateTimeFormat('en',{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'}).format(new Date(day+'T00:00:00Z'));
  // A step line preserves the known count between scoring days.
  const path=points.map((p,i)=>`${i?'H':'M'}${x(p.date).toFixed(2)}${i?'V':' '}${y(p.mastered).toFixed(2)}`).join(' ');
  const last=points.at(-1);
  return `<section class="mastery-chart" aria-labelledby="mastery-title">
    <h2 id="mastery-title">Words mastered over time</h2>
    <div class="mastery-chart-scroll" tabindex="0" role="region" aria-label="Mastery chart">
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="mastery-title mastery-description">
        <desc id="mastery-description">${last.mastered} words currently mastered. Daily totals from ${escape(dateLabel(points[0].date))} to ${escape(dateLabel(last.date))}.</desc>
        ${milestones.filter(([count])=>count<=maximum).map(([count,label])=>`<g class="mastery-milestone"><line x1="${left}" x2="${right}" y1="${y(count)}" y2="${y(count)}"/><text x="${left-12}" y="${y(count)+4}" text-anchor="end">${number(count)}</text><text x="${right+16}" y="${y(count)+4}">${label}</text></g>`).join('')}
        <line class="mastery-axis" x1="${left}" x2="${right}" y1="${bottom}" y2="${bottom}"/>
        <text class="mastery-tick" x="${left-12}" y="${bottom+4}" text-anchor="end">0</text>
        <path class="mastery-line" d="${path}"/>
        ${[0,.5,1].map(fraction=>{const day=new Date(start+(end-start)*fraction).toISOString().slice(0,10);return `<text class="mastery-tick" x="${left+(right-left)*fraction}" y="${bottom+28}" text-anchor="${fraction===0?'start':fraction===1?'end':'middle'}">${escape(dateLabel(day))}</text>`;}).join('')}
      </svg>
    </div>
  </section>`;
}
