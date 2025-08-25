/**
 * @jest-environment jsdom
 */

test('approval badge shows with valid approver email', async () => {
  const ids = [
    ['form', 'gateForm'], ['div', 'toast'], ['div', 'toastMsg'],
    ['input', 'inviteId'], ['input', 'vName'], ['datalist', 'vNameList'],
    ['input', 'vPhone'], ['input', 'vEmail'], ['select', 'vType'],
    ['input', 'vPurpose'], ['input', 'vCompany'], ['input', 'vValid'],
    ['input', 'hName'], ['input', 'hDept'], ['input', 'needApproval'],
    ['div', 'approverBox'], ['input', 'approverEmail'],
    ['img', 'prevPhoto'],
    ['span', 'pName'], ['span', 'pPhone'], ['span', 'pEmail'],
    ['span', 'pType'], ['span', 'pCompany'], ['span', 'pHost'],
    ['span', 'pDept'], ['span', 'pPurpose'], ['span', 'pGate'],
    ['span', 'pValid'], ['span', 'pStatus'],
    ['div', 'qrBox'],
    ['button', 'printBtn'], ['button', 'pdfBtn'], ['button', 'viewBtn'],
    ['button', 'copyLinkBtn'], ['button', 'copyPassLinkBtn'], ['button', 'newBtn'],
    ['button', 'confirmBtn'], ['button', 'saveBtn'],
    ['img', 'mPhoto'], ['span', 'mName'], ['span', 'mPhone'],
    ['span', 'mHost'], ['span', 'mPurpose'], ['span', 'mValid'],
    ['input', 'uploadPhoto'], ['input', 'captured'], ['button', 'toHost'],
    ['div', 'photoSource'], ['input', 'srcUpload'], ['input', 'srcCamera'],
    ['div', 'uploadControls', 'upload-controls'], ['div', 'cameraControls', 'camera-controls'],
    ['video', 'cam'], ['div', 'cropContainer'], ['img', 'cropImg'],
    ['button', 'captureBtn'], ['button', 'startCam'], ['button', 'stopCam'], ['button', 'useImage'],
    ['div', 'confirmModal'], ['input', 'pondInput'], ['div', 'visitor-tab'],
    ['button', 'toPhoto'], ['button', 'backVisitor'], ['button', 'backPhoto'],
    ['button', 'toReview'], ['button', 'backHost'],
    ['div', 'photo-tab'], ['div', 'host-tab'], ['div', 'review-tab'],
    ['div', 'approvalBadge']
  ];

  document.body.innerHTML = ids
    .map(([tag, id, cls]) => `<${tag} id="${id}"${cls ? ` class="${cls}"` : ''}></${tag}>`)
    .join('');
  document.getElementById('approvalBadge').innerHTML = '<span></span><div id="pApproverEmail"></div>';

  const form = document.getElementById('gateForm');
  form.dataset.defaultHost = '';

  global.intlTelInput = jest.fn(() => ({
    setNumber: jest.fn(),
    getNumber: jest.fn(),
    isValidNumber: () => true
  }));
  global.flatpickr = jest.fn(() => ({ setDate: jest.fn(), set: jest.fn() }));
  global.FilePond = { registerPlugin: jest.fn(), create: jest.fn() };
  global.FilePondPluginImagePreview = {};
  global.FilePondPluginFileEncode = {};
  const showTab = jest.fn();
  global.bootstrap = {
    Toast: { getOrCreateInstance: () => ({ show: jest.fn() }) },
    Tab: { getOrCreateInstance: () => ({ show: showTab }) },
    Modal: function () { return { show: jest.fn(), hide: jest.fn() }; }
  };
  global.initPhotoUploader = jest.fn(() => ({ uploader: {}, ready: Promise.resolve() }));
  global.validateEmail = () => true;
  global.showFieldError = jest.fn();
  global.clearFieldError = jest.fn();

  const fs = require('fs');
  const path = require('path');
  let code = fs.readFileSync(path.resolve(__dirname, '../static/js/gatepass_form.js'), 'utf8');
  code = code.replace(/^import[\s\S]*?;\n/gm, '');
  code = code.replace(
    /export\s+async\s+function initGatepassForm/,
    'window.initGatepassForm = async function initGatepassForm'
  );
  new Function(code)();
  await initGatepassForm();

  const approverEmail = document.getElementById('approverEmail');
  const needApproval = document.getElementById('needApproval');
  const approvalBadge = document.getElementById('approvalBadge');
  const pApproverEmail = document.getElementById('pApproverEmail');

  approverEmail.value = 'a@example.com';
  approverEmail.dispatchEvent(new Event('input'));
  needApproval.checked = true;
  needApproval.dispatchEvent(new Event('change'));

  expect(approvalBadge.classList.contains('d-none')).toBe(false);
  expect(pApproverEmail.textContent).toBe('a@example.com');
});
