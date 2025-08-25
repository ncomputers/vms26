/**
 * @jest-environment jsdom
 */

test('removes src on modal hidden', () => {
  document.body.innerHTML = '<div class="modal"><img class="feed-img" src="foo"></div>';
  globalThis.__TEST__ = true;
  const fs = require('fs');
  const path = require('path');
  const code = fs.readFileSync(path.resolve(__dirname, '../static/js/mjpeg_feed.js'), 'utf8');
  new Function(code)();
  globalThis.initMjpegFeeds(document);
  const img = document.querySelector('img.feed-img');
  document.querySelector('.modal').dispatchEvent(new Event('hidden.bs.modal'));
  expect(img.getAttribute('src')).toBeNull();
});
