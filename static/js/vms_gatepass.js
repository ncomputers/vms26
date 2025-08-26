document.addEventListener('DOMContentLoaded', function () {
  function qs(id) { return document.getElementById(id); }
  const fields = ['full_name', 'host_name', 'visit_date', 'purpose'];
  function updatePreview() {
    qs('gp-name').textContent = qs('full_name').value;
    qs('gp-host').textContent = qs('host_name').value;
    qs('gp-date').textContent = qs('visit_date').value;
    qs('gp-purpose').textContent = qs('purpose').value;
  }
  fields.forEach(f => qs(f).addEventListener('input', updatePreview));
  updatePreview();

  let stream;
  qs('btn-capture').addEventListener('click', async () => {
    if (!stream) {
      stream = await navigator.mediaDevices.getUserMedia({ video: true }).catch(() => null);
      if (!stream) return;
      const video = document.createElement('video');
      video.autoplay = true;
      video.srcObject = stream;
      document.body.appendChild(video);
      const snap = document.createElement('button');
      snap.textContent = 'Snap';
      document.body.appendChild(snap);
      snap.addEventListener('click', () => {
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        qs('gp-photo').src = canvas.toDataURL('image/png');
        stream.getTracks().forEach(t => t.stop());
        video.remove();
        snap.remove();
      }, { once: true });
    }
  });
});
