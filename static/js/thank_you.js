const params = new URLSearchParams(location.search);
const data = window.INVITE_DATA || {
  visitor_id: params.get('visitor_id'),
  qr: params.get('qr')
};

if (data.visitor_id) {
  document.getElementById('visitorId').textContent = data.visitor_id;
}

if (data.qr) {
  const img = document.getElementById('qrImg');
  img.src = data.qr;
  document.getElementById('downloadBtn').href = data.qr;
  document.getElementById('saveLink').href = data.qr;
}

document.getElementById('printBtn')?.addEventListener('click', () => window.print());
