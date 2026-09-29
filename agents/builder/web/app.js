const $ = (id) => document.getElementById(id);
const terminal = new Set(['succeeded', 'failed', 'cancelled', 'interrupted', 'needs_input']);
const statuses = {queued:'已排队',planning:'Qwen 正在理解需求',building:'正在构建',validating:'Isaac Sim 正在验证',succeeded:'构建与验证通过',failed:'任务未通过',cancelled:'已取消',interrupted:'任务已中断',needs_input:'需要补充信息'};
let token = '', current = null, connected = false, busy = false, timer = null, color = null;
let previewUrl = null, runnerArtifacts = {}, bundleId = null, importRequested = false;

function showError(message) { $('error').textContent = message; $('error').hidden = !message; }
function setBusy(value) {
  busy = value; $('controls').disabled = value || !connected;
  $('cancel').disabled = !value || !current; $('connect').disabled = value;
  $('rerun').disabled = value || current?.detail?.design?.scene?.scene_id !== 'moon';
  $('import-color').disabled = value;
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
    const event = (job.events || []).filter((e) => e.stage === element.dataset.stage).at(-1);
    const state = event?.status || 'waiting'; element.className = state;
    element.querySelector('span').textContent = {running:'进行中',passed:'通过',reused:'复用',waiting:'等待'}[state] || state;
  }
  $('refresh').disabled = false;
}
async function showResults(job) {
  const detail = job.detail; runnerArtifacts = detail.results.runner.artifacts;
  bundleId = detail.results.optimizer.artifacts['scene.zip'];
  $('design').textContent = JSON.stringify(detail.design, null, 2);
  $('result-model').textContent = detail.execution_mode === 'agent' ? '真实模型：'+detail.model : '结构化参数重跑 · 不调用模型';
  const checks = detail.results.runner.checks; const count = Object.values(checks).filter(v => v === true).length;
  $('checks').textContent = `${count}/${Object.keys(checks).length} 项检查通过 · 仿真 ${detail.results.runner.simulated_s} 秒。无训练策略，不代表真实飞行可行性。`;
  $('result').hidden = false;
  const blob = await request('/api/artifacts/'+runnerArtifacts['preview.png'], undefined, true);
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(blob); $('preview').src = previewUrl;
  $('thrust').value = detail.design.simulation.thrust_n ?? 11;
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
$('build-form').addEventListener('submit', async (event) => {
  event.preventDefault(); if (busy || !connected) return;
  showError(''); $('result').hidden = true; current = null; setBusy(true); $('status').textContent = '正在提交需求';
  try {
    const design = {scene:{scene_id:$('scene').value}, asset:{scale:Number($('scale').value)}};
    if (color) design.asset.body_color = color;
    const project = await request('/api/projects', {design});
    current = await request('/api/jobs', {project_id:project.project_id,revision_id:project.revision_id,
      execution_mode:'agent',request_id:crypto.randomUUID(),instruction:$('instruction').value.trim()});
    setBusy(true); await poll();
  } catch (error) { setBusy(false); showError('提交未确认：'+error.message+' 请先核对服务端任务，避免重复启动。'); }
});
$('cancel').addEventListener('click', async () => {
  if (!current) return;
  try { await request('/api/jobs/'+current.job_id+'/cancel', {}); $('status').textContent = '已请求取消，等待安全停止'; await poll(); }
  catch (error) { showError(error.message); }
});
$('refresh').addEventListener('click', () => { if (current) poll(); });
$('import-color').addEventListener('click', () => {
  importRequested = true; $('concept').contentWindow.postMessage({type:'unbound:request-color'}, '*');
});
window.addEventListener('message', (event) => {
  if (!importRequested || busy || event.source !== $('concept').contentWindow || event.data?.type !== 'unbound:concept-color') return;
  if (!/^#[0-9a-f]{6}$/i.test(event.data.color || '')) return;
  color = event.data.color.toUpperCase(); importRequested = false;
  $('import-note').textContent = '已采用机身色 '+color+'。只影响下一次新建任务；需求文字若指定其他颜色，由模型处理。翅膀、口头禅、电量及性格标签未导入。';
});
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
