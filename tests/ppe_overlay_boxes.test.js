/**
 * @jest-environment jsdom
 */

global.__TEST__ = true;
const fs = require('fs');
const path = require('path');

const code = fs.readFileSync(path.resolve(__dirname, '../static/js/feed_overlays.js'), 'utf8');
new Function(code)();

const { renderOverlay } = globalThis.__overlay_test__;

test('draws ppe boxes for each type', () => {
  const canvas = { width:100, height:100 };
  const calls=[];
  const ctx = {
    clearRect: jest.fn(),
    strokeRect: (...args)=>calls.push(args),
    beginPath: jest.fn(),
    moveTo: jest.fn(),
    lineTo: jest.fn(),
    stroke: jest.fn(),
    fillText: jest.fn(),
    font: '',
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 0,
    resetTransform: jest.fn(),
    scale: jest.fn()
  };
  const info={src:{w:100,h:100}, ppe:[{type:'helmet',box:[10,10,10,10]},{type:'vest_jacket',box:[30,30,10,10]},{type:'safety_glasses',box:[50,50,10,10]}]};
  renderOverlay(ctx, canvas, info);
  expect(calls).toHaveLength(3);
});

test('handles empty ppe list', () => {
  const canvas = { width:100, height:100 };
  const calls=[];
  const ctx = {
    clearRect: jest.fn(),
    strokeRect: (...args)=>calls.push(args),
    beginPath: jest.fn(),
    moveTo: jest.fn(),
    lineTo: jest.fn(),
    stroke: jest.fn(),
    fillText: jest.fn(),
    font: '',
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 0,
    resetTransform: jest.fn(),
    scale: jest.fn()
  };
  const info={src:{w:100,h:100}, ppe:[]};
  renderOverlay(ctx, canvas, info);
  expect(calls).toHaveLength(0);
});
