/* taste-guard fix · behavior only (external；CSP script-src 'self' 允许) */
window.GBT_NAV_DISABLE = true;
document.addEventListener('click', function (e) {
  var b = e.target && e.target.closest ? e.target.closest('#hero-open') : null;
  if (!b) return;
  var v = document.getElementById('view-workbench');
  if (v) { v.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
});
