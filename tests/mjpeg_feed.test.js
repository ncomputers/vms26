/**
 * @jest-environment jsdom
 */

test('calls show/hide endpoints and clears src', () => {
  document.body.innerHTML = '<div class="modal"><img class="feed-img" data-cam="1"></div>';
  global.fetch = jest.fn(() => Promise.resolve());

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
  expect(fetch).toHaveBeenCalledWith('/api/cameras/1/show', {method: 'POST'});
  expect(img.getAttribute('src')).toBe('/api/cameras/1/mjpeg');
  document.querySelector('.modal').dispatchEvent(new Event('hidden.bs.modal'));
  expect(fetch).toHaveBeenCalledWith('/api/cameras/1/hide', {method: 'POST'});
  expect(img.getAttribute('src')).toBeNull();
});
