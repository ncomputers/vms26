/**
 * @jest-environment jsdom
 */

const fs = require('fs');
const path = require('path');

async function loadScript() {
  const code = fs
    .readFileSync(path.resolve(__dirname, '../static/js/invite_panel.js'), 'utf8')
    .replace(/^import[^;]*;\n?/gm, '');
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  await new AsyncFunction(code)();
}

function setupStubs() {
  global.intlTelInput = jest.fn(() => ({ isValidNumber: () => true, getNumber: () => '1234567890' }));
  const hostChoices = { getValue: () => 'H', removeActiveItems: jest.fn() };
  const linkHostChoices = { getValue: () => 'H' };
  const linkTypeChoices = { getValue: () => 'Official' };
  global.Choices = jest.fn((sel) => {
    if (sel === '#host') return hostChoices;
    if (sel === '#linkHost') return linkHostChoices;
    if (sel === '#linkType') return linkTypeChoices;
    return { getValue: () => '' };
  });
  global.flatpickr = jest.fn();
  global.PhotoUploader = jest.fn();
  global.showFieldError = jest.fn();
  global.clearFieldError = jest.fn();
  global.validateEmail = jest.fn(() => true);
  global.alert = jest.fn();
  global.atob = (b64) => Buffer.from(b64, 'base64').toString('binary');
}

test('submits invite without photo controls', async () => {
  document.body.innerHTML = `
    <form id="manualForm">
      <input id="phone" required />
      <input name="email" />
      <input name="name" required />
      <select id="host" required></select>
      <select id="visitor_type" name="visitor_type" required><option value="Guest" selected>Guest</option></select>
      <input id="company" name="company" required value="ACME" />
      <select id="linkHost"></select>
      <select id="linkType"></select>
      <input id="visit_time" value="2024-01-01 10:00" />
      <input id="expiry" />
      <select id="purpose"></select>
      <div id="lookupInfo"></div>
      <button id="createBtn" type="submit"></button>
    </form>
    <button id="genLink"></button>
    <div id="linkBox"></div>
    <table id="inviteTable"><tbody></tbody></table>
    <button id="loadMore"></button>
  `;

  setupStubs();
  const fetchMock = jest.fn((url) => {
    if (url === '/invites') {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ invite_id: 1 }) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ invites: [], next_cursor: null }) });
  });
  global.fetch = fetchMock;

  await loadScript();

  document.getElementById('phone').value = '1234567890';
  document.querySelector('input[name="name"]').value = 'Alice';
  document.getElementById('host').value = 'H';

  document.getElementById('manualForm').dispatchEvent(new Event('submit'));
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();

  expect(global.PhotoUploader).not.toHaveBeenCalled();
  expect(fetchMock).toHaveBeenCalled();
});
