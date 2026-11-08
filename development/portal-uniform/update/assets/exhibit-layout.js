// Matching section preferences apply across exhibits on this browser.
(() => {
  const sections = [...document.querySelectorAll('details[data-section]')];
  const storageKey = d => 'zoco-exhibit-section-v1:' + d.dataset.section;
  for (const d of sections) {
    try { const saved = localStorage.getItem(storageKey(d)); if (saved !== null) d.open = saved === 'open'; } catch {}
    d.addEventListener('toggle', () => { try { localStorage.setItem(storageKey(d), d.open ? 'open' : 'closed'); } catch {} });
  }
  const reveal = () => { const d = document.getElementById(location.hash.slice(1)); if (d instanceof HTMLDetailsElement && d.dataset.section) d.open = true; };
  addEventListener('hashchange', reveal);
  document.addEventListener('click', event => {
    const a = event.target.closest('.exhibit-jump a');
    if (a) { const d = document.getElementById(a.hash.slice(1)); if (d) d.open = true; }
  });
  reveal();
})();
