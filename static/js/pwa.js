(function() {
  if ('serviceWorker' in navigator) {
    const swUrl = window.location.hostname === 'localhost' ? '/sw-dev.js' : '/service-worker.js';
    navigator.serviceWorker.register(swUrl).then(reg => {
      function promptUpdate(registration) {
        if (confirm('New version available. Update?')) {
          registration.waiting.postMessage({ type: 'SKIP_WAITING' });
        }
      }
      if (reg.waiting) {
        promptUpdate(reg);
      }
      reg.addEventListener('updatefound', () => {
        const newWorker = reg.installing;
        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
            promptUpdate(reg);
          }
        });
      });
    });
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      window.location.reload();
    });
  }

  let deferredPrompt;
  const btn = document.getElementById('a2hs-button');
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    btn.classList.remove('d-none');
  });
  btn && btn.addEventListener('click', async () => {
    btn.classList.add('d-none');
    if (deferredPrompt) {
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
    }
  });

  const notifyBtn = document.getElementById('enable-notifications');
  if ('Notification' in window && Notification.permission === 'default') {
    notifyBtn.classList.remove('d-none');
  }
  notifyBtn && notifyBtn.addEventListener('click', async () => {
    const perm = await Notification.requestPermission();
    if (perm === 'granted') {
      const reg = await navigator.serviceWorker.ready;
      reg.showNotification('Notifications enabled');
    }
    notifyBtn.classList.add('d-none');
  });
})();
