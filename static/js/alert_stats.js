(() => {
  const key='alertStats';
  const ctrl=window.eventControllers.get('alertStats');
  async function loadStats() {
    try {
      const r = await fetch('/api/stats');
      if (!r.ok) return;
      const d = await r.json();
      const gc = d.group_counts || {};
      update('metric_person_in', gc.person && gc.person.in);
      update('metric_person_out', gc.person && gc.person.out);
      update('metric_vehicle_in', gc.vehicle && gc.vehicle.in);
      update('metric_vehicle_out', gc.vehicle && gc.vehicle.out);
      update('metric_vehicle_detected', gc.vehicle && gc.vehicle.in);
    } catch (e) {
      console.error('Failed to load alert stats', e);
    }
  }
  function update(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val != null ? val : 0;
  }
  document.getElementById('toggleMetrics')?.addEventListener('click', () => {
    const box = document.getElementById('miniMetrics');
    if(!box) return;
    box.classList.toggle('d-none');
    if (!box.classList.contains('d-none')) {
      loadStats();
      window.pageScheduler.set(key, loadStats, 5000);
    } else {
      window.pageScheduler.clear(key);
    }
  },{signal:ctrl.signal});
})();
