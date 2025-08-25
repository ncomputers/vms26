/**
 * @jest-environment jsdom
 */

global.__TEST__ = true;
const fs = require('fs');
const path = require('path');

const code = fs.readFileSync(path.resolve(__dirname, '../static/js/feed_overlays.js'), 'utf8');
new Function(code)();

const { setupFeed, applyOverlay, overlayState } = globalThis.__overlay_test__;

class MockWebSocket {
  constructor(url){
    this.url = url;
    MockWebSocket.instances.push(this);
    setTimeout(()=>this.onopen && this.onopen(),0);
  }
  close(){ this.onclose && this.onclose({code:1000}); }
}
MockWebSocket.instances=[];
global.WebSocket = MockWebSocket;
global.fetch = jest.fn().mockResolvedValue({ok:true,json:async()=>({})});

test('log keeps last five messages newest first', async () => {
  document.body.innerHTML = '<div id="token-warning" class="alert d-none"></div><div class="feed-container" data-overlay="true" data-token="tok"><img class="feed-img" data-cam="1"/></div><pre id="yolo-log" class="yolo-log"></pre>';
  const img=document.querySelector('img');
  setupFeed(img);
  overlayState.flags.show_track_lines=true;
  applyOverlay();
  await Promise.resolve();
  const ws=MockWebSocket.instances[0];
  expect(ws.url).toContain('&token=tok');
  for(let i=1;i<=6;i++){
    ws.onmessage && ws.onmessage({data:`msg${i}`});
  }
  const logEl=document.getElementById('yolo-log');
  expect(logEl.textContent.split('\n')).toEqual(['msg6','msg5','msg4','msg3','msg2']);
});
