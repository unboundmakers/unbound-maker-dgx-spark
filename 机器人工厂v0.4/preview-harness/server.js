// Preview harness: serves the real web UI from the competition repo with a stub API.
// No Spark / Isaac Sim required. Job lifecycle is simulated (~15s for agent mode, ~6s for structured rerun).
const http = require('http');
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { execFile } = require('child_process');
const { promisify } = require('util');
const execFileAsync = promisify(execFile);

const ROOT = __dirname;
const WEB = path.resolve(ROOT, '../builder-web');
const ART = path.join(ROOT, 'artifacts');
const VENV_PY = path.join(ROOT, '.venv/bin/python');
const OLLAMA = process.env.OLLAMA_URL || 'http://127.0.0.1:11434';

const DRAWING_PROMPT = `This is a child's drawing of an imaginary robot creature. Look at it and answer in JSON only, no other text:
{"body": "round|slim|stocky|quad", "ears": "cat|round|long|horn", "wings": "b5|b3|bat|none", "paws": "pad|claw|hoof|mitt", "tail": "long|fluff|stub|none", "color": "<main body color as hex like #F2A65A>", "wing_color": "<accent color of wings/ears as hex>", "creature": "<what animal it looks like, in Chinese>"}
Rules: quad=four legs; b5=many blade feathers, b3=a few blades, bat=membrane wings; pick the closest option; color must be the dominant body color.`;
const ENUMS = {
  body: ['round', 'slim', 'stocky', 'quad'],
  ears: ['cat', 'round', 'long', 'horn'],
  wings: ['b5', 'b3', 'bat', 'none'],
  paws: ['pad', 'claw', 'hoof', 'mitt'],
  tail: ['long', 'fluff', 'stub', 'none'],
};

function parseDrawingCfg(text) {
  const m = String(text || '').match(/\{[^{}]*\}/s);
  if (!m) return null;
  let raw;
  try { raw = JSON.parse(m[0]); } catch { return null; }
  const cfg = {};
  for (const [key, allowed] of Object.entries(ENUMS)) {
    if (allowed.includes(raw[key])) cfg[key] = raw[key];
  }
  const hexRe = /^#[0-9a-f]{6}$/i;
  if (hexRe.test(raw.color || '')) {
    cfg.color = 'custom';
    cfg.customColor = [raw.color.toUpperCase(), hexRe.test(raw.wing_color || '') ? raw.wing_color.toUpperCase() : '#8EA2E8'];
  }
  return Object.keys(cfg).length ? { cfg, creature: String(raw.creature || '') } : null;
}

function readRaw(req, limit = 25 * 1024 * 1024) {
  return new Promise((resolve, reject) => {
    const chunks = []; let size = 0;
    req.on('data', (c) => { size += c.length; if (size > limit) reject(new Error('too large')); else chunks.push(c); });
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

function cliArg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
const port = Number(process.env.PORT || cliArg('--port', cliArg('-p', 7100)));
const host = process.env.HOST || cliArg('--host', '::');

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.json': 'application/json', '.zip': 'application/octet-stream' };
const ARTIFACTS = { ['a'.repeat(32)]: 'preview.png', ['b'.repeat(32)]: 'run-report.json', ['c'.repeat(32)]: 'scene.zip' };
const STAGES = [['asset', 3], ['personality', 3], ['scene', 3], ['optimizer', 2.5], ['runner', 3.5]];

/* v0.3: serve the newest sketch2sim/机器人工厂_vX.Y.html (override with FACTORY_HTML=<path>) */
function factoryHtml() {
  if (process.env.FACTORY_HTML) return path.resolve(process.env.FACTORY_HTML);
  const dir = path.resolve(ROOT, '../sketch2sim');
  const ver = (f) => (f.match(/_v(\d+)\.(\d+)/) || [0, 0, 0]).slice(1).map(Number);
  const files = fs.readdirSync(dir).filter((f) => /^机器人工厂_v\d+\.\d+.*\.html$/.test(f))
    .sort((x, y) => { const a = ver(x), b = ver(y); return a[0] - b[0] || a[1] - b[1]; });
  return path.join(dir, files[files.length - 1]);
}

const hex = () => crypto.randomBytes(16).toString('hex');
const revisions = new Map(); // revision_id -> design
const jobs = new Map();      // job_id -> job record

function jobView(job) {
  const now = Date.now() / 1000;
  const elapsed = now - job.start;
  const speed = job.mode === 'structured' ? 0.4 : 1; // structured rerun is faster
  const events = [];
  let cursor = job.start, current = -1, done = true;
  STAGES.forEach(([stage, secs], i) => {
    const end = cursor + secs * speed;
    if (elapsed >= end - job.start) {
      events.push({ stage, status: 'running', time: cursor }, { stage, status: i === 1 && job.reusedPersonality ? 'reused' : 'passed', time: end });
    } else {
      if (current === -1) { current = i; events.push({ stage, status: 'running', time: cursor }); }
      done = false;
    }
    cursor = end;
  });
  let status;
  if (job.cancelled) status = 'cancelled';
  else if (done) status = 'succeeded';
  else if (elapsed < 1.2) status = 'queued';
  else if (current === STAGES.length - 1) status = 'validating';
  else if (current <= 0) status = 'planning';
  else status = 'building';
  const view = { job_id: job.id, project_id: job.project_id, status, execution_mode: job.mode, events };
  if (status === 'succeeded') {
    view.detail = {
      revision_id: job.revision_id, execution_mode: job.mode, model: 'Qwen3-32B · DGX Spark 本机',
      design: job.design,
      results: {
        runner: {
          artifacts: { 'preview.png': 'a'.repeat(32), 'run-report.json': 'b'.repeat(32) },
          checks: { 资产加载: true, 场景完整性: true, 推力参数生效: true, 边界内运动: true, 无报错退出: true },
          simulated_s: 10,
        },
        optimizer: { artifacts: { 'scene.zip': 'c'.repeat(32) } },
      },
    };
  } else if (status === 'cancelled') {
    view.detail = { message: '任务已被取消，未产生已验证结果。' };
  }
  return view;
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let raw = '';
    req.on('data', (c) => { raw += c; if (raw.length > 65536) reject(new Error('too large')); });
    req.on('end', () => { try { resolve(raw ? JSON.parse(raw) : {}); } catch (e) { reject(e); } });
  });
}
function sendJson(res, code, value) {
  const body = JSON.stringify(value);
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(body);
}
function sendFile(res, file) {
  const body = fs.readFileSync(file);
  res.writeHead(200, { 'Content-Type': (MIME[path.extname(file)] || 'application/octet-stream') + '; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(body);
}

const server = http.createServer(async (req, res) => {
  const url = req.url.split('?')[0];
  if (req.method === 'POST') console.log('POST', url, req.headers['content-type'] || '-', req.headers['content-length'] || '-');
  if (req.method === 'GET' && url === '/factory') {
    let html = fs.readFileSync(factoryHtml(), 'utf-8');
    const bridge = '<script src="/factory-bridge.js"></script>';
    html = html.includes('</body>') ? html.replace('</body>', bridge + '</body>') : html + bridge;
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
    return res.end(html);
  }
  if (req.method === 'GET' && url === '/factory-bridge.js') {
    return sendFile(res, path.join(ROOT, 'factory-bridge.js'));
  }
  const asset = url.match(/^\/preview-assets\/([0-9A-Za-z._-]+)$/);
  if (req.method === 'GET' && asset) {
    const file = path.join(ROOT, asset[1]);
    if (fs.existsSync(file) && fs.statSync(file).isFile()) return sendFile(res, file);
  }
  try {
    if (req.method === 'GET') {
      if (url === '/') return sendFile(res, path.join(WEB, 'index.html'));
      if (['/ui/app.js', '/ui/style.css', '/ui/concept-bridge.js'].includes(url)) return sendFile(res, path.join(WEB, path.basename(url)));
      if (url === '/concept-preview') {
        let html = fs.readFileSync(path.join(ROOT, 'concept.html'), 'utf-8');
        const bridge = '<script src="/ui/concept-bridge.js"></script>';
        html = html.includes('</body>') ? html.replace('</body>', bridge + '</body>') : html + bridge;
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
        return res.end(html);
      }
      const art = url.match(/^\/api\/artifacts\/([0-9a-f]{32})$/);
      if (art && ARTIFACTS[art[1]]) return sendFile(res, path.join(ART, ARTIFACTS[art[1]]));
      const jobGet = url.match(/^\/api\/jobs\/([0-9a-f]{32})$/);
      if (jobGet && jobs.has(jobGet[1])) return sendJson(res, 200, jobView(jobs.get(jobGet[1])));
      if (url === '/api/capabilities') return sendJson(res, 200, { model: { ready: true, model: 'Qwen3-32B · DGX Spark 本机（预览桩）' }, worker_error: null });
    }
    if (req.method === 'POST' && url === '/api/asr') {
      const buf = await readRaw(req);
      const tmp = path.join(os.tmpdir(), 'ub-asr-' + Date.now() + '.audio');
      fs.writeFileSync(tmp, buf);
      try {
        const out = await execFileAsync(VENV_PY, [path.join(ROOT, 'asr.py'), tmp], { timeout: 300000, maxBuffer: 4 * 1024 * 1024 });
        return sendJson(res, 200, { text: out.stdout.trim() });
      } catch (e) {
        return sendJson(res, 200, { text: '', warn: 'asr unavailable: ' + String(e.message || e).slice(0, 120) });
      } finally { fs.unlink(tmp, () => {}); }
    }
    if (req.method === 'POST' && url === '/api/analyze-drawing') {
      const buf = await readRaw(req);
      try {
        let parsed = null, lastRaw = '';
        for (let attempt = 0; attempt < 3 && !parsed; attempt++) {
          const r = await fetch(OLLAMA + '/api/generate', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: 'moondream', prompt: DRAWING_PROMPT, images: [buf.toString('base64')], stream: false,
                                   keep_alive: '30m',
                                   options: { temperature: 0.1, num_predict: 220 } }),
          });
          const out = await r.json();
          lastRaw = out.response || '';
          parsed = parseDrawingCfg(lastRaw);
          if (!parsed) console.log('vlm unparsable (attempt', attempt + 1, '):', lastRaw.slice(0, 120));
        }
        if (!parsed) return sendJson(res, 502, { error: 'unrecognized drawing' });
        return sendJson(res, 200, parsed);
      } catch (e) {
        return sendJson(res, 502, { error: 'vlm unavailable: ' + String(e.message || e).slice(0, 120) });
      }
    }
    if (req.method === 'POST') {
      const data = await readBody(req);
      if (url === '/api/projects') {
        const project_id = hex(), revision_id = hex();
        revisions.set(revision_id, data.design || {});
        return sendJson(res, 201, { project_id, revision_id });
      }
      const rev = url.match(/^\/api\/projects\/([0-9a-f]{32})\/revisions$/);
      if (rev) {
        const parent = revisions.get(data.parent_revision) || {};
        const design = JSON.parse(JSON.stringify(parent));
        design.simulation = { ...(design.simulation || {}), ...((data.patch || {}).simulation || {}) };
        const revision_id = hex();
        revisions.set(revision_id, design);
        return sendJson(res, 201, { project_id: rev[1], revision_id });
      }
      if (url === '/api/jobs') {
        const base = revisions.get(data.revision_id) || {};
        const design = JSON.parse(JSON.stringify(base));
        design.scene = design.scene || { scene_id: 'moon' };
        design.asset = { body_color: '#F2A65A', scale: 1, ...(design.asset || {}) };
        design.simulation = { gravity_m_s2: 1.62, mass_kg: 2, thrust_n: 7, duration_s: 10, headless: true, ...(design.simulation || {}) };
        const job = { id: hex(), project_id: data.project_id, revision_id: data.revision_id, mode: data.execution_mode || 'agent', start: Date.now() / 1000, design, cancelled: false };
        jobs.set(job.id, job);
        return sendJson(res, 202, jobView(job));
      }
      const cancel = url.match(/^\/api\/jobs\/([0-9a-f]{32})\/cancel$/);
      if (cancel && jobs.has(cancel[1])) {
        jobs.get(cancel[1]).cancelled = true;
        return sendJson(res, 200, jobView(jobs.get(cancel[1])));
      }
    }
    sendJson(res, 404, { error: 'Not found' });
  } catch (e) {
    sendJson(res, 400, { error: String(e.message || e) });
  }
});
server.listen(port, host, () => console.log(`preview on http://${host}:${port}`));
