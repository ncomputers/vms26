/**
 * @jest-environment jsdom
 */

const fs = require('fs');
const path = require('path');

async function loadSuggestions() {
  const code = fs
    .readFileSync(path.resolve(__dirname, '../static/js/suggestions.js'), 'utf8')
    .replace('export function initSuggestions', 'function initSuggestions');
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  return await new AsyncFunction(code + '; return initSuggestions;')();
}

test('typing does not lose focus', async () => {
  document.body.innerHTML = `
    <input name="name" id="name" />
    <input id="phone" />
    <input name="email" />
    <div id="lookupInfo"></div>
  `;
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
  const initSuggestions = await loadSuggestions();
  initSuggestions();

  const nameField = document.querySelector('input[name="name"]');
  nameField.focus();
  nameField.value = 'Alice Bob';
  nameField.dispatchEvent(new Event('input', { bubbles: true }));
  await new Promise(res => setTimeout(res, 400));
  expect(document.activeElement).toBe(nameField);
  expect(nameField.value).toBe('Alice Bob');

  const phoneField = document.getElementById('phone');
  phoneField.focus();
  phoneField.value = '1234567890';
  phoneField.dispatchEvent(new Event('input', { bubbles: true }));
  await new Promise(res => setTimeout(res, 400));
  expect(document.activeElement).toBe(phoneField);
  expect(phoneField.value).toBe('1234567890');
});
