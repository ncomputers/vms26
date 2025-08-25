import { validateEmail, showFieldError, clearFieldError } from './validation.js';

const form = document.getElementById('pubForm');
const nameField = document.getElementById('name');
const phoneField = document.getElementById('phone');
const emailField = document.getElementById('email');
const typeField = document.getElementById('visitor_type');
const companyField = document.getElementById('company');
const purposeField = document.getElementById('purpose');
const hostField = document.getElementById('host');
const visitField = document.getElementById('visit_time');
const fileInput = document.getElementById('photo');
const preview = document.getElementById('photoPreview');
const noPhoto = document.getElementById('noPhoto');
const reasonBlock = document.getElementById('noPhotoReasonBlock');
const reasonInput = document.getElementById('noPhotoReason');
const msgBox = document.getElementById('msg');
const submitBtn = form.querySelector('button[type="submit"]');

const phoneInput = intlTelInput(phoneField, {
  initialCountry: 'in',
  utilsScript: 'https://cdn.jsdelivr.net/npm/intl-tel-input@18.1.1/build/js/utils.js'
});
flatpickr('#visit_time', { enableTime: true });

[fileInput, nameField, phoneField, emailField, typeField, companyField, purposeField, hostField, visitField].forEach(el => {
  el.addEventListener('input', () => clearFieldError(el));
});

fileInput.addEventListener('change', () => {
  const f = fileInput.files[0];
  if (f) {
    preview.src = URL.createObjectURL(f);
    preview.classList.remove('d-none');
  } else {
    preview.src = '';
    preview.classList.add('d-none');
  }
});

noPhoto.addEventListener('change', () => {
  if (noPhoto.checked) {
    fileInput.disabled = true;
    fileInput.value = '';
    preview.src = '';
    preview.classList.add('d-none');
    reasonBlock.classList.remove('d-none');
  } else {
    fileInput.disabled = false;
    reasonBlock.classList.add('d-none');
    reasonInput.value = '';
  }
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  msgBox.innerHTML = '';
  let valid = true;
  if (!nameField.value.trim()) { showFieldError(nameField, 'Name is required'); valid = false; }
  if (!phoneInput.isValidNumber()) { showFieldError(phoneField, 'Invalid phone number'); valid = false; }
  if (emailField.value && !validateEmail(emailField.value)) { showFieldError(emailField, 'Invalid email address'); valid = false; }
  if (!typeField.value.trim()) { showFieldError(typeField, 'Visitor type is required'); valid = false; }
  if (!hostField.value.trim()) { showFieldError(hostField, 'Host is required'); valid = false; }
  if (!visitField.value.trim()) { showFieldError(visitField, 'Visit time is required'); valid = false; }
  if (!companyField.value.trim()) { showFieldError(companyField, 'Company is required'); valid = false; }
  const purposeVal = purposeField.value.trim();
  if (!purposeVal) { showFieldError(purposeField, 'Purpose is required'); valid = false; }
  if (!noPhoto.checked && fileInput.files.length === 0) { msgBox.innerHTML = '<div class="alert alert-danger">Photo is required</div>'; valid = false; }
  if (!valid) return;

  submitBtn.disabled = true;
  const data = new FormData(form);
  try {
    const r = await fetch('/invite/submit', { method: 'POST', body: data });
    const d = await r.json().catch(() => ({}));
    if (r.ok && d.ok && d.redirect) {
      window.location.href = d.redirect;
    } else if (d.errors) {
      Object.entries(d.errors).forEach(([field, message]) => {
        const input = form.querySelector(`[name="${field}"]`);
        if (input) {
          showFieldError(input, message);
        } else {
          msgBox.innerHTML = `<div class="alert alert-danger">${message}</div>`;
        }
      });
      submitBtn.disabled = false;
    } else {
      msgBox.innerHTML = '<div class="alert alert-danger">Error</div>';
      submitBtn.disabled = false;
    }
  } catch (err) {
    msgBox.innerHTML = '<div class="alert alert-danger">Network error</div>';
    submitBtn.disabled = false;
  }
});
