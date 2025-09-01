/**
 * @jest-environment jsdom
 */

test('calls show and hide around modal preview', () => {
  document.body.innerHTML = '<div class="modal"><img class="feed-img" data-cam="1"></div>';
  globalThis.__TEST__ = true;
  const fetchMock = jest.fn(() => Promise.resolve({}));
  global.fetch = fetchMock;
  const fs = require('fs');
  const path = require('path');
  const code = fs.readFileSync(path.resolve(__dirname, '../static/js/mjpeg_feed.js'), 'utf8');
  new Function(code)();
  globalThis.initMjpegFeeds(document);
  const modal = document.querySelector('.modal');
  const img = document.querySelector('img.feed-img');
  modal.dispatchEvent(new Event('shown.bs.modal'));
  expect(fetchMock).toHaveBeenCalledWith('/api/cameras/1/show', { method: 'POST' });
  expect(img.src).toContain('/api/cameras/1/mjpeg');
  modal.dispatchEvent(new Event('hidden.bs.modal'));
  expect(fetchMock).toHaveBeenLastCalledWith('/api/cameras/1/hide', { method: 'POST' });
  expect(img.getAttribute('src')).toBeNull();
});
