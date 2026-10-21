/* Interactive, public-only battery cutaway.  The SVG template is trusted static markup;
 * all dataset/catalog text is inserted with textContent. */
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.BatteryExplorer = api;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function () {
  'use strict';

  const IDS = ['cathode', 'anode', 'electrolyte', 'separator', 'interface', 'collectors'];
  const ID_SET = new Set(IDS);
  const TOP_KEYS = ['schema_version', 'as_of', 'note', 'sources', 'components'];
  const COMPONENT_KEYS = ['id', 'label', 'label_en', 'description', 'scope', 'papers'];
  const PAPER_KEYS = ['paper_id', 'doi', 'relation', 'reason'];
  const SOURCE_KEYS = ['label', 'url'];
  const SOURCE_HOSTS = new Set(['energy.gov', 'www.energy.gov', 'anl.gov', 'www.anl.gov', 'publications.anl.gov']);
  const NOTICE = '该图是结构示意，不按比例绘制；以石墨/液态电解液为例，不代表所有电池架构。';
  const PLAIN = '—';

  function exact(value, keys) {
    return !!value && typeof value === 'object' && !Array.isArray(value) &&
      Object.keys(value).length === keys.length && keys.every(k => Object.prototype.hasOwnProperty.call(value, k));
  }
  function text(value, limit) { return typeof value === 'string' && !!value.trim() && value.length <= (limit || 4000); }
  function fail(errors, message) { errors.push(message); return false; }
  function validUrl(value) {
    try {
      const u = new URL(value);
      return u.protocol === 'https:' && SOURCE_HOSTS.has(u.hostname.toLowerCase()) &&
        (u.port === '' || u.port === '443') && !u.username && !u.password && !u.search && !u.hash;
    } catch (_) { return false; }
  }

  /* Pure validation and lookup. It never substitutes a nearby paper for a stale reference. */
  function resolve(data, papers) {
    const errors = [];
    if (!exact(data, TOP_KEYS) || data.schema_version !== 1 || !/^\d{4}-\d{2}-\d{2}$/.test(data.as_of || '') || !text(data.note)) {
      fail(errors, 'battery component map has unknown or missing fields');
    }
    if (!Array.isArray(papers)) fail(errors, 'canonical paper catalog is unavailable');
    const catalog = new Map();
    if (Array.isArray(papers)) papers.forEach(paper => {
      if (!paper || typeof paper.id !== 'string' || !paper.id.trim() || catalog.has(paper.id)) fail(errors, 'canonical catalog contains an invalid or duplicate paper ID');
      else catalog.set(paper.id, paper);
    });
    if (!Array.isArray(data && data.sources) || !data.sources.length) fail(errors, 'figure needs a structural source');
    (Array.isArray(data && data.sources) ? data.sources : []).forEach(source => {
      if (!exact(source, SOURCE_KEYS) || !text(source.label, 300) || !text(source.url, 1000) || !validUrl(source.url)) fail(errors, 'figure source must be an allowed public HTTPS URL');
    });
    if (!Array.isArray(data && data.components) || data.components.length !== IDS.length) fail(errors, 'expected six battery component groups');
    const seen = new Set();
    const components = [];
    (Array.isArray(data && data.components) ? data.components : []).forEach(component => {
      let okay = exact(component, COMPONENT_KEYS) && text(component.id, 100) && ID_SET.has(component.id) && !seen.has(component.id) &&
        text(component.label, 300) && text(component.label_en, 300) && text(component.description) && text(component.scope) && Array.isArray(component.papers);
      if (!okay) { fail(errors, 'component has unknown fields, duplicate ID, or missing content'); return; }
      seen.add(component.id);
      const refs = [];
      const refIds = new Set();
      component.papers.forEach(ref => {
        const canonical = ref && typeof ref.paper_id === 'string' ? catalog.get(ref.paper_id) : null;
        const validRef = exact(ref, PAPER_KEYS) && text(ref.paper_id, 300) && text(ref.doi, 500) &&
          !!canonical && canonical.doi === ref.doi && (ref.relation === 'direct' || ref.relation === 'related') && text(ref.reason);
        if (!validRef || refIds.has(ref.paper_id)) { fail(errors, 'component citation is unknown, stale, or duplicated'); return; }
        refIds.add(ref.paper_id);
        refs.push({ ...ref, paper: canonical });
      });
      components.push({ ...component, papers: refs });
    });
    if (seen.size !== IDS.length) fail(errors, 'component map is missing one or more required IDs');
    if (errors.length) return { ok: false, errors, components: [], data: null, catalog: new Map() };
    return { ok: true, errors: [], components, data, catalog };
  }

  const SVG = `<svg class="battery-explorer__svg" viewBox="0 0 1000 680" role="img" aria-labelledby="battery-svg-title battery-svg-desc" xmlns="http://www.w3.org/2000/svg">
    <title id="battery-svg-title">圆柱锂离子电池：金属外壳、正负端子与内部卷芯的局部剖开示意</title>
    <desc id="battery-svg-desc">中央为带正负端子的圆柱电芯；前部剖开露出放大的电极、隔膜、集流体与孔隙电解液。图上六个编号圆点可选读相应论文；内部层次与厚度不是生产尺寸。</desc>
    <defs>
      <linearGradient id="be-shell" x1="0" x2="1"><stop stop-color="#183e32"/><stop offset=".2" stop-color="#57816a"/><stop offset=".48" stop-color="#35654d"/><stop offset=".82" stop-color="#1c4837"/><stop offset="1" stop-color="#112c24"/></linearGradient>
      <linearGradient id="be-metal" x1="0" x2="1"><stop stop-color="#6c7c7c"/><stop offset=".2" stop-color="#b6c5c1"/><stop offset=".46" stop-color="#f2f4ee"/><stop offset=".7" stop-color="#c0ccc5"/><stop offset="1" stop-color="#637675"/></linearGradient>
      <linearGradient id="be-al" x1="0" x2="1"><stop stop-color="#7d969c"/><stop offset=".4" stop-color="#ebf2f0"/><stop offset="1" stop-color="#809a9c"/></linearGradient>
      <linearGradient id="be-cu" x1="0" x2="1"><stop stop-color="#995d39"/><stop offset=".4" stop-color="#efb582"/><stop offset="1" stop-color="#8c4f32"/></linearGradient>
      <linearGradient id="be-positive" x1="0" x2="1"><stop stop-color="#ba683b"/><stop offset=".5" stop-color="#e5b078"/><stop offset="1" stop-color="#c87b4b"/></linearGradient>
      <linearGradient id="be-negative" x1="0" x2="1"><stop stop-color="#334940"/><stop offset=".5" stop-color="#607a65"/><stop offset="1" stop-color="#344d42"/></linearGradient>
      <radialGradient id="be-ground"><stop stop-color="#254735" stop-opacity=".2"/><stop offset="1" stop-color="#254735" stop-opacity="0"/></radialGradient>
      <pattern id="be-separator" width="8" height="12" patternUnits="userSpaceOnUse"><circle cx="3" cy="4" r="1.6" fill="#83b6b7"/><circle cx="7" cy="10" r="1.4" fill="#a3c8c5"/></pattern>
      <pattern id="be-particles" width="32" height="43" patternUnits="userSpaceOnUse"><circle cx="10" cy="15" r="6" fill="#9c4e31"/><circle cx="27" cy="34" r="4" fill="#f3c787"/><path d="M4 30l6-4 5 4" fill="none" stroke="#75573d" stroke-width="1.4"/></pattern>
      <pattern id="be-graphite" width="50" height="17" patternUnits="userSpaceOnUse"><path d="M0 11l13-6 13 5 14-6 10 4" fill="none" stroke="#b4c1a8" stroke-width="2"/><path d="M3 15l14-5 13 5 15-6" fill="none" stroke="#253e32" stroke-width="2"/></pattern>
    </defs>
    <ellipse cx="510" cy="620" rx="214" ry="27" fill="url(#be-ground)"/>
    <g class="be-can" aria-hidden="true">
      <path d="M350 110 C350 80 670 80 670 110 V563 C670 609 350 609 350 563Z" fill="url(#be-shell)" stroke="#264837" stroke-width="2"/>
      <ellipse cx="510" cy="563" rx="160" ry="43" fill="url(#be-metal)" stroke="#526e60" stroke-width="2"/>
      <ellipse cx="510" cy="563" rx="140" ry="29" fill="#8b9e8e"/>
      <path d="M354 110 C374 151 642 151 666 110 V556 C638 594 378 594 354 556Z" fill="url(#be-shell)"/>
      <path d="M363 133V540" stroke="#92ad94" stroke-width="4" opacity=".32"/>
      <path d="M655 132V545" stroke="#101f18" stroke-width="5" opacity=".3"/>
      <ellipse cx="510" cy="110" rx="160" ry="43" fill="url(#be-metal)" stroke="#526e60" stroke-width="2"/>
      <ellipse cx="510" cy="108" rx="141" ry="31" fill="#a8b9a9" stroke="#e3ebe1" stroke-width="2"/>
      <ellipse cx="510" cy="107" rx="100" ry="23" fill="#7e9b81"/>
      <ellipse cx="510" cy="103" rx="57" ry="15" fill="#2f4d3b"/>
      <path d="M469 69V91 C469 111 551 111 551 91V69Z" fill="url(#be-metal)" stroke="#6e8077" stroke-width="1.5"/>
      <ellipse cx="510" cy="69" rx="41" ry="12" fill="#e8eee4" stroke="#7b8c7f" stroke-width="1.5"/>
      <text x="582" y="71" class="be-terminal-label">+</text>
      <text x="684" y="579" class="be-terminal-label">−</text>
      <path d="M385 174 Q510 135 635 174V514 Q510 555 385 514Z" fill="#1c3429" stroke="#abc1ac" stroke-width="5"/>
      <path d="M383 174Q384 170 390 169V512" fill="none" stroke="#f0f0df" stroke-width="3" opacity=".72"/>
      <text x="510" y="585" text-anchor="middle" class="be-can-label">Li-ion</text>
    </g>
    <g class="be-layer" data-component="collectors" aria-label="铝与铜集流体">
      <path d="M396 173L411 168V510L396 515Z" fill="url(#be-al)" stroke="#607c7c" stroke-width="1.5"/>
      <path d="M600 169L615 175V515L600 509Z" fill="url(#be-cu)" stroke="#905633" stroke-width="1.5"/>
      <path d="M401 180V502M607 181V503" stroke="#fff5d7" opacity=".5" stroke-width="2"/>
    </g>
    <g class="be-layer" data-component="cathode" aria-label="正极复合活性层">
      <path d="M412 169Q443 156 476 165V510Q446 526 412 510Z" fill="url(#be-positive)" stroke="#a46a3a" stroke-width="1.5"/>
      <path d="M418 181Q443 169 470 177V498Q444 514 418 500Z" fill="url(#be-particles)" opacity=".93"/>
      <g class="be-fluid-traces" fill="#7fc5c1"><circle cx="425" cy="204" r="3"/><circle cx="462" cy="248" r="3"/><circle cx="433" cy="341" r="3"/><circle cx="467" cy="416" r="3"/><circle cx="436" cy="477" r="3"/></g>
    </g>
    <g class="be-layer be-interface--cathode" data-component="interface" aria-label="正极界面反应区域">
      <path d="M477 166L483 167V509L477 511Z" fill="#e7c76b" stroke="#b49949"/>
      <path d="M480 183V494" stroke="#fff4b0" stroke-width="2" stroke-dasharray="5 8"/>
    </g>
    <g class="be-layer" data-component="electrolyte" aria-label="电解液及孔隙离子通道">
      <path d="M484 168L497 167V512L484 510Z" fill="#8eced1" opacity=".94" stroke="#568f99"/>
      <path d="M489 180V498" stroke="#e3ffff" stroke-width="2" stroke-dasharray="4 9"/>
      <g fill="#e3ffff" stroke="#4c9ba4" stroke-width="1"><circle cx="490" cy="218" r="4"/><circle cx="491" cy="291" r="4"/><circle cx="489" cy="374" r="4"/><circle cx="492" cy="456" r="4"/></g>
    </g>
    <g class="be-layer" data-component="separator" aria-label="多孔隔膜">
      <path d="M499 166Q506 162 513 168V514Q506 518 499 513Z" fill="#f4efdc" stroke="#bcb390" stroke-width="1.5"/>
      <path d="M501 177H511V503H501Z" fill="url(#be-separator)"/>
    </g>
    <g class="be-layer be-interface--anode" data-component="interface" aria-label="负极SEI反应区域">
      <path d="M516 168L522 166V511L516 514Z" fill="#dfbc63" stroke="#a58c47"/>
      <path d="M519 180V501" stroke="#fff2a0" stroke-width="2" stroke-dasharray="4 7"/>
    </g>
    <g class="be-layer" data-component="anode" aria-label="石墨负极活性层">
      <path d="M525 166Q563 156 598 168V509Q562 526 525 512Z" fill="url(#be-negative)" stroke="#254d35" stroke-width="1.5"/>
      <path d="M532 179Q563 168 591 179V497Q563 512 532 501Z" fill="url(#be-graphite)" opacity=".92"/>
      <g class="be-fluid-traces" fill="#7fc5c1"><circle cx="544" cy="194" r="3"/><circle cx="582" cy="264" r="3"/><circle cx="539" cy="336" r="3"/><circle cx="577" cy="413" r="3"/><circle cx="548" cy="490" r="3"/></g>
    </g>
    <g class="be-roll-top" aria-hidden="true">
      <ellipse cx="505" cy="165" rx="110" ry="23" fill="#d4bd90" stroke="#8e937a"/>
      <ellipse cx="505" cy="165" rx="100" ry="19" fill="none" stroke="#8a5940" stroke-width="2"/>
      <ellipse cx="505" cy="165" rx="86" ry="16" fill="none" stroke="#e8dfc6" stroke-width="3"/>
      <ellipse cx="505" cy="165" rx="74" ry="13" fill="none" stroke="#496750" stroke-width="3"/>
      <ellipse cx="505" cy="165" rx="60" ry="10" fill="none" stroke="#c98c5e" stroke-width="3"/>
      <ellipse cx="505" cy="165" rx="46" ry="8" fill="none" stroke="#e7e4cb" stroke-width="3"/>
      <ellipse cx="505" cy="165" rx="33" ry="6" fill="#5c715b" stroke="#a87956" stroke-width="3"/>
    </g>
    <g class="be-annotation" aria-hidden="true">
      <g fill="none" stroke="#9eafa2" stroke-width="1.5"><path d="M245 281H404"/><path d="M618 352H772"/><path d="M245 439H477"/><path d="M524 198H772"/><path d="M536 503H772"/><path d="M248 185L365 185L393 220"/></g>
      <text x="245" y="269" text-anchor="end">正极活性材料</text><text x="778" y="342">石墨负极</text>
      <text x="245" y="427" text-anchor="end">孔隙中的电解液</text><text x="778" y="187">多孔隔膜</text>
      <text x="778" y="493">SEI / CEI 界面区域</text><text x="245" y="173" text-anchor="end">铝 / 铜集流体</text>
      <text x="510" y="643" text-anchor="middle" class="be-scale-note">圆柱电芯局部剖开 · 内部材料层放大显示，非实际厚度比例</text>
    </g>
  </svg>`;

  function make(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }
  function paperTitle(paper, titleZh) {
    const zh = typeof titleZh === 'function' ? titleZh(paper) : '';
    const title = make('div', 'battery-explorer__paper-title', paper.title || paper.id || PLAIN);
    if (typeof zh === 'string' && zh.trim() && zh.trim() !== (paper.title || '').trim()) title.appendChild(make('div', 'battery-explorer__paper-title-zh', zh));
    return title;
  }
  function displayMeta(paper) {
    return [paper.year, paper.journal, paper.doi].filter(v => v !== undefined && v !== null && String(v).trim()).join(' · ') || PLAIN;
  }
  function mount(element, options) {
    const opts = options || {};
    if (!element || typeof element.appendChild !== 'function') return function () {};
    let current = resolve(opts.data, opts.papers);
    let selected = null;
    let destroyed = false;
    const listeners = [];
    const paperListeners = [];
    function on(node, event, handler, bucket = listeners) { node.addEventListener(event, handler); bucket.push(() => node.removeEventListener(event, handler)); }
    function render() {
      if (destroyed) return;
      listeners.splice(0).forEach(fn => fn());
      paperListeners.splice(0).forEach(fn => fn());
      while (element.firstChild) element.removeChild(element.firstChild);
      const shell = make('div', 'battery-explorer');
      shell.setAttribute('data-state', current.ok ? 'ready' : 'invalid');
      const heading = make('div', 'battery-explorer__heading');
      heading.appendChild(make('div', 'battery-explorer__eyebrow', '结构示意'));
      heading.appendChild(make('h2', '', typeof opts.heading === 'string' && opts.heading.trim() ? opts.heading : '锂离子电池剖面图'));
      heading.appendChild(make('p', 'battery-explorer__notice', current.ok ? NOTICE : '组件资料暂不可用：引用已安全停止显示，请检查公开数据与文献目录。'));
      if (current.ok && current.data.note) {
        const note = make('details', 'battery-explorer__dataset-note');
        note.appendChild(make('summary', '', '数据说明'));
        note.appendChild(make('p', '', current.data.note));
        heading.appendChild(note);
      }
      shell.appendChild(heading);
      if (!current.ok) {
        const error = make('p', 'battery-explorer__error', current.errors.join('；'));
        shell.appendChild(error); element.appendChild(shell); return;
      }
      const layout = make('div', 'battery-explorer__layout');
      const figure = make('div', 'battery-explorer__figure');
      const canvas = make('div', 'battery-explorer__canvas');
      const svgWrap = make('div', 'battery-explorer__svg-wrap'); svgWrap.innerHTML = SVG;
      canvas.appendChild(svgWrap); figure.appendChild(canvas);
      const pins = make('div', 'battery-explorer__pins');
      const pinPositions = { cathode: ['44.5%', '41.2%'], electrolyte: ['49%', '64.7%'], separator: ['50.6%', '30.9%'], interface: ['51.9%', '73.5%'], anode: ['56.2%', '51.5%'], collectors: ['60.7%', '35.3%'] };
      current.components.forEach((component, index) => {
        const pin = make('button', 'battery-explorer__pin'); pin.type = 'button'; pin.dataset.component = component.id; pin.style.left = pinPositions[component.id][0]; pin.style.top = pinPositions[component.id][1]; pin.setAttribute('aria-label', component.label + '：' + component.label_en); pin.setAttribute('aria-pressed', component.id === selected ? 'true' : 'false');
        pin.appendChild(make('span', 'battery-explorer__pin-number', String(index + 1))); pin.appendChild(make('span', 'battery-explorer__pin-tooltip', component.label));
        on(pin, 'click', () => select(component.id));
        on(pin, 'mouseenter', () => svgWrap.querySelector('.battery-explorer__svg').classList.add('is-hovering-' + component.id));
        on(pin, 'mouseleave', () => svgWrap.querySelector('.battery-explorer__svg').classList.remove('is-hovering-' + component.id));
        on(pin, 'focus', () => svgWrap.querySelector('.battery-explorer__svg').classList.add('is-hovering-' + component.id));
        on(pin, 'blur', () => svgWrap.querySelector('.battery-explorer__svg').classList.remove('is-hovering-' + component.id));
        pins.appendChild(pin);
      });
      svgWrap.appendChild(pins);
      const controls = make('div', 'battery-explorer__controls');
      controls.appendChild(make('div', 'battery-explorer__controls-label', '鼠标移到圆点可放大部位；点击圆点后，下方才会出现论文。窄屏可横向滑动示意图。'));
      current.components.forEach((component, index) => {
        const item = make('span', 'battery-explorer__legend-item');
        item.appendChild(make('span', 'battery-explorer__hotspot-label', `${index + 1} ${component.label}`));
        item.appendChild(make('span', 'battery-explorer__hotspot-en', component.label_en));
        controls.appendChild(item);
      });
      figure.appendChild(controls); layout.appendChild(figure);
      const panel = make('section', 'battery-explorer__panel');
      panel.setAttribute('aria-label', '所选部位相关论文'); panel.setAttribute('aria-live', 'polite');
      function renderPanel() {
        paperListeners.splice(0).forEach(fn => fn());
        while (panel.firstChild) panel.removeChild(panel.firstChild);
        panel.hidden = !selected;
        if (!selected) return;
        const chosen = current.components.find(c => c.id === selected);
        const close = make('button', 'battery-explorer__close-list', '收起论文列表'); close.type = 'button';
        on(close, 'click', () => {
          const previous = selected; select(null);
          pins.querySelector('[data-component="' + previous + '"]')?.focus?.();
        }, paperListeners);
        panel.appendChild(close);
        panel.appendChild(make('div', 'battery-explorer__panel-kicker', chosen.label_en));
        panel.appendChild(make('h3', '', `${chosen.label} · ${chosen.papers.length} 篇选读`));
        panel.appendChild(make('p', 'battery-explorer__description', chosen.description));
        panel.appendChild(make('p', 'battery-explorer__scope', chosen.scope));
        const list = make('div', 'battery-explorer__papers');
        if (!chosen.papers.length) list.appendChild(make('p', 'battery-explorer__empty', '当前类别没有已核验的专门引用；不以相邻类别文献代替。'));
        chosen.papers.forEach(ref => {
          const paper = ref.paper; const card = make('div', 'battery-explorer__paper');
          const open = make('button', 'battery-explorer__paper-open'); open.type = 'button'; open.appendChild(paperTitle(paper, opts.titleZh));
          on(open, 'click', () => { if (typeof opts.onOpen === 'function') opts.onOpen(ref.paper_id); }, paperListeners);
          card.appendChild(open);
          card.appendChild(make('div', 'battery-explorer__paper-meta', displayMeta(paper)));
          card.appendChild(make('div', 'battery-explorer__paper-relation', ref.relation === 'direct' ? '主题直接相关' : '相关背景'));
          card.appendChild(make('p', 'battery-explorer__paper-reason', ref.reason)); list.appendChild(card);
        });
        panel.appendChild(list);
      }
      renderPanel(); layout.appendChild(panel); shell.appendChild(layout);
      const sourceLine = make('div', 'battery-explorer__sources'); sourceLine.appendChild(make('span', '', '结构来源：'));
      const sourceList = make('ul', '');
      current.data.sources.forEach(source => { const li = make('li', ''); const a = make('a', '', source.label); a.href = source.url; a.target = '_blank'; a.rel = 'noopener noreferrer'; li.appendChild(a); sourceList.appendChild(li); });
      sourceLine.appendChild(sourceList);
      shell.appendChild(sourceLine); element.appendChild(shell);
      function centerNarrowFigure() {
        if (canvas.scrollWidth > canvas.clientWidth) canvas.scrollLeft = (canvas.scrollWidth - canvas.clientWidth) / 2;
      }
      centerNarrowFigure();
      if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') on(window, 'resize', centerNarrowFigure);
      const svg = shell.querySelector('.battery-explorer__svg');
      if (selected) svg.classList.add('is-selected-' + selected);
      function select(id) {
        if (destroyed || selected === id) return;
        selected = id;
        current.components.forEach(component => svg.classList.toggle('is-selected-' + component.id, component.id === id));
        [pins, controls].forEach(group => group.querySelectorAll('[data-component]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.component === id))));
        renderPanel();
      }
      current.components.forEach(component => { const group = svg.querySelector('[data-component="' + component.id + '"]'); if (group) group.setAttribute('aria-label', component.label); });
    }
    render();
    return { cleanup: function () { destroyed = true; listeners.splice(0).forEach(fn => fn()); paperListeners.splice(0).forEach(fn => fn()); while (element.firstChild) element.removeChild(element.firstChild); }, update: function (next) { current = resolve(next && next.data, next && next.papers); selected = null; render(); } };
  }
  return { resolve, mount, componentIds: IDS.slice() };
});
