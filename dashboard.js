const DATA_SOURCE = './results.json';

const MODELS_MAP = {
  meta:    { label: 'llama-3.1-8b-instant',  display: 'LLaMA 3.1 8B' },
  openai:  { label: 'openai/gpt-oss-120b',   display: 'GPT-OSS 120B' },
  alibaba: { label: 'qwen/qwen3-32b',         display: 'Qwen3 32B' }
};

const VARIATIONS = [
  'baseline','concise','verbose','expert','academic',
  'casual','production','no_examples','plain_text','negative_instruction'
];

const PROBLEMS = [
  { id: 'humaneval_000', entry: 'has_close_elements' },
  { id: 'humaneval_001', entry: 'separate_paren_groups' },
  { id: 'humaneval_002', entry: 'truncate_number' },
  { id: 'humaneval_003', entry: 'below_zero' },
  { id: 'humaneval_004', entry: 'mean_absolute_deviation' },
  { id: 'humaneval_005', entry: 'intersperse' },
  { id: 'humaneval_006', entry: 'parse_nested_parens' },
  { id: 'humaneval_007', entry: 'filter_by_substring' },
  { id: 'humaneval_008', entry: 'sum_product' },
  { id: 'humaneval_009', entry: 'rolling_max' }
];

let allResults = {};
let rawResults = null;
let isRunning = false;

function log(msg, type='') {
  const b = document.getElementById('log');
  const line = document.createElement('span');
  if (type) line.className = type;
  line.textContent = msg + '\n';
  b.appendChild(line);
  b.scrollTop = b.scrollHeight;
}

function setP(pct, label) {
  document.getElementById('pf').style.width = pct + '%';
  document.getElementById('pl').textContent = label;
}

function avg(arr) {
  const v = arr.filter(x => x != null);
  return v.length ? v.reduce((a,b)=>a+b,0)/v.length : null;
}

function pct(arr) {
  const a = avg(arr);
  return a != null ? (a * 100).toFixed(0) + '%' : '—';
}

function fmtL(arr) {
  const a = avg(arr);
  return a != null ? a.toFixed(2) + 's' : '—';
}

function fmtS(arr) {
  const a = avg(arr);
  return a != null ? (a * 100).toFixed(0) + '%' : '—';
}

function loadResultsFile() {
  return fetch(DATA_SOURCE)
    .then(resp => {
      if (!resp.ok) throw new Error(`Unable to load ${DATA_SOURCE}: ${resp.statusText}`);
      return resp.json();
    })
    .then(data => {
      rawResults = data;
      return data;
    });
}

function buildAggregates(entries, models) {
  const result = {};
  models.forEach(mk => {
    result[mk] = {};
    VARIATIONS.forEach(v => {
      result[mk][v] = {
        syntax_valid: [],
        passed_tests: [],
        generation_seconds: [],
        structural_similarities: [],
        instruction_compliance: [],
        error_types: []
      };
    });
  });

  entries.forEach(entry => {
    const bucket = result[entry.model]?.[entry.variation_type];
    if (!bucket) return;
    bucket.syntax_valid.push(entry.syntax_valid ? 1 : 0);
    bucket.passed_tests.push(entry.passed_tests ? 1 : 0);
    bucket.generation_seconds.push(entry.generation_seconds);
    bucket.structural_similarities.push(entry.structural_similarity);
    bucket.instruction_compliance.push(entry.instruction_compliance ? 1 : 0);
    bucket.error_types.push(entry.error_type || null);
  });

  return result;
}

async function startEval() {
  if (isRunning) return;
  isRunning = true;
  document.getElementById('runBtn').disabled = true;
  document.getElementById('expBtn').style.display = 'none';
  document.getElementById('progSection').style.display = 'block';
  document.getElementById('summarySection').style.display = 'none';
  document.getElementById('resultsSection').style.display = 'none';
  document.getElementById('log').innerHTML = '';

  const numP = parseInt(document.getElementById('numP').value, 10);
  const numR = parseInt(document.getElementById('numR').value, 10);
  const mdlSel = document.getElementById('mdl').value;
  const models = mdlSel === 'all' ? ['meta','openai','alibaba'] : [mdlSel];
  const selectedProblemIds = PROBLEMS.slice(0, numP).map(p => p.id);

  try {
    setP(5, 'Loading precomputed results...');
    if (!rawResults) {
      await loadResultsFile();
    }
    setP(40, 'Filtering results...');

    const entries = rawResults.entries.filter(e =>
      selectedProblemIds.includes(e.problem_id) &&
      e.run_id < numR &&
      models.includes(e.model)
    );

    allResults = buildAggregates(entries, models);

    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('summarySection').style.display = 'block';
    document.getElementById('resultsSection').style.display = 'block';
    document.getElementById('expBtn').style.display = 'inline-block';
    setP(100, 'Loaded results');
    renderAll(models);
  } catch (err) {
    log(`Failed to load results: ${err.message || err}`, 'err');
    setP(0, 'Load failed');
  } finally {
    isRunning = false;
    document.getElementById('runBtn').disabled = false;
  }
}

function renderAll(models) {
  const sg = document.getElementById('sg');
  sg.innerHTML = '';
  models.forEach(mk => {
    const rows = Object.values(allResults[mk] || {});
    const allSyn = rows.flatMap(r => r.syntax_valid);
    const allPass = rows.flatMap(r => r.passed_tests);
    const allLat = rows.flatMap(r => r.generation_seconds);
    const allSim = rows.flatMap(r => r.structural_similarities);
    sg.innerHTML += `
      <div class="scard"><div class="model-tag">${MODELS_MAP[mk].label}</div><div class="metric-val">${pct(allSyn)}</div><div class="metric-name">syntax success</div></div>
      <div class="scard"><div class="model-tag">${MODELS_MAP[mk].label}</div><div class="metric-val">${pct(allPass)}</div><div class="metric-name">task accuracy</div></div>
      <div class="scard"><div class="model-tag">${MODELS_MAP[mk].label}</div><div class="metric-val">${fmtL(allLat)}</div><div class="metric-name">avg latency</div></div>
      <div class="scard"><div class="model-tag">${MODELS_MAP[mk].label}</div><div class="metric-val">${fmtS(allSim)}</div><div class="metric-name">struct similarity</div></div>`;
  });

  const tabsRow = document.getElementById('tabsRow');
  tabsRow.innerHTML = '';
  models.forEach((mk, i) => {
    const tab = document.createElement('div');
    tab.className = 'tab' + (i === 0 ? ' active' : '');
    tab.textContent = MODELS_MAP[mk].display;
    tab.onclick = () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      renderTable(mk);
    };
    tabsRow.appendChild(tab);
  });
  renderTable(models[0]);
}

function renderTable(mk) {
  const data = allResults[mk];
  if (!data) return;

  let html = `<table>
    <thead><tr>
      <th style="width:140px">Variation</th>
      <th>Syntax Output<br>Success Rate</th>
      <th>Structural<br>Similarity Score</th>
      <th>Generation<br>Latency (avg)</th>
      <th>Task Accuracy /<br>Test Pass Rate</th>
    </tr></thead><tbody>`;

  VARIATIONS.forEach(v => {
    const r = data[v];
    if (!r || !r.syntax_valid.length) {
      html += `<tr><td class="vcol">${v}</td><td colspan="4" style="font-size:11px;color:var(--text3);text-align:center">not run</td></tr>`;
      return;
    }
    const synA  = avg(r.syntax_valid);
    const passA = avg(r.passed_tests);
    const simA  = avg(r.structural_similarities);
    const latA  = avg(r.generation_seconds);

    const synStr  = synA  != null ? (synA*100).toFixed(0) + '%' : '—';
    const passStr = passA != null ? (passA*100).toFixed(0) + '%' : '—';
    const simStr  = simA  != null ? (simA*100).toFixed(0) + '%' : '—';
    const latStr  = latA  != null ? latA.toFixed(2) + 's' : '—';
    const simNum  = simA  != null ? (simA*100).toFixed(0) : 0;

    const synBadge  = synA  >= 0.8 ? 'g' : synA  >= 0.5 ? 'a' : 'r';
    const passBadge = passA >= 0.7 ? 'g' : passA >= 0.4 ? 'a' : 'r';
    const vLabel = v.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());

    html += `<tr>
      <td class="vcol">${vLabel}</td>
      <td><span class="badge ${synBadge}">${synStr}</span></td>
      <td>
        <div class="barwrap">
          <div class="barbg"><div class="barfg" style="width:${simNum}%"></div></div>
          <span class="barval">${simStr}</span>
        </div>
      </td>
      <td><span class="latval">${latStr}</span></td>
      <td><span class="badge ${passBadge}">${passStr}</span></td>
    </tr>`;
  });

  html += `</tbody></table>`;
  const ic = pct(Object.values(data).flatMap(r => r.instruction_compliance));
  const runCount = Object.values(data)[0]?.syntax_valid.length || 0;
  const problems = PROBLEMS.slice(0, parseInt(document.getElementById('numP').value, 10)).length;
  html += `<div class="compliance-row">
    <span><strong>Instruction compliance</strong> (avg across variations): ${ic}</span>
    <span><strong>Model:</strong> ${MODELS_MAP[mk].label}</span>
    <span><strong>Data scope:</strong> ${problems} problems · ${runCount / problems || 0} runs per prompt</span>
  </div>
  <div class="footnote">
    <strong>Metric definitions (mirrors evaluation.py):</strong>
    Syntax: <code>ast.parse()</code> validation ·
    Structural similarity: structural feature overlap vs reference solution ·
    Latency: generation wall-clock seconds ·
    Accuracy: precomputed test pass rate ·
    Green ≥ 80% / 70% · Amber ≥ 50% / 40% · Red below
  </div>`;
  document.getElementById('tbl').innerHTML = html;
}

function doExport() {
  const rows = [];
  Object.keys(allResults).forEach(mk => {
    VARIATIONS.forEach(v => {
      const r = allResults[mk]?.[v];
      if (!r || !r.syntax_valid.length) return;
      rows.push([
        MODELS_MAP[mk].label,
        v.replace(/_/g,' '),
        avg(r.syntax_valid)?.toFixed(4) || '',
        avg(r.structural_similarities)?.toFixed(4) || '',
        avg(r.generation_seconds)?.toFixed(4) || '',
        avg(r.passed_tests)?.toFixed(4) || '',
        avg(r.instruction_compliance)?.toFixed(4) || ''
      ]);
    });
  });
  const csv = ['model,variation_type,syntax_valid,structural_similarity,generation_seconds,passed_tests,instruction_compliance', ...rows.map(r => r.map(v => `"${v}"`).join(','))].join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  a.download = 'cs614_evaluation_results.csv';
  a.click();
}
