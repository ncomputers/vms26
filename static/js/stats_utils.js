export function animateMetric(id, val) {
  const el = document.getElementById(id);
  if (!el) return;
  const obj = { val: parseInt(el.textContent) || 0 };
  if (typeof gsap !== 'undefined') {
    gsap.to(obj, { val: val, duration: 0.5, ease: 'power1.out', onUpdate: () => { el.textContent = Math.round(obj.val); } });
    gsap.fromTo(el, { scale: 1 }, { scale: 1.1, duration: 0.3, yoyo: true, repeat: 1, ease: 'power1.out' });
  } else {
    el.textContent = val;
  }
}

export function updateTrend(id, pct) {
  const el = document.getElementById(id + '_trend');
  if (!el) return;
  if (pct === undefined || pct === null) { el.textContent = ''; return; }
  const up = pct >= 0;
  el.innerHTML = `<span class="${up ? 'text-success' : 'text-danger'}"><i class="bi ${up ? 'bi-arrow-up' : 'bi-arrow-down'}"></i> ${Math.abs(pct)}%</span>`;
}
