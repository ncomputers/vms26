/**
 * @jest-environment jsdom
 */

global.__TEST__ = true;
const fs = require('fs');
const path = require('path');

const code = fs.readFileSync(path.resolve(__dirname, '../static/js/feed_overlays.js'), 'utf8');
new Function(code)();

const { setupFeed, applyOverlay, overlayState, defaults } = globalThis.__overlay_test__;

function mount(html){
  document.body.innerHTML = html;
  return document.querySelector('img');
}

beforeEach(() => {
  document.body.innerHTML = '';
  Object.assign(defaults, { show_lines: true, show_track_lines: true, show_counts: true, show_face_boxes: true, show_ids: true });
  overlayState.key = 'test';
  overlayState.flags = { show_lines:false, show_track_lines:false, show_counts:false, show_face_boxes:false, show_ids:false, show_person:false, show_vehicle:false, show_faces:false };
  MockWebSocket.instances = [];
  global.fetch = jest.fn().mockResolvedValue({ok:true,json:async()=>({})});
  applyOverlay();
});

class MockWebSocket {
  constructor(url){
    this.url = url;
    MockWebSocket.instances.push(this);
    this.closed = false;
    setTimeout(()=>this.onopen && this.onopen(),0);
  }
  close(){ this.closed = true; this.onclose && this.onclose(); }
}
MockWebSocket.instances = [];
global.WebSocket = MockWebSocket;

test('toggling overlay adds/removes canvas and websocket', async () => {
  const img = mount('<div class="feed-container" data-overlay="true" data-token="tok"><img class="feed-img" data-cam="1"/></div>');
  setupFeed(img);
  expect(document.querySelector('canvas.overlay')).toBeNull();
  expect(MockWebSocket.instances.length).toBe(0);

  overlayState.flags.show_track_lines = true;
  applyOverlay();
  await Promise.resolve();
  expect(document.querySelector('canvas.overlay')).not.toBeNull();
  expect(MockWebSocket.instances.length).toBe(1);
  expect(MockWebSocket.instances[0].url).toContain('&token=tok');

  overlayState.flags.show_track_lines = false;
  applyOverlay();
  expect(document.querySelector('canvas.overlay')).toBeNull();
  expect(MockWebSocket.instances[0].closed).toBe(true);
});

test('setupFeed ignores feeds without overlay flag', async () => {
  overlayState.flags.show_track_lines = true;
  applyOverlay();
  await Promise.resolve();
  const img = mount('<div class="feed-container"><img class="feed-img" data-cam="2"/></div>');
  setupFeed(img);
  expect(document.querySelector('canvas.overlay')).toBeNull();
});

test('missing token fetches token before connecting', async () => {
  document.body.innerHTML = '<div id="token-warning" class="alert d-none"></div><div class="feed-container" data-overlay="true" data-token=""><img class="feed-img" data-cam="4"/></div>';
  const img = document.querySelector('img');
  global.fetch = jest.fn().mockResolvedValue({ ok:true, json:()=>Promise.resolve({token:'newtok'}) });
  setupFeed(img);
  overlayState.flags.show_track_lines = true;
  applyOverlay();
  await new Promise(r=>setTimeout(r,0));
  expect(MockWebSocket.instances.length).toBe(1);
  expect(MockWebSocket.instances[0].url).toContain('&token=newtok');
  expect(document.getElementById('token-warning').classList.contains('d-none')).toBe(true);
});

test('invalid token triggers warning on close', async () => {
  const warn = jest.spyOn(console, 'warn').mockImplementation(()=>{});
  const img = mount('<div id="token-warning" class="alert d-none"></div><div class="feed-container" data-overlay="true" data-token="bad"><img class="feed-img" data-cam="5"/></div>');
  setupFeed(img);
  overlayState.flags.show_track_lines = true;
  applyOverlay();
  await Promise.resolve();
  const ws = MockWebSocket.instances[0];
  expect(ws.url).toContain('&token=bad');
  ws.onclose({code:1008});
  expect(warn).toHaveBeenCalled();
  warn.mockRestore();
});

test('load event updates src with natural size when enabled', async () => {
  overlayState.flags.show_track_lines = true;
  applyOverlay();
  const img = mount('<div class="feed-container" data-overlay="true" data-token="tok"><img class="feed-img" data-cam="3"/></div>');
  const { dataMap } = globalThis.__overlay_test__;
  setupFeed(img);
  await Promise.resolve();
  Object.defineProperty(img, 'naturalWidth', { value: 320, configurable: true });
  Object.defineProperty(img, 'naturalHeight', { value: 240, configurable: true });
  img.dispatchEvent(new Event('load'));
  expect(dataMap['3'].src).toEqual({ w: 320, h: 240 });
});
