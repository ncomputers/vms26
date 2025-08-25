/**
 * @jest-environment jsdom
 */

test('shows field errors and re-enables button on invite creation failure', async () => {
  document.body.innerHTML = `
    <form id="manualForm">
      <input id="phone" />
      <input name="email" />
      <input name="name" />
      <select id="host"></select>
      <select id="linkHost"></select>
      <select id="linkType"></select>
      <input id="visit_time" value="2024-01-01 10:00" />
      <input id="expiry" />
      <select id="purpose"></select>
      <div class="photo-controls" data-prefix="p">
        <input type="hidden" value="img" />
      </div>
      <video id="p_preview"></video>
      <img id="p_photoPreview" />
      <button id="p_capture"></button>
      <div id="p_cameraError"></div>
      <input id="p_upload" />
      <button id="p_retake"></button>
      <div id="lookupInfo"></div>
      <button id="createBtn" type="submit">Create Invite</button>
    </form>
    <button id="genLink"></button>
    <div id="linkBox"></div>
    <table id="inviteTable"><tbody></tbody></table>
    <button id="loadMore"></button>
  `;

  global.intlTelInput = jest.fn(() => ({ isValidNumber: () => true, getNumber: () => '' }));
  const hostChoices = { getValue: () => 'H', removeActiveItems: jest.fn() };
  const linkHostChoices = { getValue: () => 'H' };
  const linkTypeChoices = { getValue: () => 'Official' };
  global.Choices = jest.fn((sel) => {
    if (sel === '#host') return hostChoices;
    if (sel === '#linkHost') return linkHostChoices;
    if (sel === '#linkType') return linkTypeChoices;
    return { getValue: () => '' };
  });
  global.PhotoUploader = class {
    constructor() {
      this.init = jest.fn(() => Promise.resolve());
      this.startCam = jest.fn(() => Promise.resolve());
      this.reset = jest.fn();
    }
  };
  global.flatpickr = jest.fn();
  window.PhotoCapture = function () { this.init = jest.fn(); };
  global.atob = (b64) => Buffer.from(b64, 'base64').toString('binary');

  let resolveFetch;
  const fetchMock = jest.fn((url) => {
    if (url === '/invites') {
      return new Promise(res => { resolveFetch = res; });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ invites: [], next_cursor: null }) });
  });
  global.fetch = fetchMock;
  global.validateEmail = () => true;
  global.showFieldError = jest.fn();
  global.clearFieldError = jest.fn();
  global.alert = jest.fn();

  const fs = require('fs');
  const path = require('path');
  const code = fs
    .readFileSync(path.resolve(__dirname, '../static/js/invite_panel.js'), 'utf8')
    .replace(/^import[^;]*;\n?/gm, '');
  // Execute invite_panel.js without the ESM imports
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  await new AsyncFunction(code)();

  const form = document.getElementById('manualForm');
  const btn = document.getElementById('createBtn');
  form.dispatchEvent(new Event('submit'));
  await Promise.resolve();
  expect(btn.disabled).toBe(true);
  resolveFetch({ ok: false, json: () => Promise.resolve({ detail: { name: 'required' } }) });
  await Promise.resolve();
  await Promise.resolve();
  expect(global.alert).toHaveBeenCalledWith('required');
  expect(btn.disabled).toBe(false);
});
