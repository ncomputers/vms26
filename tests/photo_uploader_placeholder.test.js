/**
 * @jest-environment jsdom
 */

const fs = require('fs');
const path = require('path');

async function loadPhotoUploader() {
  let code = fs.readFileSync(path.resolve(__dirname, '../static/js/photo_uploader.js'), 'utf8');
  code = code.replace(/^export\s+/gm, '');
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  return await new AsyncFunction(code + '; return { PhotoUploader };')();
}

test('PhotoUploader toggles placeholder class', async () => {
  const { PhotoUploader } = await loadPhotoUploader();
  document.body.innerHTML = `
    <div id="photoBox" class="photo-placeholder">
      <video id="vid" class="d-none"></video>
      <img id="img" class="d-none" />
      <div class="photo-actions">
        <button id="capture"></button>
        <button id="uploadBtn"></button>
      </div>
    </div>
    <div id="afterControls" class="d-none">
      <button id="retake"></button>
      <button id="changePhoto"></button>
    </div>
  `;
  const uploader = new PhotoUploader({
    videoEl: document.getElementById('vid'),
    previewEl: document.getElementById('img'),
    captureBtn: document.getElementById('capture'),
    uploadBtn: document.getElementById('uploadBtn'),
    startBtn: document.createElement('button'),
    stopBtn: document.createElement('button'),
    resetBtn: document.getElementById('retake'),
    changeBtn: document.getElementById('changePhoto'),
    onCapture: jest.fn(),
  });

  uploader.showPreview('data:image/png;base64,test');
  expect(document.getElementById('photoBox').classList.contains('photo-placeholder')).toBe(false);

  uploader.showVideo();
  expect(document.getElementById('photoBox').classList.contains('photo-placeholder')).toBe(true);
});

test('brightness slider adjusts video filter', async () => {
  const { PhotoUploader } = await loadPhotoUploader();
  document.body.innerHTML = `
    <video id="v"></video>
    <img id="i" />
    <input id="b" type="range" />
  `;
  const uploader = new PhotoUploader({
    videoEl: document.getElementById('v'),
    previewEl: document.getElementById('i'),
    captureBtn: document.createElement('button'),
    uploadBtn: document.createElement('button'),
    uploadInput: document.createElement('input'),
    brightnessInput: document.getElementById('b'),
    onCapture: jest.fn(),
  });
  document.getElementById('b').value = '1.5';
  uploader.updateBrightness();
  expect(document.getElementById('v').style.filter).toBe('brightness(1.5)');
});

test('reset restores slider and clears filter', async () => {
  const { PhotoUploader } = await loadPhotoUploader();
  document.body.innerHTML = `
    <video id="v"></video>
    <img id="i" />
    <input id="b" type="range" data-default="1" />
  `;
  const uploader = new PhotoUploader({
    videoEl: document.getElementById('v'),
    previewEl: document.getElementById('i'),
    captureBtn: document.createElement('button'),
    uploadBtn: document.createElement('button'),
    uploadInput: document.createElement('input'),
    brightnessInput: document.getElementById('b'),
    startBtn: document.createElement('button'),
    onCapture: jest.fn(),
  });
  const slider = document.getElementById('b');
  slider.value = '1.8';
  uploader.updateBrightness();
  uploader.reset();
  expect(slider.value).toBe('1');
  expect(document.getElementById('v').style.filter).toBe('');
});

test('cropper rotate button', async () => {
  const { PhotoUploader } = await loadPhotoUploader();
  document.body.innerHTML = '';
  const uploader = new PhotoUploader({
    previewEl: document.createElement('img'),
    captureBtn: document.createElement('button'),
    uploadBtn: document.createElement('button'),
    onCapture: jest.fn(),
  });
  global.bootstrap = { Modal: class { constructor() {} show() {} hide() {} } };
  uploader.buildCropper();
  uploader.modelsLoaded = true;
  const rotate = jest.fn();
  global.Cropper = function (img, opts) {
    setTimeout(opts.ready, 0);
    this.rotate = rotate;
    this.getCroppedCanvas = () => document.createElement('canvas');
  };
  uploader.openCropper('foo');
  uploader.cropImg.onload();
  const rotBtn = uploader.cropModal.querySelector('#pcRotate');
  rotBtn.click();
  expect(rotate).toHaveBeenCalledWith(90);
});
