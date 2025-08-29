/**
 * @jest-environment jsdom
 */

global.__TEST__ = true;
const fs = require('fs');
const path = require('path');

const code = fs.readFileSync(path.resolve(__dirname, '../static/js/feed_overlays.js'), 'utf8');
new Function(code)();

const { renderOverlay, settings, applyOverlay, overlayState } = globalThis.__overlay_test__;

function makeCtx(){
  const calls = {strokeRect:[], fillText:[], beginPath:[], moveTo:[], lineTo:[], stroke:[]};
  const ctx = {
    clearRect: jest.fn(),
    strokeRect: (...a)=>calls.strokeRect.push(a),
    beginPath: ()=>calls.beginPath.push(true),
    moveTo: (...a)=>calls.moveTo.push(a),
    lineTo: (...a)=>calls.lineTo.push(a),
    stroke: ()=>calls.stroke.push(true),
    fillText: (...a)=>calls.fillText.push(a),
    font:'', fillStyle:'', strokeStyle:'', lineWidth:0,
    resetTransform: jest.fn(),
    scale: jest.fn()
  };
  return {ctx,calls};
}

beforeEach(()=>{
  overlayState.flags = { show_lines:false, show_track_lines:false, show_counts:false, show_ids:false, show_person:false, show_vehicle:false, show_faces:false };
  applyOverlay();
});

test('show_ids controls label rendering', () => {
  const {ctx,calls}=makeCtx();
  const canvas={width:100,height:100};
  const info={src:{w:100,h:100}, tracks:[{id:1,label:'p',conf:0.5,box:[10,10,10,10]}]};
  overlayState.flags.show_ids = true;
  applyOverlay();
  renderOverlay(ctx,canvas,info);
  expect(calls.fillText).toHaveLength(1);
  calls.fillText.length=0;
  overlayState.flags.show_ids = false;
  applyOverlay();
  renderOverlay(ctx,canvas,info);
  expect(calls.fillText).toHaveLength(0);
});

test('show_lines and show_track_lines are independent', () => {
  const {ctx,calls}=makeCtx();
  const canvas={width:100,height:100};
  const info={src:{w:100,h:100}, lines:[[0,0,1,0]], tracks:[{id:1,box:[10,10,10,10],trail:[[10,10],[20,20]]}]};
  overlayState.flags.show_lines = true;
  applyOverlay();
  renderOverlay(ctx,canvas,info);
  const lineMove = calls.moveTo[0];
  calls.moveTo.length=0;
  overlayState.flags.show_lines = false;
  overlayState.flags.show_track_lines = true;
  applyOverlay();
  renderOverlay(ctx,canvas,info);
  const trailMove = calls.moveTo[0];
  expect(lineMove).toEqual([0,0]);
  expect(trailMove).toEqual([10,10]);
});


test('trail crossing center line sets color', () => {
  const {ctx,calls}=makeCtx();
  const canvas={width:100,height:100};
  const info={src:{w:100,h:100}, lines:[[0.5,0,0.5,1]], tracks:[{id:1,box:[10,10,10,10],trail:[[40,10],[60,10]]}]};
  overlayState.flags.show_track_lines = true;
  overlayState.flags.show_lines = true;
  applyOverlay();
  renderOverlay(ctx,canvas,info);
  expect(ctx.strokeStyle).toBe('green');
});

test('category flags filter tracks', () => {
  const {ctx,calls}=makeCtx();
  const canvas={width:100,height:100};
  const info={src:{w:100,h:100}, tracks:[
    {id:1,label:'person',box:[10,10,10,10]},
    {id:2,label:'vehicle',box:[20,20,10,10]},
    {id:3,label:'face',box:[30,30,10,10]},
  ]};
  overlayState.flags.show_person = true;
  applyOverlay();
  renderOverlay(ctx,canvas,info);
  expect(calls.strokeRect).toHaveLength(1);
  calls.strokeRect.length=0;
  overlayState.flags = { show_lines:false, show_track_lines:false, show_counts:false, show_ids:false, show_person:false, show_vehicle:true, show_faces:false };
  applyOverlay();
  renderOverlay(ctx,canvas,info);
  expect(calls.strokeRect).toHaveLength(1);
  calls.strokeRect.length=0;
  overlayState.flags = { show_lines:false, show_track_lines:false, show_counts:false, show_ids:false, show_person:false, show_vehicle:false, show_faces:false };
  applyOverlay();
  renderOverlay(ctx,canvas,info);
  expect(calls.strokeRect).toHaveLength(0);
});
