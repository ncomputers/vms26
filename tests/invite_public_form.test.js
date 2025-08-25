/**
 * @jest-environment jsdom
 */
const fs = require('fs');
const path = require('path');

async function loadScript() {
  const code = fs
    .readFileSync(path.resolve(__dirname, '../static/js/invite_public.js'), 'utf8')
    .replace(/^import[^\n]*\n/, '');
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  await new AsyncFunction(code)();
}

function baseDom() {
  document.body.innerHTML = `
    <form id="pubForm">
      <input id="name" />
      <input id="phone" />
      <input id="email" />
      <select id="visitor_type"></select>
      <input id="company" />
      <input id="purpose" />
      <input id="host" />
      <input id="visit_time" />
      <input type="file" id="photo" />
      <img id="photoPreview" class="d-none" />
      <input type="checkbox" id="noPhoto" />
      <div id="noPhotoReasonBlock" class="d-none"><input id="noPhotoReason" /></div>
      <button type="submit">Submit</button>
    </form>
    <div id="msg"></div>
  `;
}

function commonStubs() {
  global.intlTelInput = jest.fn(() => ({ isValidNumber: () => true }));
  global.flatpickr = jest.fn();
  global.validateEmail = jest.fn(() => true);
  global.showFieldError = jest.fn();
  global.clearFieldError = jest.fn();
  global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true, redirect: '/ok' }) }));
  global.URL.createObjectURL = jest.fn(() => 'blob:preview');
}

test('shows preview when file selected', async () => {
  baseDom();
  commonStubs();
  await loadScript();
  const fileInput = document.getElementById('photo');
  const preview = document.getElementById('photoPreview');
  const file = new File(['a'], 'a.jpg', { type: 'image/jpeg' });
  Object.defineProperty(fileInput, 'files', { value: [file] });
  fileInput.dispatchEvent(new Event('change'));
  expect(preview.classList.contains('d-none')).toBe(false);
});

test('no photo checkbox disables file input and shows reason', async () => {
  baseDom();
  commonStubs();
  await loadScript();
  const chk = document.getElementById('noPhoto');
  const block = document.getElementById('noPhotoReasonBlock');
  const fileInput = document.getElementById('photo');
  chk.checked = true;
  chk.dispatchEvent(new Event('change'));
  expect(block.classList.contains('d-none')).toBe(false);
  expect(fileInput.disabled).toBe(true);
});
