const $ = (id) => document.getElementById(id);
const terminal = new Set(['succeeded', 'failed', 'cancelled', 'interrupted', 'needs_input']);
const statuses = {queued:'已排队',planning:'Qwen 正在理解需求',building:'正在构建',validating:'Isaac Sim 正在验证',succeeded:'构建与验证通过',failed:'任务未通过',cancelled:'已取消',interrupted:'任务已中断',needs_input:'需要补充信息'};
let token = '', current = null, connected = false, busy = false, timer = null, color = null;
let previewUrl = null, runnerArtifacts = {}, bundleId = null;
let busySince = null, elapsedTimer = null, cancelArmed = false, cancelTimer = null;
const KID_SCENE = {grass:'meadow', space:'space', moon:'moon'};
const KID_STAGE_TEXT = {asset:'正在挑选身体…', personality:'正在画上笑脸…', scene:'正在搬进小世界…', optimizer:'正在收拾房间…', runner:'正在试飞！'};
const KID_STAGE_ORDER = ['asset', 'personality', 'scene', 'optimizer', 'runner'];
let kidJob = false, robotName = '', kidTemplate = null;
const CREATURE_TEMPLATES = {duck:{id:'duck', name:'网红鸭'}, flying_cat:{id:'flying_cat', name:'飞行猫'}, crab:{id:'crab', name:'小螃蟹'}};  /* v0.5: crab added; asset-builder must support template 'crab' */

function setMode(kid) {
  $('mode-kid').classList.toggle('on', kid);
  $('mode-engineer').classList.toggle('on', !kid);
  $('mode-kid').setAttribute('aria-selected', kid);
  $('mode-engineer').setAttribute('aria-selected', !kid);
  document.body.classList.toggle('kid', kid);
  document.querySelector('main').hidden = kid;
  $('kid-view').hidden = !kid;
  if (!kid) stopKidRecording(true);
}
function playHandoff() {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return Promise.resolve();
  $('handoff').hidden = false;
  return new Promise((resolve) => setTimeout(() => { $('handoff').hidden = true; resolve(); }, 1200));
}
function forwardToFactory(msg) {
  const factory = $('factory');
  if (factory && factory.contentWindow) factory.contentWindow.postMessage(msg, '*');
}
/* Kid-facing build narration lives inside the factory page; we just forward stage events. */
function renderDiary(job) {
  if (!kidJob) return;
  let passed = 0, runningIdx = -1;
  KID_STAGE_ORDER.forEach((stage, i) => {
    const event = (job.events || []).filter((e) => e.stage === stage).at(-1);
    if (event?.status === 'passed' || event?.status === 'reused') passed++;
    else if (event?.status === 'running' && runningIdx === -1) runningIdx = i;
  });
  let text, pct;
  if (job.status === 'succeeded') { text = '造好啦！它马上就来见你～'; pct = 100; }
  else if (terminal.has(job.status)) { text = '哎呀，这次没造成…没关系，我们再试试！'; pct = Math.round(passed / 5 * 100); }
  else {
    const idx = runningIdx === -1 ? Math.min(passed, 4) : runningIdx;
    text = KID_STAGE_TEXT[KID_STAGE_ORDER[idx]];
    pct = Math.round((passed + (runningIdx !== -1 ? 0.5 : 0)) / 5 * 100);
  }
  forwardToFactory({type:'unbound:build-stage', text, pct, done: terminal.has(job.status), ok: job.status === 'succeeded'});
}

function showError(message) {
  $('error').textContent = message; $('error').hidden = !message;
  if (message) $('error').scrollIntoView({behavior:'smooth', block:'nearest'});
}
function fmtDuration(seconds) {
  const s = Math.max(0, Math.round(seconds));
  return s >= 60 ? Math.floor(s / 60) + ' 分 ' + (s % 60) + ' 秒' : s + ' 秒';
}
function tickElapsed() {
  if (busySince !== null) $('elapsed').textContent = '已等待 ' + fmtDuration((Date.now() - busySince) / 1000);
}
function disarmCancel() {
  cancelArmed = false; clearTimeout(cancelTimer); $('cancel').textContent = '取消任务';
}
function setBusy(value) {
  busy = value; $('controls').disabled = value || !connected;
  $('cancel').disabled = !value || !current; $('connect').disabled = value;
  $('rerun').disabled = value || current?.detail?.design?.scene?.scene_id !== 'moon';
  $('build').textContent = value ? '构建与验证进行中…' : '让 Qwen 构建并验证';
  $('kid-send').disabled = value;
  $('kid-send').querySelector('.lbl').textContent = value ? '正在造…' : '送去工厂真正造出来';
  $('kid-send').querySelector('.ico').textContent = value ? '🛠' : '🚀';
  clearInterval(elapsedTimer); elapsedTimer = null;
  if (value) { if (busySince === null) busySince = Date.now(); tickElapsed(); elapsedTimer = setInterval(tickElapsed, 1000); }
  else { busySince = null; $('elapsed').textContent = ''; disarmCancel(); }
}
async function request(path, data, binary = false) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(path, {method:data === undefined ? 'GET' : 'POST',
      headers:{Authorization:'Bearer '+token, ...(data === undefined ? {} : {'Content-Type':'application/json'})},
      body:data === undefined ? undefined : JSON.stringify(data), signal:controller.signal});
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(response.status === 401 ? '连接令牌不正确，请重新连接。' : `请求失败 (${response.status})：${detail.error || '请检查服务'}`);
    }
    return binary ? response.blob() : response.json();
  } finally { clearTimeout(timeout); }
}
function renderJob(job) {
  $('status').textContent = statuses[job.status] || job.status;
  $('job-id').textContent = '任务 '+job.job_id+' · '+job.execution_mode;
  for (const element of $('stages').children) {
    const events = (job.events || []).filter((e) => e.stage === element.dataset.stage);
    const event = events.at(-1);
    const state = event?.status || 'waiting'; element.className = state;
    let label = {running:'进行中',passed:'通过',reused:'复用',waiting:'等待'}[state] || state;
    const first = events.find((e) => typeof e.time === 'number');
    if (first && event && typeof event.time === 'number' && state !== 'running' && state !== 'waiting' && event.time - first.time >= 1) {
      label += ' · ' + fmtDuration(event.time - first.time);
    }
    element.querySelector('span').textContent = label;
  }
  $('refresh').disabled = false;
  $('updated').textContent = '状态更新于 ' + new Date().toLocaleTimeString('zh-CN', {hour12:false});
  renderDiary(job);
}
function confettiBurst(canvas, duration = 2400) {
  const ctx = canvas.getContext('2d');
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = innerWidth * dpr; canvas.height = innerHeight * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const palette = ['#E8513D', '#2867D7', '#FFC531', '#35C07A', '#B088D8'];
  const parts = Array.from({length: 130}, () => ({
    x: Math.random() * innerWidth, y: -30 - Math.random() * innerHeight * 0.4,
    w: 6 + Math.random() * 6, h: 8 + Math.random() * 8,
    vy: 2.2 + Math.random() * 3, vx: -1.2 + Math.random() * 2.4,
    rot: Math.random() * Math.PI, vr: -0.12 + Math.random() * 0.24,
    color: palette[Math.floor(Math.random() * palette.length)],
  }));
  const start = performance.now(); let raf = 0;
  (function frame(t) {
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    for (const p of parts) {
      p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot);
      ctx.fillStyle = p.color; ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h); ctx.restore();
    }
    if (t - start < duration) raf = requestAnimationFrame(frame);
    else ctx.clearRect(0, 0, innerWidth, innerHeight);
  })(start);
  return () => cancelAnimationFrame(raf);
}
function showCeremony(checksText) {
  $('ceremony-img').src = previewUrl;
  $('ceremony-caption').textContent = robotName ? robotName + '的第一张试飞照片！🎉' : '它真的动起来啦！🎉';
  $('ceremony-checks').textContent = checksText;
  $('ceremony').hidden = false;
  if (!matchMedia('(prefers-reduced-motion: reduce)').matches) confettiBurst($('confetti'));
}
function hideCeremony() { $('ceremony').hidden = true; }
async function showResults(job) {
  const detail = job.detail; runnerArtifacts = detail.results.runner.artifacts;
  bundleId = detail.results.optimizer.artifacts['scene.zip'];
  $('design').textContent = JSON.stringify(detail.design, null, 2);
  $('result-model').textContent = detail.execution_mode === 'agent' ? '真实模型：'+detail.model : '结构化参数重跑 · 不调用模型';
  const checks = detail.results.runner.checks; const count = Object.values(checks).filter(v => v === true).length;
  $('checks').textContent = `${count}/${Object.keys(checks).length} 项检查通过 · 仿真 ${detail.results.runner.simulated_s} 秒。无训练策略，不代表真实飞行可行性。`;
  $('result').hidden = false;
  $('result').scrollIntoView({behavior:'smooth', block:'start'});
  const blob = await request('/api/artifacts/'+runnerArtifacts['preview.png'], undefined, true);
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(blob); $('preview').src = previewUrl;
  $('thrust').value = detail.design.simulation.thrust_n ?? 11;
  showCeremony($('checks').textContent);
  forwardToFactory({type:'unbound:build-photo', artifact: runnerArtifacts['preview.png'], name: robotName});
}
async function poll() {
  clearTimeout(timer);
  try {
    const job = await request('/api/jobs/'+current.job_id); current = job; renderJob(job); showError('');
    if (terminal.has(job.status)) {
      setBusy(false);
      if (job.status === 'succeeded') await showResults(job);
      else showError(job.detail?.message || '未生成已验证结果。请调整需求后重新提交；服务端保留诊断记录。');
    } else { setBusy(true); timer = setTimeout(poll, 1200); }
  } catch (error) {
    showError('状态查询失败：'+error.message+' 原任务可能仍在运行，请点击“重新查询”。不要重复提交。');
    $('refresh').disabled = false;
  }
}
$('connect').addEventListener('click', async () => {
  showError(''); token = $('token').value.trim();
  if (token.length < 32) { showError('请输入至少 32 字符的本机访问令牌。'); return; }
  try {
    const capabilities = await request('/api/capabilities');
    connected = capabilities.model.ready && !capabilities.worker_error;
    $('model').textContent = capabilities.model.model;
    $('connection-status').textContent = connected ? '已连接 Spark 本地模型。页面刷新后需要重新输入令牌。' : '模型未就绪或 worker 异常，请先检查 Spark 服务。';
    $('connection').open = !connected; $('token').value = ''; setBusy(false);
  } catch (error) { connected = false; setBusy(false); showError(error.message); }
});
$('token').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') { event.preventDefault(); $('connect').click(); }
});
$('instruction').addEventListener('input', () => { $('instruction-count').textContent = $('instruction').value.length; });
$('instruction-count').textContent = $('instruction').value.length;
async function submitBuild() {
  if (busy || !connected) return;
  showError(''); $('result').hidden = true; current = null; setBusy(true); $('status').textContent = '正在提交需求';
  if (kidJob) forwardToFactory({type:'unbound:build-stage', text:KID_STAGE_TEXT.asset, pct:5, done:false, ok:false});
  try {
    const design = {scene:{scene_id:$('scene').value}, asset:{scale:Number($('scale').value)}};
    if (color) design.asset.body_color = color;
    if (kidJob && kidTemplate) design.asset.template = kidTemplate.id;
    const project = await request('/api/projects', {design});
    current = await request('/api/jobs', {project_id:project.project_id,revision_id:project.revision_id,
      execution_mode:'agent',request_id:crypto.randomUUID(),instruction:$('instruction').value.trim()});
    setBusy(true); await poll();
  } catch (error) { setBusy(false); showError('提交未确认：'+error.message+' 请先核对服务端任务，避免重复启动。'); }
}
$('build-form').addEventListener('submit', (event) => { event.preventDefault(); kidJob = false; submitBuild(); });

/* ---- kid entry bar (v0.3): speak / draw / type / send sit on the frame, the factory page only listens ---- */
let kidRecorder = null, kidChunks = [], kidStream = null, kidToastTimer = null;
function kidToast(text, isErr) {
  const t = $('kid-toast'); t.textContent = text; t.classList.toggle('err', !!isErr); t.hidden = false;
  clearTimeout(kidToastTimer); kidToastTimer = setTimeout(() => { t.hidden = true; }, 3000);
}
function setVoiceUi(on) {
  const b = $('kid-voice'); b.classList.toggle('rec', on); b.setAttribute('aria-pressed', on);
  b.querySelector('.lbl').textContent = on ? '说完啦' : '说出来';
}
function stopKidRecording(discard) {
  if (!kidRecorder || kidRecorder.state !== 'recording') return;
  if (discard) kidRecorder.onstop = () => { kidStream?.getTracks().forEach((t) => t.stop()); setVoiceUi(false); };
  kidRecorder.stop();
}
$('kid-voice').addEventListener('click', async () => {
  if (kidRecorder && kidRecorder.state === 'recording') { stopKidRecording(false); return; }
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
    kidToast('这个浏览器没有麦克风，画给我看吧！', true); return;
  }
  try {
    kidStream = await navigator.mediaDevices.getUserMedia({audio: true});
    kidChunks = []; kidRecorder = new MediaRecorder(kidStream);
    kidRecorder.ondataavailable = (e) => kidChunks.push(e.data);
    kidRecorder.onstop = () => {
      kidStream.getTracks().forEach((t) => t.stop()); setVoiceUi(false);
      forwardToFactory({type: 'unbound:express', kind: 'audio', blob: new Blob(kidChunks)});
    };
    kidRecorder.start(); setVoiceUi(true);
  } catch (error) { kidToast('麦克风没打开，可以画给我看！', true); }
});
$('kid-draw').addEventListener('click', () => { $('kid-file').value = ''; $('kid-file').click(); });
$('kid-file').addEventListener('change', (event) => {
  const file = event.target.files && event.target.files[0];
  if (file) forwardToFactory({type: 'unbound:express', kind: 'image', file});
});
$('kid-text-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const text = $('kid-text').value.trim();
  if (!text) return;
  forwardToFactory({type: 'unbound:express', kind: 'text', text: text.slice(0, 200)});
  $('kid-text').value = '';
});
$('kid-send').addEventListener('click', () => forwardToFactory({type: 'unbound:request-send'}));
$('mode-kid').addEventListener('click', () => setMode(true));
$('mode-engineer').addEventListener('click', () => setMode(false));
window.addEventListener('message', (event) => {
  if (event.source !== $('factory').contentWindow || event.data?.type !== 'unbound:robot-name') return;
  robotName = String(event.data.name || '').replace(/[<>]/g, '').trim().slice(0, 12);
});
window.addEventListener('message', async (event) => {
  const factory = $('factory');
  if (event.source !== factory.contentWindow || event.data?.type !== 'unbound:build-request') return;
  if (!/^#[0-9a-f]{6}$/i.test(event.data.color || '')) return;
  const reply = (msg) => factory.contentWindow.postMessage(msg, '*');
  color = event.data.color.toUpperCase();
  const swatch = $('color-swatch'); swatch.hidden = false; swatch.style.background = color; swatch.title = color;
  kidTemplate = CREATURE_TEMPLATES[event.data.creature] || CREATURE_TEMPLATES.flying_cat;
  $('scene').value = KID_SCENE[event.data.scene] || 'meadow';
  const sceneName = $('scene').selectedOptions[0].textContent.split(' ')[0];
  if (event.data.svg) $('kid-order-fig').innerHTML = event.data.svg;
  $('kid-order-text').textContent = kidTemplate.name+' · 机身 '+color+' · '+sceneName+' · '+new Date().toLocaleTimeString('zh-CN', {hour12:false});
  $('kid-order-raw').textContent = JSON.stringify(event.data.cfg || {}, null, 2);
  $('kid-order').hidden = false; $('order-empty').hidden = true;
  $('import-note').textContent = '已采用机身色 '+color+'。翅膀、表情和性格标签暂未映射，不会进入真实构建。';
  $('instruction').value = '把'+kidTemplate.name+'身体改成颜色 '+color+'。在'+sceneName+'场景，质量 2kg，向上推力 7N，默认开心表情，运行 10 秒无窗口测试。';
  $('instruction-count').textContent = $('instruction').value.length;
  if (!connected || busy) {
    kidJob = false;
    reply({type:'unbound:build-blocked', reason: connected ? '上一个作品还在建造中，等它完成哦' : '需要先由大人连接 Spark 服务'});
    setMode(false); $('connection').open = true;
    showError(connected ? '上一个任务还在进行中，请等它完成后再送出作品。' : '请先在「连接本机服务」中输入令牌，再让孩子送出作品。');
    return;
  }
  kidJob = true; robotName = '';
  reply({type:'unbound:build-accepted'});
  await playHandoff();
  setMode(true);   /* the child stays in their own world; engineer mode is opt-in */
  await submitBuild();
});
$('cancel').addEventListener('click', async () => {
  if (!current) return;
  if (!cancelArmed) {
    cancelArmed = true; $('cancel').textContent = '再点一次确认取消';
    cancelTimer = setTimeout(disarmCancel, 3000);
    return;
  }
  disarmCancel();
  try { await request('/api/jobs/'+current.job_id+'/cancel', {}); $('status').textContent = '已请求取消，等待安全停止'; await poll(); }
  catch (error) { showError(error.message); }
});
$('refresh').addEventListener('click', () => { if (current) poll(); });
$('rerun').addEventListener('click', async () => {
  if (busy || current?.status !== 'succeeded' || current.detail.design.scene.scene_id !== 'moon') return;
  const thrust = Number($('thrust').value);
  if (!$('thrust').value || !Number.isFinite(thrust) || thrust < 0 || thrust > 50) { showError('推力范围为 0–50N。'); return; }
  setBusy(true); showError(''); $('result').hidden = true;
  try {
    const revision = await request('/api/projects/'+current.project_id+'/revisions',
      {parent_revision:current.detail.revision_id,patch:{simulation:{thrust_n:thrust}}});
    current = await request('/api/jobs', {project_id:revision.project_id,revision_id:revision.revision_id,
      execution_mode:'structured',request_id:crypto.randomUUID()});
    await poll();
  } catch (error) { setBusy(false); showError('参数修改未确认：'+error.message); }
});
async function download(id, filename) {
  if (!id) return;
  try {
    const blob = await request('/api/artifacts/'+id, undefined, true); const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  } catch (error) { showError('下载失败：'+error.message); }
}
$('report').addEventListener('click', () => download(runnerArtifacts['run-report.json'],'run-report.json'));
$('bundle').addEventListener('click', () => download(bundleId,'scene-private.zip'));
$('ceremony-close').addEventListener('click', () => { hideCeremony(); if (kidJob) setMode(false); });
$('ceremony-again').addEventListener('click', () => { hideCeremony(); kidJob = false; setMode(true); window.scrollTo({top:0, behavior:'smooth'}); });
$('ceremony').addEventListener('click', (event) => { if (event.target === $('ceremony')) hideCeremony(); });
document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && !$('ceremony').hidden) hideCeremony(); });
setMode(true);  /* kid-first: the child is the default user; engineer mode is for adults */
