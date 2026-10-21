/* Add a visual cue only while a horizontal navigation row can scroll. */
(function () {
  'use strict';
  function update(row) {
    var canScroll = row.scrollWidth > row.clientWidth + 1;
    row.classList.toggle('is-overflowing', canScroll);
    row.classList.toggle('overflow-left', canScroll && row.scrollLeft > 1);
    row.classList.toggle('overflow-right', canScroll && row.scrollLeft + row.clientWidth < row.scrollWidth - 1);
  }
  function bind(row) {
    if (row.dataset.overflowBound === 'true') return;
    row.dataset.overflowBound = 'true';
    var refresh = function () { update(row); };
    row.addEventListener('scroll', refresh, { passive: true });
    row.addEventListener('focusin', function () { row.classList.add('overflow-focus'); });
    row.addEventListener('focusout', function () { row.classList.remove('overflow-focus'); });
    window.addEventListener('resize', refresh);
    if (window.ResizeObserver) new ResizeObserver(refresh).observe(row);
    if (window.MutationObserver) new MutationObserver(refresh).observe(row, { childList: true, subtree: true, characterData: true });
    refresh();
  }
  function init() { document.querySelectorAll('.site-nav-links, .home-tabs').forEach(bind); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
}());
