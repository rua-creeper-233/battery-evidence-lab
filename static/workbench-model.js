/* Read-only data model for the Paper Workbench.
 * It deliberately does not alter the catalog records.  The browser UI can use
 * WorkbenchModel.create({ papers, tags, titles, components, domestic, insights }).
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.WorkbenchModel = factory();
})(typeof window !== 'undefined' ? window : globalThis, function () {
  const METHODS = ['DFT', 'AIMD', 'NEB', 'MD', 'MLIP'];
  const SOFTWARE = ['MS', 'VASP', 'LAMMPS', 'GROMACS', 'CP2K', 'CASTEP', 'ABINIT', 'Quantum ESPRESSO', 'ORCA', 'VASPKIT', 'DMol3', 'COMSOL', 'PACKMOL'];
  const COMPONENTS = ['cathode', 'anode', 'electrolyte', 'separator', 'interface', 'collectors'];
  const text = value => value == null ? '' : Array.isArray(value) ? value.map(text).join(' ') : typeof value === 'object' ? Object.values(value).map(text).join(' ') : String(value);
  const list = value => Array.isArray(value) ? value : value == null ? [] : [value];
  const unique = values => [...new Set(values.filter(value => value !== '' && value != null))];
  const normalizeId = p => p && (p.id || p.paper_id);

  function safeLink(value) {
    if (typeof value !== 'string' || !value.trim()) return null;
    const raw = value.trim();
    if (raw.includes('\\') || raw.startsWith('//')) return null;
    if (raw.startsWith('/') || raw.startsWith('./') || raw.startsWith('../') || raw.startsWith('#')) return raw;
    try {
      const url = new URL(raw);
      if (url.protocol !== 'https:') return null;
      if (/[?&](?:token|access_token|api[_-]?key|key|password|passwd|secret|signature|sig)=/i.test(url.search)) return null;
      if (url.username || url.password) return null;
      return url.href;
    } catch (_) { return null; }
  }

  function recordFor(source, id) {
    if (!source) return null;
    if (Array.isArray(source)) return source.find(x => normalizeId(x) === id || x.paper_id === id) || null;
    return source[id] || source.papers?.[id] || source.entries?.find(x => normalizeId(x) === id) || null;
  }

  function domesticInfo(domestic, id, paper) {
    const entry = recordFor(domestic, id) || (Array.isArray(domestic?.entries) && domestic.entries.find(x => x.paper_id === id || x.id === id));
    const authors = list(paper.authors).concat(list(paper.affiliations));
    // Institution names alone are not evidence of region.  Accept only a
    // structured region/country annotation supplied by the record/curator.
    const affiliation = authors.some(a => a && typeof a === 'object' && /^(?:中国(?:内地|大陆)?|mainland china|cn|china)$/i.test(text(a.region || a.country).trim()));
    const explicit = text(paper.region || paper.region_annotation || paper.region_note).toLowerCase();
    const international = /国际|international|国外|overseas|foreign/.test(explicit);
    const domesticPositive = !!entry || affiliation || /国内|中国内地|中国大陆|domestic|mainland china/.test(explicit);
    if (domesticPositive) return { value: 'domestic', label: '国内团队', reason: entry ? 'domestic registry' : affiliation ? 'supported affiliation annotation' : 'explicit region annotation' };
    if (international) return { value: 'international', label: '国际', reason: 'explicit region annotation' };
    return { value: 'unknown', label: '未知地区', reason: 'no supported domestic or international affiliation/annotation' };
  }

  function methodSoftware(paper, tagRecord) {
    // Reading and replication suggestions may name a package the paper did not use.
    const curated = list(tagRecord?.method_tags).concat(list(paper.method_tags));
    const fields = [paper.methods, paper.method, paper.methodology, paper.software, paper.protocol, paper.protocol_steps, paper.computational_method, paper.computational_details];
    const methodText = text(fields).toLowerCase();
    const implementation = [paper.methods, paper.method, paper.software].flatMap(list);
    const explicitSoftware = list(paper.software_tags).map(name => text(name).toLowerCase());
    const tags = unique(curated.map(x => String(x).trim()));
    const methods = METHODS.filter(kind => tags.includes(kind) ||
      (kind === 'DFT' && /\b(?:dft|density functional|first-principles|ab initio)\b/i.test(methodText)) ||
      (kind === 'AIMD' && /\b(?:aimd|ab initio molecular dynamics)\b/i.test(methodText)) ||
      (kind === 'NEB' && /\bneb\b|nudged elastic band/i.test(methodText)) ||
      (kind === 'MD' && /molecular dynamics|\b(?:md|mlmd)\b/i.test(methodText)) ||
      (kind === 'MLIP' && /\b(?:mlip|machine[- ]learning potential|nequip|m3gnet|chgnet|deepmd)\b/i.test(methodText)));
    const software = SOFTWARE.filter(name => {
      if (explicitSoftware.includes(name.toLowerCase())) return true;
      if (name === 'MS') {
        const explicit = implementation.some(x => /^\s*(?:MS|Materials Studio(?: \d{4})?)\s*$/i.test(text(x)) || /(?:used|using|with|via|performed in|calculated in)\s+Materials Studio/i.test(text(x)));
        return explicit && !/(?:not|without|instead of|no)\s+(?:using\s+)?(?:MS|Materials Studio)/i.test(text(implementation));
      }
      const pattern = name === 'Quantum ESPRESSO' ? '(?:quantum\\s+espresso|qe)' : name;
      const mentions = new RegExp(`(?:^|[^a-z])${pattern}(?:$|[^a-z])`, 'i');
      const excluded = /(?:not|without|instead of|no)\s+(?:using\s+)?/i;
      return implementation.some(value => mentions.test(text(value)) && !excluded.test(text(value)));
    });
    return { methods, software };
  }

  function componentsOf(paper, registry) {
    const explicit = list(paper.component || paper.components || paper.battery_component).map(String).map(x => x.toLowerCase());
    const direct = explicit.map(value => /^(?:solid|liquid) electrolyte$/.test(value) ? 'electrolyte' : value).filter(value => COMPONENTS.includes(value));
    return unique([...direct, ...registry.filter(item => list(item.papers).some(x => (x.paper_id || x.id) === normalizeId(paper))).map(item => item.id)]);
  }

  function validMetrics(card) {
    return list(card?.metrics).filter(metric => {
      if (!metric || typeof metric !== 'object') return false;
      const meaningful = value => typeof value === 'number' ? Number.isFinite(value) : typeof value === 'string' && value.trim().length > 0;
      return meaningful(metric.label) && meaningful(metric.value) && meaningful(metric.source) && meaningful(metric.locator);
    }).map(metric => ({ label: String(metric.label).trim(), value: metric.value, ...(metric.unit != null ? { unit: String(metric.unit) } : {}), ...(metric.conditions != null ? { conditions: metric.conditions } : {}), ...(metric.comparison != null ? { comparison: metric.comparison } : {}), source: String(metric.source).trim(), locator: String(metric.locator).trim() }));
  }

  function create(options = {}) {
    const inputPapers = list(options.papers);
    const tagSource = options.tags || {};
    const titleSource = options.titles || {};
    const insightSource = options.insights || {};
    const componentSource = Array.isArray(options.components) ? options.components : options.components?.components || [];
    const registry = componentSource.filter(x => x && x.id);
    const normalized = inputPapers.map(original => {
      const id = normalizeId(original);
      const tagRecord = recordFor(tagSource, id) || {};
      const titleRecord = recordFor(titleSource, id) || {};
      const insight = recordFor(insightSource, id) || {};
      const region = domesticInfo(options.domestic, id, original);
      const ms = methodSoftware(original, tagRecord);
      const paperTypes = unique([tagRecord.paper_kind || original.paper_kind, ...list(tagRecord.display_tags).filter(tag => tag === '综述' || tag === '观点')]);
      if (!paperTypes.length && original.document_type) paperTypes.push(original.document_type);
      const component_ids = componentsOf(original, registry);
      const component = component_ids[0] || null;
      const tags = unique(list(tagRecord.display_tags).concat(list(original.display_tags), list(tagRecord.tags), list(original.tags_zh)));
      const links = unique([original.url, original.doi ? `https://doi.org/${original.doi}` : '', ...list(original.resources).map(x => x && x.url), ...list(original.links).map(x => typeof x === 'string' ? x : x?.url)]).map(safeLink).filter(Boolean);
      return { ...original, id, title_zh: original.title_zh || titleRecord.title_zh || titleRecord.title || '', display_tags: tags, methods_normalized: ms.methods, software_normalized: ms.software, component, component_ids, region: region.value, region_label: region.label, region_reason: region.reason, paper_type: paperTypes[0], paper_types: paperTypes, links, insight };
    }).filter(p => p.id);
    const byId = new Map(normalized.map(p => [p.id, p]));
    const facet = (values, labels = {}) => unique(values).map(value => ({ value, label: labels[value] || value, count: normalized.filter(p => valuesFor(p, value)).length }));
    const facets = {
      components: facet(normalized.flatMap(p => p.component_ids).filter(Boolean)),
      methods: facet(METHODS), software: facet(SOFTWARE),
      types: facet(normalized.flatMap(p => p.paper_types)),
      years: facet(normalized.map(p => p.year).filter(Boolean).sort((a, b) => b - a).map(String)),
      regions: facet(['domestic', 'international', 'unknown'], { domestic: '国内团队', international: '国际', unknown: '未知地区' })
    };
    function valuesFor(p, value) { return p.component_ids.includes(value) || p.methods_normalized.includes(value) || p.software_normalized.includes(value) || p.paper_types.includes(value) || String(p.year) === String(value) || p.region === value; }
    function query(state = {}) {
      const q = state.q ?? state.query ?? '';
      const clean = String(q).trim().toLowerCase();
      const selected = key => unique(list(state[key] ?? state[`${key}s`])).map(String);
      const components = selected('component'), methods = selected('method'), software = selected('software'), types = selected('type'), regions = selected('region');
      const agent = options.searchAgent || (typeof globalThis !== 'undefined' && globalThis.BatteryBrowserAgent);
      let rows;
      let expandedTerms = unique(list(state.expandedTerms || state.expanded_terms));
      if (agent && typeof agent.searchDetailed === 'function' && clean) {
        const retrieval = agent.searchDetailed(String(q), normalized, normalized.length, options.searchConfig || {});
        rows = retrieval.results;
        expandedTerms = unique(expandedTerms.concat(retrieval.query?.expanded_terms || []));
      } else {
        rows = normalized.slice();
        if (clean) rows = rows.filter(p => text([p.title, p.title_zh, p.summary, p.role, p.systems, p.properties, p.display_tags]).toLowerCase().includes(clean));
      }
      rows = rows.filter(p => (!components.length || components.some(x => p.component_ids.includes(x))) && (!methods.length || methods.every(x => p.methods_normalized.includes(x))) && (!software.length || software.every(x => p.software_normalized.includes(x))) && (!types.length || types.some(x => p.paper_types.includes(x))) && (!regions.length || regions.includes(p.region)) && (!state.year || String(p.year) === String(state.year)));
      const sort = state.sort || (clean ? 'relevance' : 'year-desc');
      if (!(clean && sort === 'relevance' && rows.some(p => p.retrieval))) rows.sort((a, b) => {
        if (sort === 'year-asc' || sort === 'oldest') return (a.year || 0) - (b.year || 0);
        if (sort === 'title') return String(a.title || '').localeCompare(String(b.title || ''));
        return (b.year || 0) - (a.year || 0);
      });
      return { rows, expandedTerms, state: { ...state, q } };
    }
    function card(id) {
      const p = byId.get(id);
      if (!p) return null;
      const insight = p.insight?.sections || {};
      const metrics = validMetrics(p.evidence_card);
      const sections = {
        header: {title:p.title, title_zh:p.title_zh, authors:p.authors || [], journal:p.journal, year:p.year, doi:p.doi, links:p.links},
        tldr: {summary:p.summary || '', metrics},
        material: {systems:p.systems || [], component:p.component},
        protocol: {methods:p.methods_normalized, software:p.software_normalized, steps:p.protocol_steps || []},
        observables: {metrics},
        evidence: {evidence:p.evidence || [], insight},
        limitations: {scope_note:p.scope_note || '', limits:insight.limits || []},
        related: {relations:p.relations || [], resources:p.links},
      };
      return { id: p.id, paper: p, sections };
    }
    return { papers: normalized, byId, facets, query, card, safeLink };
  }
  return { create, safeLink };
});
