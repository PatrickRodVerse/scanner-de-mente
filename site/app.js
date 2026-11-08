const names = { original: 'John and Mary', reverse: 'Reverse direction', names: 'Alice and Bob', template: 'Sarah and David' };
const signed = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2, signDisplay: 'exceptZero' });
const percent = new Intl.NumberFormat('en-US', { style: 'percent', maximumFractionDigits: 1 });
const scoreKeys = ['clean', 'corrupt', 'restore', 'clamp_last', 'clamp_adjacent', 'restore_clamp_last', 'restore_clamp_adjacent'];
const controls = { restore: 'corrupt', restore_clamp_last: 'clamp_last', restore_clamp_adjacent: 'clamp_adjacent' };
const svgNamespace = 'http://www.w3.org/2000/svg';

export function summarizeCase(studyCase) {
  const { scores } = studyCase;
  const restore = scores.restore - scores.corrupt;
  const fixed = scores.restore_clamp_last - scores.clamp_last;
  return { restore, fixed, drop: restore > 0 ? 1 - fixed / restore : null };
}

function requireStudy(study) {
  if (!study || !Array.isArray(study.cases) || study.cases.length !== Object.keys(names).length ||
      !Array.isArray(study.scan?.patches) || study.scan.patches.length !== 24 ||
      !study.cases.every((item) => item && Object.hasOwn(names, item.id) &&
        scoreKeys.every((key) => Number.isFinite(item.scores?.[key]))) ||
      new Set(study.cases.map((item) => item.id)).size !== study.cases.length) {
    throw new Error('Study measurements are unavailable or incomplete.');
  }
  const original = study.cases.find((item) => item.id === 'original');
  for (const position of [original.edited_position, original.last_position]) {
    const series = study.scan.patches.filter((point) => point.position === position);
    if (series.length !== 12 || !Array.from({ length: 12 }, (_, layer) =>
      series.some((point) => point.layer === layer && Number.isFinite(point.recovery))).every(Boolean)) {
      throw new Error('The scan is incomplete.');
    }
  }
  return study;
}

function showPrompt(element, text, speaker) {
  const index = text.lastIndexOf(` ${speaker} `);
  if (index < 0) {
    element.textContent = text;
    return;
  }
  const mark = document.createElement('mark');
  mark.textContent = speaker;
  element.replaceChildren(text.slice(0, index + 1), mark, text.slice(index + 1 + speaker.length));
}

function drawChart(study, svg, width) {
  if (width < 100) return;
  const original = study.cases.find((item) => item.id === 'original');
  const x = (layer) => 44 + layer / 11 * (width - 58);
  const y = (value) => 174 - value * 152;
  svg.setAttribute('viewBox', `0 0 ${width} 215`);
  svg.replaceChildren();

  function add(tag, attrs, label = '') {
    const element = document.createElementNS(svgNamespace, tag);
    for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
    element.textContent = label;
    svg.append(element);
    return element;
  }

  add('title', { id: 'scan-title' }, 'Recovery of the score gap after each block');
  add('desc', { id: 'scan-description' }, 'Patching the changed name has a larger effect through block 7. From block 8 on, patching the final token has a larger effect. Each point is a separate intervention.');
  for (const tick of [0, .25, .5, .75, 1]) {
    add('line', { x1: 44, x2: width - 14, y1: y(tick), y2: y(tick), class: 'grid-line' });
    add('text', { x: 36, y: y(tick) + 4, 'text-anchor': 'end', class: 'plot-text' }, percent.format(tick));
  }
  for (const layer of (width < 360 ? [0, 3, 6, 8, 11] : [0, 2, 4, 6, 8, 10, 11])) {
    add('text', { x: x(layer), y: 192, 'text-anchor': 'middle', class: 'plot-text' }, String(layer));
  }
  add('text', { x: (44 + width - 14) / 2, y: 213, 'text-anchor': 'middle', class: 'plot-text' }, 'Patch after block');

  for (const [position, className] of [[original.edited_position, 'name-series'], [original.last_position, 'last-series']]) {
    const points = study.scan.patches.filter((point) => point.position === position).sort((a, b) => a.layer - b.layer);
    add('polyline', { class: `plot-series ${className}`, points: points.map((point) => `${x(point.layer)},${y(point.recovery)}`).join(' ') });
    for (const point of points) {
      add('circle', { cx: x(point.layer), cy: y(point.recovery), r: 3.3, class: `plot-point ${className}` });
    }
  }
}

function connectStudy(study) {
  const byId = (id) => document.getElementById(id);
  const put = (id, value) => { byId(id).textContent = value; };
  const picker = byId('case');
  const workbench = byId('workbench');
  const chart = byId('chart');
  const scoreLimit = Math.ceil(Math.max(...study.cases.flatMap((item) => Object.values(item.scores).map(Math.abs))));
  const descriptions = {
    corrupt: 'The changed prompt gives us a baseline for the patch. The bar shows the difference in scores between the two names.',
    restore: `We copy the reference state of the name after block ${study.source_layer}.`,
    restore_clamp_last: `We restore the name and hold the final token’s state after block ${study.downstream_layer} at its value in the changed prompt.`,
    restore_clamp_adjacent: 'We restore the name and apply the same control to the token just before the last one.',
  };

  function showResult() {
    const item = study.cases.find((entry) => entry.id === picker.value);
    const condition = workbench.querySelector('input[name="condition"]:checked').value;
    const value = item.scores[condition];
    const fill = byId('meter-fill');
    const width = Math.abs(value) / scoreLimit * 50;
    put('favored', value > 0 ? item.target : value < 0 ? item.contrast : 'Tie');
    put('score-label', `${item.target} minus ${item.contrast} (logits)`);
    put('score', signed.format(value));
    put('meter-left', item.contrast);
    put('meter-right', item.target);
    fill.style.width = `${width}%`;
    fill.style.left = `${value < 0 ? 50 - width : 50}%`;
    fill.classList.toggle('negative', value < 0);
    put('condition-note', descriptions[condition]);
    put('effect', condition === 'corrupt' ? '' : `${signed.format(value - item.scores[controls[condition]])} logits compared with the matching control.`);
  }

  function showCase() {
    const item = study.cases.find((entry) => entry.id === picker.value);
    showPrompt(byId('clean-prompt'), item.clean_prompt, item.contrast);
    showPrompt(byId('corrupt-prompt'), item.corrupt_prompt, item.target);
    put('clean-gloss', `${item.contrast} gives the object away. Of the two names, the model favors ${item.target}.`);
    put('corrupt-gloss', `${item.target} gives the object away. Of the two names, the model favors ${item.contrast}.`);
    showResult();
  }

  for (const item of study.cases) {
    const { restore, fixed, drop } = summarizeCase(item);
    const row = byId('evidence-rows').insertRow();
    const label = document.createElement('th');
    label.scope = 'row';
    label.textContent = names[item.id];
    row.append(label);
    for (const value of [signed.format(restore), signed.format(fixed), drop === null ? '—' : percent.format(drop)]) row.insertCell().textContent = value;
  }
  put('revision', `${study.model}@${study.revision}`);
  picker.disabled = false;
  workbench.hidden = false;
  byId('load-status').hidden = true;
  picker.addEventListener('change', showCase);
  workbench.addEventListener('change', showResult);
  showCase();
  new ResizeObserver(() => drawChart(study, byId('scan-chart'), chart.clientWidth)).observe(chart);
}

if (typeof document !== 'undefined') {
  const status = document.getElementById('load-status');
  status.hidden = false;
  fetch(new URL('./ioi.json', import.meta.url))
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then(requireStudy)
    .then(connectStudy)
    .catch(() => {
      status.hidden = false;
      status.textContent = 'Could not load the measurements. Refresh the page or download the JSON in the Method section.';
    });
}
