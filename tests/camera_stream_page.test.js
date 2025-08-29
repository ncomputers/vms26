/**
 * @jest-environment jsdom
 */

global.__TEST__ = true;
const fs = require('fs');
const path = require('path');

const code = fs.readFileSync(path.resolve(__dirname, '../static/js/feed_overlays.js'), 'utf8');
new Function(code)();

const { overlayState, defaults, init } = globalThis.__overlay_test__;

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

describe('camera stream page overlay buttons', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div class="btn-group overlay-toggle-group" role="group">
        <button class="btn btn-sm btn-outline-primary overlay-toggle" data-flag="show_track_lines" id="overlayTracks">Tracks</button>
        <button class="btn btn-sm btn-outline-primary overlay-toggle" data-flag="show_ids" id="overlayId">ID</button>
      </div>
      <div id="token-warning" class="alert d-none"></div>
      <div class="feed-container" data-overlay="true" data-token="t">
        <img class="feed-img" data-cam="1" />
      </div>
      <pre id="yolo-log" class="yolo-log"></pre>`;
    Object.assign(defaults, { show_lines: true, show_track_lines: false, show_counts: true, show_ids: false });
    overlayState.flags = { show_lines:false, show_track_lines:false, show_counts:false, show_ids:false, show_person:false, show_vehicle:false, show_faces:false };
    overlayState.key = 'overlayFlags:1';
    MockWebSocket.instances = [];
    global.fetch = jest.fn().mockResolvedValue({ok:true, json:()=>Promise.resolve({ show_lines: true, show_track_lines: false, show_counts: true, show_ids: false })});
  });

  test('clicking buttons updates mode and storage', async () => {
    await init();
    const idBtn = document.getElementById('overlayId');
    idBtn.click();
    expect(overlayState.flags.show_ids).toBe(true);
    expect(JSON.parse(localStorage.getItem('overlayFlags:1')).show_ids).toBe(true);
    expect(idBtn.classList.contains('active')).toBe(true);
    const trackBtn = document.getElementById('overlayTracks');
    trackBtn.click();
    await Promise.resolve();
    expect(overlayState.flags.show_track_lines).toBe(true);
    expect(JSON.parse(localStorage.getItem('overlayFlags:1')).show_track_lines).toBe(true);
    expect(trackBtn.classList.contains('active')).toBe(true);
    expect(MockWebSocket.instances[1].url).toContain('&token=t');
  });
});
