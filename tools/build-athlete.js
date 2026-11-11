// Baut athlete.html aus tools/athlete.src.html und den gemeinsamen Funktionen aus index.html.
// Aufruf: node tools/build-athlete.js   (nach jeder Änderung an index.html oder athlete.src.html)
const fs = require('fs'), path = require('path'), acorn = require('acorn');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const style = html.slice(html.indexOf('<style>') + 7, html.indexOf('</style>'));
const js = html.slice(html.indexOf('<script>') + 8, html.lastIndexOf('</script>'));

// Gemeinsame Bausteine (Rechnen, Workout-Modell, API, Diagramme). Reihenfolge wie in index.html.
const NAMES = new Set(['$', '$$', 'esc', 'LS', 'status', 'iv', 'pool', 'pad', 'ymd', 'parseYmd', 'addDays', 'monday', 'MON', 'dShort', 'dLong',
  'RELEASE_HOUR', 'horizon', 'hiddenFor', 'fmtDur', 'fmtH', 'fmtPace', 'parseTime', 'km', 'n0', 'n2', 'vo2', 'pctMax', 'vdotOf', 'predict', 'speedAt', 'DISTS',
  'SPORTS', 'sportOf', 'EX_RE', 'TMODES', 'secOf', 'mmss', 'perOf', 'rng', 'stepText', 'LINE_RE', 'parseStep', 'workoutText', 'workoutDescription',
  'parseWorkout', 'thrFor', 'zoneBounds', 'HRZ_F', 'factor', 'flatten', 'totals', 'hrFracOf', 'powerModel', 'predictTSS', 'stepTargetText',
  'sportSettings', 'events', 'activities', 'hasWatts', 'cachedPower', 'ensurePower', 'metrics', 'initials', 'openDialog', 'closeDialog',
  'isRace', 'raceInfo', 'downsample', 'chart', 'matchPlan', 'compliance', 'compColor', 'compPill', 'stepRange', 'compareSteps',
  'planVsActualHtml', 'formTxt', 'FEEL', 'feedbackPills', 'loadMessages',
  'DATA_FOLDER', 'parseJson', 'VAPID_PUB', 'isIOS', 'isStandalone', 'b64u', 'pushReg', 'pushState', 'pushSave', 'pushEnable', 'pushDisable', 'mountPushCard',
  'economy', 'n1', 'ECO', 'ecoRuns', 'ecoKpis', 'ecoCards', 'powerCurveHtml']);

const ast = acorn.parse(js, { ecmaVersion: 'latest', sourceType: 'script', allowAwaitOutsideFunction: true });
const out = [], found = new Set();
for (const node of ast.body) {
  let names = [];
  if (node.type === 'FunctionDeclaration') names = [node.id.name];
  else if (node.type === 'VariableDeclaration') names = node.declarations.map(d => d.id.name).filter(Boolean);
  if (names.length && names.every(n => NAMES.has(n))) { out.push(js.slice(node.start, node.end)); names.forEach(n => found.add(n)); }
}
const missing = [...NAMES].filter(n => !found.has(n));
if (missing.length) { console.error('Fehlt in index.html:', missing.join(', ')); process.exit(1); }

let shared = out.join('\n')
  .replace("localStorage.getItem('coach.' + k)", "localStorage.getItem('athlete.' + k)")
  .replace("localStorage.setItem('coach.' + k, JSON.stringify(v))", "localStorage.setItem('athlete.' + k, JSON.stringify(v))")
  .replace("localStorage.removeItem('coach.' + k)", "localStorage.removeItem('athlete.' + k)")
  .replace('Kommentar an den Athleten …', 'Nachricht an deinen Coach …');
if (shared.includes("'coach.'")) { console.error('LS-Präfix nicht ersetzt'); process.exit(1); }

const src = fs.readFileSync(path.join(__dirname, 'athlete.src.html'), 'utf8');
fs.writeFileSync(path.join(root, 'athlete.html'), src.replace('/*SHARED_STYLE*/', () => style).replace('/*SHARED_JS*/', () => shared));
console.log('athlete.html gebaut,', found.size, 'gemeinsame Bausteine');
