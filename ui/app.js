const $ = (id) => document.getElementById(id);
const number = (value, places = 3, signed = false) => typeof value === 'number' && Number.isFinite(value)
  ? new Intl.NumberFormat('en-US', { minimumFractionDigits: places, maximumFractionDigits: places, signDisplay: signed ? 'exceptZero' : 'auto' }).format(value)
  : '—';
const percent = (value) => typeof value === 'number' && Number.isFinite(value) ? `${number(value * 100, 1)}%` : '—';
const put = (id, text) => { $(id).textContent = text; };

export function demoResult() {
  const tokens = ['When', ' John', ' and', ' Mary', ' went', ' to', ' the', ' shops', ',', ' John', ' gave', ' the', ' bag', ' to'];
  const clean = 2.4, corrupt = -1.2;
  const patches = [];
  for (let layer = 0; layer < 12; layer++) {
    for (let position = 0; position < tokens.length; position++) {
      let value = .56 * Math.exp(-((layer - 5) ** 2) / 7 - ((position - 9) ** 2) / 1.3)
        + .82 * Math.exp(-((layer - 8.5) ** 2) / 13 - ((position - 13) ** 2) / 2)
        - .11 * Math.exp(-((layer - 4) ** 2) / 5 - ((position - 3) ** 2) / 2);
      if (layer === 11) value = position === tokens.length - 1 ? 1 : 0;
      patches.push({ layer, position, recovery: value, effect: value * (clean - corrupt), patched_score: corrupt + value * (clean - corrupt) });
    }
  }
  return {
    model: 'Synthetic demo', tokens, clean_score: clean, corrupt_score: corrupt,
    denominator: clean - corrupt, target: 'Mary', contrast: 'John', patches,
    clean_prompt: 'When John and Mary went to the shops, John gave the bag to',
    corrupt_prompt: 'When John and Mary went to the shops, Mary gave the bag to',
    activation_norms: Array.from({ length: 12 }, (_, layer) => tokens.map((_, pos) => 12 + layer * 3.6 + Math.sin(pos) * 2)),
    controls: { corrupt_identity_error: 0, clean_identity_error: 0, final_restore_error: 0, final_nonlast_effect: 0 },
    metadata: { synthetic: true },
  };
}

export function patchIndex(result) {
  return new Map(result.patches.map((patch) => [`${patch.layer}:${patch.position}`, patch]));
}

export function colorFor(value, scale) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '#f0f3f3';
  const fraction = Math.min(1, Math.abs(value) / Math.max(scale, 1e-8));
  const base = [237, 242, 242], end = value < 0 ? [168, 111, 63] : [27, 108, 128];
  return `rgb(${base.map((channel, index) => Math.round(channel + (end[index] - channel) * fraction)).join(', ')})`;
}

let state = null, result = null, measured = null, synthetic = false;
let selected = null, index = new Map(), lastResult = '', lastJob = '', failureCount = 0, lastRepositoryJob = null;

function showError(message) {
  $('error-message').hidden = !message;
  put('error-message', message || '');
}

async function api(path, body) {
  const response = await fetch(path, body === undefined ? { cache: 'no-store' } : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.error === 'string' ? data.error : data.message || `HTTP error ${response.status}`);
  return data;
}

function displayResult(value, isDemo = false) {
  result = value;
  synthetic = isDemo;
  index = value ? patchIndex(value) : new Map();
  selected = value ? value.patches.filter((patch) => patch.layer < value.activation_norms.length - 1)
    .sort((a, b) => Math.abs(b.effect) - Math.abs(a.effect))[0] || value.patches[0] || { layer: 0, position: 0 } : null;
  $('demo-notice').hidden = !isDemo;
  $('source-label').classList.toggle('synthetic', isDemo);
  put('source-label', isDemo ? 'Synthetic data' : value ? 'Measured result' : 'No results');
  $('real-result-button').hidden = !isDemo || !measured;
  $('export-link').setAttribute('aria-disabled', String(!measured || isDemo));
  $('empty-map').hidden = !!value;
  $('matrix-scroll').hidden = !value;
  const cleanPrompt = value?.clean_prompt || $('clean-prompt').value;
  const corruptPrompt = value?.corrupt_prompt || $('corrupt-prompt').value;
  put('heatmap-caption', value ? `${value.activation_norms.length} blocks · ${value.tokens.length} tokens · ${value.patches.length} ${isDemo ? 'synthetic ' : ''}interventions` : 'Replace a state from the corrupted run with its clean counterpart.');
  $('heatmap-title').title = value ? `Clean prompt: ${cleanPrompt}\nCorrupted prompt: ${corruptPrompt}` : '';
  put('clean-score', number(value?.clean_score));
  put('corrupt-score', number(value?.corrupt_score));
  put('baseline-label', `logit(${value?.target || $('target').value}) − logit(${value?.contrast || $('contrast').value})`);
  const baselinePassed = value?.metadata?.baseline_task_passed ?? (value?.clean_score > 0 && value?.corrupt_score < 0);
  put('map-footnote', value && !isDemo && !baselinePassed
    ? 'The model did not favor the expected name in both prompts. Treat the results as changes in the logit gap for this pair.'
    : 'Each cell shows a separate intervention on the next token prediction. Gray cells were untested. Indices start at 0.');
  renderMap();
  renderControls();
  updateGraph();
}

function renderMap() {
  const matrix = $('matrix');
  matrix.replaceChildren();
  if (!result) { selectCell(null); put('map-range', 'No measurements'); return; }
  const metric = $('map-metric').value;
  const values = result.patches.map((patch) => patch[metric]).filter((value) => typeof value === 'number' && Number.isFinite(value));
  const scale = Math.max(metric === 'recovery' ? 1 : .01, ...values.map(Math.abs));
  matrix.style.setProperty('--columns', result.tokens.length);
  const addText = (className, text, title = '') => {
    const cell = document.createElement('div'); cell.className = className; cell.textContent = text; cell.title = title; matrix.append(cell);
  };
  addText('matrix-corner', 'Block');
  result.tokens.forEach((token, position) => addText('matrix-token', token.replace(/^ /, '▁'), `Token ${position}: ${JSON.stringify(token)}`));
  for (let layer = 0; layer < result.activation_norms.length; layer++) {
    addText('matrix-label', `L${String(layer).padStart(2, '0')}`);
    result.tokens.forEach((token, position) => {
      const patch = index.get(`${layer}:${position}`);
      const cell = document.createElement('button'); cell.type = 'button';
      cell.className = `matrix-cell${patch ? '' : ' unmeasured'}`;
      cell.dataset.layer = layer; cell.dataset.position = position;
      const value = patch?.[metric];
      cell.style.backgroundColor = colorFor(value, scale);
      const description = `Block ${layer}, token ${position}: ${JSON.stringify(token)}. ${patch ? metric === 'recovery' ? `Recovery ${percent(value)}` : `Change ${number(value, 3, true)} logits` : 'Untested'}`;
      cell.title = description; cell.setAttribute('aria-label', description);
      cell.tabIndex = selected?.layer === layer && selected?.position === position ? 0 : -1;
      cell.classList.toggle('selected', cell.tabIndex === 0);
      cell.addEventListener('click', () => selectCell({ layer, position }));
      cell.addEventListener('keydown', (event) => {
        const directions = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
        if (!(event.key in directions)) return;
        event.preventDefault(); const [dy, dx] = directions[event.key];
        const nextLayer = Math.max(0, Math.min(result.activation_norms.length - 1, layer + dy));
        const nextPosition = Math.max(0, Math.min(result.tokens.length - 1, position + dx));
        selectCell({ layer: nextLayer, position: nextPosition });
        matrix.querySelector(`[data-layer="${nextLayer}"][data-position="${nextPosition}"]`).focus();
      });
      matrix.append(cell);
    });
  }
  addText('matrix-corner', 'Token');
  result.tokens.forEach((_, position) => addText('matrix-position', position));
  const formatRange = (value) => metric === 'recovery' ? percent(value) : number(value, 2);
  put('map-range', values.length ? `${formatRange(Math.min(...values))} to ${formatRange(Math.max(...values))}${metric === 'effect' ? ' logits' : ''}` : 'Recovery unavailable');
  document.querySelector('.map-legend').setAttribute('aria-label', metric === 'recovery' ? 'Diverging recovery scale' : 'Diverging scale for change in the logit gap');
  document.querySelector('.map-legend>span:last-child').textContent = metric === 'recovery' ? 'Higher recovery' : 'Higher effect';
  selectCell(selected);
}

function selectCell(selection) {
  selected = selection;
  const patch = selection ? index.get(`${selection.layer}:${selection.position}`) : null;
  document.querySelectorAll('.matrix-cell').forEach((cell) => {
    const active = !!selection && Number(cell.dataset.layer) === selection.layer && Number(cell.dataset.position) === selection.position;
    cell.classList.toggle('selected', active); cell.tabIndex = active ? 0 : -1;
    cell.setAttribute('aria-pressed', String(active));
  });
  put('selection-id', selection ? `L${String(selection.layer).padStart(2, '0')} / T${selection.position}` : 'L— / T—');
  put('selected-token', selection ? JSON.stringify(result.tokens[selection.position]) : '—');
  const recoveryMode = $('map-metric').value === 'recovery';
  put('selected-effect', recoveryMode ? percent(patch?.recovery) : number(patch?.effect, 3, true));
  put('selected-unit', recoveryMode ? 'recovery' : 'change in logit gap');
  put('selected-logits', number(patch?.effect, 3, true));
  put('selected-score', number(patch?.patched_score));
  put('selected-norm', number(selection ? result.activation_norms[selection.layer][selection.position] : undefined, 2));
  put('selection-note', !selection ? 'Select a cell to inspect its effect.'
    : !patch ? 'The scan skipped this position. The residual norm measures the size of the state.'
      : synthetic ? 'This synthetic value illustrates how to read the map.'
        : selection.layer === result.activation_norms.length - 1 && selection.position === result.tokens.length - 1
          ? 'Restoring the final state checks the patch. Inspect earlier blocks to see where a patch changes the result.'
          : 'The logit gap is measured after replacing the entire state at this position.');
}

function renderControls() {
  const controls = result?.controls;
  const definitions = [['Identity patch', Math.max(controls?.corrupt_identity_error ?? Infinity, controls?.clean_identity_error ?? Infinity)],
    ['Final state restoration', controls?.final_restore_error], ['Structural null control', Math.abs(controls?.final_nonlast_effect ?? Infinity)]];
  const list = $('control-list'); list.replaceChildren();
  for (const [label, error] of definitions) {
    const row = document.createElement('div'), name = document.createElement('span'), status = document.createElement('span');
    name.textContent = label;
    status.textContent = !controls ? '—' : synthetic ? 'Example' : error <= 1e-4 ? 'Passed' : 'Failed or missing';
    status.title = controls && !synthetic ? `Absolute error: ${number(error, 7)}` : '';
    row.append(name, status); list.append(row);
  }
  put('controls-summary', !controls ? 'Waiting for a run' : synthetic ? 'Demo data' : 'Tolerance: 0.0001');
}

function updateGraph() {
  const available = !!measured && !synthetic && !!state?.circuit?.available;
  $('circuit-frame').hidden = !available;
  $('circuit-empty').hidden = available;
  $('open-circuit').hidden = !available;
  if (!available) {
    const graphify = state?.graphify;
    const warning = state?.job?.kind === 'patching' ? state.job.warning : null;
    put('circuit-empty', synthetic ? 'Graphs are available for measured results.'
      : graphify?.available === false ? graphify.message || 'Install Graphify to generate experiment graphs.'
        : warning || (measured ? 'No graph is available for this result. Run the experiment again to generate one.'
          : 'Graphify can generate this graph after a measured run.'));
  }
  if (available && !$('graph-panel').hidden && !$('circuit-frame').hasAttribute('src')) $('circuit-frame').src = '/graphs/circuit';
}

function renderSae(sae) {
  const content = $('sae-content'); content.replaceChildren();
  if (!sae?.metrics) {
    const panel = document.createElement('section'); panel.className = 'panel sae-empty';
    const heading = document.createElement('h2'); heading.textContent = 'No trained SAE yet';
    const description = document.createElement('p'); description.textContent = 'Collect activations from one block across varied prompts, then train an autoencoder. Evaluation metrics and the most activating prefixes will appear here.';
    panel.append(heading, description); content.append(panel); return;
  }
  const stats = document.createElement('div'); stats.className = 'sae-stats';
  const holdout = sae.metrics.holdout || {};
  for (const [label, value] of [['Relative error on held-out data', number(holdout.normalized_mse)], ['Active features per token', number(holdout.mean_l0, 1)], ['Inactive features on held-out data', percent(holdout.dead_fraction)]]) {
    const item = document.createElement('div'), name = document.createElement('span'), amount = document.createElement('strong');
    name.textContent = label; amount.textContent = value; item.append(name, amount); stats.append(item);
  }
  content.append(stats);
  const panel = document.createElement('section'); panel.className = 'panel';
  const title = document.createElement('h2'); title.textContent = `Top activating prefixes · Block ${sae.metrics.layer ?? '—'}`; panel.append(title);
  const table = document.createElement('table'); table.className = 'feature-table';
  const thead = table.createTHead(), header = thead.insertRow();
  ['Feature', 'Activation', 'Observed prefix'].forEach((text) => { const th = document.createElement('th'); th.scope = 'col'; th.textContent = text; header.append(th); });
  const tbody = table.createTBody();
  (sae.features || []).forEach((feature) => { const row = tbody.insertRow(); [`F${feature.feature}`, number(feature.activation), feature.context].forEach((text) => { row.insertCell().textContent = text; }); });
  panel.append(table); content.append(panel);
}

function route() {
  const requested = location.hash.slice(1), view = ['experimento', 'sae', 'repositorio'].includes(requested) ? requested : 'experimento';
  document.querySelectorAll('.view').forEach((section) => { section.hidden = section.id !== `view-${view}`; });
  document.querySelectorAll('.nav-item').forEach((link) => {
    link.classList.toggle('active', link.dataset.view === view);
    if (link.dataset.view === view) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  });
  put('breadcrumb', { experimento: 'Experiment', sae: 'SAE features', repositorio: 'Repository graph' }[view]);
  $('sidebar').classList.remove('open'); $('menu-toggle').setAttribute('aria-expanded', 'false');
  if (view === 'repositorio' && state?.repository?.available && !$('repository-frame').hasAttribute('src')) $('repository-frame').src = '/graphs/repository';
}

function showJob(job) {
  const signature = JSON.stringify(job);
  if (signature === lastJob) return;
  lastJob = signature;
  const statuses = { idle: 'Idle', running: 'Running', success: 'Complete', error: 'Failed' };
  put('job-status', statuses[job?.status] || 'Idle');
  $('job-status').className = `job-status ${job?.status || ''}`;
  const log = (job?.log || []).join('\n');
  put('job-log', log || 'The model loads when you run an experiment.');
  $('job-log').scrollTop = $('job-log').scrollHeight;
  if (job?.status === 'error') showError(job.error || 'The run failed. Check the log before trying again.');
}

async function refresh() {
  try {
    const next = await api('/api/state'); state = next;
    if (failureCount >= 2) showError(null);
    failureCount = 0;
    put('connection-text', 'Local server'); $('connection-dot').style.backgroundColor = 'var(--positive)';
    const memory = next.memory, busy = next.job.status === 'running';
    const canRun = memory.can_run && !busy;
    $('run-button').disabled = !canRun;
    const minimum = number(memory.minimum_gib, 1);
    $('run-button').title = busy ? 'Wait for the current job' : memory.can_run ? 'Run GPT‑2 locally with these prompts' : `Free up memory until ${minimum} GiB are available`;
    const canBuildGraph = next.graphify?.available !== false;
    $('rebuild-button').disabled = busy || !canBuildGraph;
    put('memory-amount', `${number(memory.available_gib, 2)} GiB available`);
    put('sidebar-memory', `${number(memory.available_gib, 2)} of ${number(memory.total_gib, 1)} GiB available`);
    $('memory-banner').classList.toggle('low', !memory.can_run);
    put('memory-message', busy ? 'A local job is running. See the run log for progress.' : memory.can_run ? 'Enough memory to run on your CPU.' : `Free up memory to run the model. At least ${minimum} GiB must be available.`);
    const signature = JSON.stringify(next.result);
    measured = next.result;
    if (signature !== lastResult) {
      lastResult = signature;
      if (!synthetic) displayResult(measured);
      $('real-result-button').hidden = !synthetic || !measured;
      $('circuit-frame').removeAttribute('src'); updateGraph();
    }
    updateGraph();
    const saeSignature = JSON.stringify(next.sae);
    if ($('sae-content').dataset.signature !== saeSignature) { renderSae(next.sae); $('sae-content').dataset.signature = saeSignature; }
    const repositoryAvailable = next.repository.available;
    $('repository-frame').hidden = !repositoryAvailable;
    $('open-repository').hidden = !repositoryAvailable;
    put('repo-counts', repositoryAvailable
      ? `${number(next.repository.nodes, 0)} nodes · ${number(next.repository.edges, 0)} edges${canBuildGraph ? '' : ' · saved graph'}`
      : canBuildGraph ? 'No repository graph yet. Rebuild with Graphify to create one.'
        : next.graphify.message || 'Install Graphify to generate this graph.');
    $('rebuild-button').title = canBuildGraph ? '' : next.graphify.message || 'Graphify is unavailable';
    showJob(next.job);
    if (next.job.kind === 'repository' && next.job.status === 'success' && next.job.id !== lastRepositoryJob) {
      lastRepositoryJob = next.job.id;
      if ($('repository-frame').hasAttribute('src')) $('repository-frame').src = `/graphs/repository?job=${encodeURIComponent(next.job.id)}`;
    }
    if (location.hash === '#repositorio' && next.repository.available && !$('repository-frame').hasAttribute('src')) $('repository-frame').src = '/graphs/repository';
  } catch (error) {
    failureCount++;
    put('connection-text', 'Disconnected'); $('connection-dot').style.backgroundColor = 'var(--negative)';
    $('run-button').disabled = true; $('rebuild-button').disabled = true;
    if (failureCount === 2) showError('The local server did not respond. Check that the lab is running, then reload this page.');
  }
}

async function run() {
  if ($('run-button').disabled) return;
  const clean = $('clean-prompt').value.trim(), corrupt = $('corrupt-prompt').value.trim();
  const target = $('target').value.trim(), contrast = $('contrast').value.trim();
  if (!clean || !corrupt || clean === corrupt) { showError('Enter two different prompts.'); return; }
  if (!target || !contrast || target === contrast) { showError('Enter two different names, one as the target and one as the contrast.'); return; }
  showError(null); $('run-button').disabled = true;
  try {
    await api('/api/run', { clean, corrupt, target, contrast, positions: $('positions').value, threads: Number($('threads').value) });
    displayResult(measured); await refresh();
  } catch (error) { showError(error.message); await refresh(); }
}

function initialize() {
  const emptyMatrix = document.querySelector('.empty-matrix');
  for (let i = 0; i < 168; i++) emptyMatrix.append(document.createElement('i'));
  ['demo-button', 'empty-demo'].forEach((id) => $(id).addEventListener('click', () => displayResult(demoResult(), true)));
  ['close-demo', 'real-result-button'].forEach((id) => $(id).addEventListener('click', () => displayResult(measured)));
  $('map-metric').addEventListener('change', renderMap);
  $('run-button').addEventListener('click', run);
  $('experiment-form').addEventListener('submit', (event) => { event.preventDefault(); run(); });
  $('export-link').addEventListener('click', (event) => { if ($('export-link').getAttribute('aria-disabled') === 'true') event.preventDefault(); });
  document.querySelectorAll('[data-result-tab]').forEach((button) => {
    button.addEventListener('click', () => {
      const map = button.dataset.resultTab === 'map';
      $('map-panel').hidden = !map; $('graph-panel').hidden = map;
      document.querySelectorAll('[data-result-tab]').forEach((tab) => { const active = tab === button; tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1; }); updateGraph();
    });
    button.addEventListener('keydown', (event) => { if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return; event.preventDefault(); const next = button.id === 'map-tab' ? $('graph-tab') : $('map-tab'); next.click(); next.focus(); });
  });
  $('menu-toggle').addEventListener('click', () => { const open = $('sidebar').classList.toggle('open'); $('menu-toggle').setAttribute('aria-expanded', String(open)); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') { $('sidebar').classList.remove('open'); $('menu-toggle').setAttribute('aria-expanded', 'false'); } });
  document.addEventListener('click', (event) => { if (!$('sidebar').contains(event.target) && !$('menu-toggle').contains(event.target)) { $('sidebar').classList.remove('open'); $('menu-toggle').setAttribute('aria-expanded', 'false'); } });
  $('rebuild-button').addEventListener('click', async () => { showError(null); try { await api('/api/repository', {}); $('repository-frame').removeAttribute('src'); await refresh(); } catch (error) { showError(error.message); location.hash = '#experimento'; } });
  ['target', 'contrast'].forEach((id) => $(id).addEventListener('input', () => {
    document.querySelectorAll('.field-title small')[0].textContent = `Expected name: ${$('target').value.trim() || '—'}`;
    document.querySelectorAll('.field-title small')[1].textContent = `Expected name: ${$('contrast').value.trim() || '—'}`;
  }));
  window.addEventListener('hashchange', route);
  document.querySelectorAll('.nav-item').forEach((link) => link.addEventListener('click', () => {
    $('sidebar').classList.remove('open'); $('menu-toggle').setAttribute('aria-expanded', 'false');
  }));
  displayResult(null); route(); refresh();
  setInterval(refresh, 2000);
}

if (typeof document !== 'undefined') initialize();
