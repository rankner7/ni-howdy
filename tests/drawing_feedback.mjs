import assert from 'node:assert/strict';
import {drawingFeedback} from '../web/drawing-feedback.js';

const overlay={reference:['M 100 200 L 800 200 Z'],missing:['M 100 200 L 800 200 Z'],
  ink:[[[50,50],[700,700]],[[80,90]]],incorrect_ink:[[[50,50],[700,700]],[[80,90]]]};
const details=[{correct:true},{correct:false,overlay}];
const html=drawingFeedback(details,[{index:0},{index:1}],'電腦');
assert.match(html,/Character 2: 腦/);
assert.doesNotMatch(html,/Character 1: 電/);
assert.equal((html.match(/<figure /g)||[]).length,1);
assert.match(html,/comparison-reference/);
assert.match(html,/comparison-missing/);
assert.match(html,/polyline class="comparison-ink" points="50,50 700,700"/);
assert.match(html,/circle class="comparison-incorrect" cx="80" cy="90"/);
assert.match(html,/translate\(0 900\) scale\(1 -1\)/);
assert.match(html,/role="img" aria-label=/);
assert.match(html,/Missing or incomplete stroke/);
assert.equal(drawingFeedback([{correct:true,overlay}],[{index:0}],'我'),'');
assert.equal(drawingFeedback([{correct:false}],[{index:0}],'我'),'');
const escaped=drawingFeedback([{correct:false,overlay:{...overlay,reference:['"/><script>bad</script>']}}],[{index:0}],'<');
assert.doesNotMatch(escaped,/<script>/);
assert.match(escaped,/&lt;script&gt;/);
console.log('PASS: per-character overlays, ink and correction layers, single-point ink, accessibility labels, escaped geometry.');
