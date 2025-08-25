const video = document.getElementById('webcam');
const canvas = document.getElementById('snapshot');
const captureBtn = document.getElementById('captureBtn');
const retakeBtn = document.getElementById('retakeBtn');
const fileInput = document.getElementById('photo');
const capturedInput = document.getElementById('captured');
let stream;

async function startCamera() {
  if (!video) return;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = stream;
    video.classList.remove('d-none');
  } catch (err) {
    document.getElementById('cameraControls')?.classList.add('d-none');
    video?.classList.add('d-none');
    fileInput?.classList.remove('d-none');
  }
}

function stopCamera() {
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
}

captureBtn?.addEventListener('click', () => {
  if (!video || !canvas) return;
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0);
  canvas.classList.remove('d-none');
  video.classList.add('d-none');
  captureBtn.classList.add('d-none');
  retakeBtn.classList.remove('d-none');
  fileInput.classList.add('d-none');
  canvas.toBlob((blob) => {
    if (!blob) return;
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result;
      if (typeof result === 'string') {
        capturedInput.value = result.split(',')[1];
      }
    };
    reader.readAsDataURL(blob);
  }, 'image/png');
});

retakeBtn?.addEventListener('click', () => {
  canvas.classList.add('d-none');
  video.classList.remove('d-none');
  captureBtn.classList.remove('d-none');
  retakeBtn.classList.add('d-none');
  fileInput.classList.remove('d-none');
  capturedInput.value = '';
});

window.addEventListener('beforeunload', stopCamera);
startCamera();
