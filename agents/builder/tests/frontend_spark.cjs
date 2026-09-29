// Opt-in real browser + Spark acceptance. Requires a separately started service/tunnel.
// Run with PLAYWRIGHT_MODULE set to the installed playwright package and
// UNBOUND_TEST_TOKEN_FILE pointing to a private file outside the public source.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

async function main() {
  const root = path.resolve(process.env.UNBOUND_TEST_OUTPUT || 'artifacts/frontend-20260929');
  const model = process.env.UNBOUND_TEST_MODEL || 'qwen2.5:7b';
  const baseUrl = process.env.UNBOUND_TEST_URL || 'http://127.0.0.1:8765/';
  const testConcept = process.env.UNBOUND_TEST_CONCEPT !== '0';
  fs.mkdirSync(root, {recursive:true});
  const token = fs.readFileSync(process.env.UNBOUND_TEST_TOKEN_FILE, 'utf8').trim();
  const context = await chromium.launchPersistentContext(path.join(root,'browser-profile'), {
    channel:'chrome', headless:process.env.HEADLESS !== '0', viewport:{width:1440,height:1050},
    acceptDownloads:true,
  });
  const page = context.pages()[0] || await context.newPage();
  const errors = []; const jobs = new Map();
  page.on('pageerror', e => errors.push(e.message));
  page.on('response', async r => {
    if (/\/api\/jobs\/[0-9a-f]{32}$/.test(r.url()) && r.status() === 200) {
      const j = await r.json().catch(() => null); if (j) jobs.set(j.job_id,j);
    }
  });
  let passed = false;
  try {
    await page.goto(baseUrl, {waitUntil:'networkidle'});
    assert.equal(await page.locator('#build').isDisabled(),true);
    await page.locator('#token').fill('wrong-token-that-is-at-least-32-characters');
    await page.locator('#connect').click();
    await page.waitForFunction(() => document.getElementById('error').textContent.includes('令牌不正确'));
    assert.equal(await page.locator('#build').isDisabled(),true);
    await page.locator('#token').fill(token); await page.locator('#connect').click();
    await page.waitForFunction(() => !document.getElementById('controls').disabled);
    assert.equal(await page.locator('#model').textContent(),model);
    assert.equal(await page.locator('#token').inputValue(),'');
    if (testConcept) {
      const frame = page.frameLocator('#concept');
      await frame.locator('#swatches .sw').nth(3).click();
      await page.locator('#import-color').click();
      await page.waitForFunction(() => document.getElementById('import-note').textContent.includes('#378ADD'));
      assert.equal(await frame.locator('.community').isVisible(),false);
    }
    await page.locator('#build').click();
    await page.waitForFunction(() => document.getElementById('job-id').textContent.includes('agent'));
    assert.equal(await page.locator('#build').isDisabled(),true);
    await page.waitForFunction(() => ['构建与验证通过','任务未通过','需要补充信息','任务已中断'].includes(document.getElementById('status').textContent),null,{timeout:240000});
    assert.equal(await page.locator('#status').textContent(),'构建与验证通过',await page.locator('#error').textContent());
    await page.waitForFunction(() => {const im=document.getElementById('preview');return im.complete && im.naturalWidth>0;},null,{timeout:30000});
    const firstId = (await page.locator('#job-id').textContent()).match(/[0-9a-f]{32}/)[0];
    const first = jobs.get(firstId); assert.ok(first);
    assert.equal(first.detail.model,model);
    assert.equal(first.detail.design.asset.body_color,'#2867D7');
    assert.equal(first.detail.design.scene.scene_id,'moon');
    assert.equal(first.detail.design.simulation.mass_kg,2);
    assert.equal(first.detail.design.simulation.thrust_n,7);
    assert.equal(first.detail.results.runner.simulated_s,10);
    assert.equal(Object.values(first.detail.results.runner.checks).every(v => v === true),true);
    const downloadReady = page.waitForEvent('download'); await page.locator('#report').click();
    const download = await downloadReady; await download.saveAs(path.join(root,'browser-run-report.json'));
    const run = JSON.parse(fs.readFileSync(path.join(root,'browser-run-report.json'),'utf8'));
    assert.equal(run.status,'succeeded'); assert.equal(run.request.thrust_n,7);
    await page.screenshot({path:path.join(root,'browser-agent-success.png'),fullPage:true});
    fs.writeFileSync(path.join(root,'browser-agent-job.json'),JSON.stringify(first,null,2));
    console.log(JSON.stringify({phase:'browser-agent-passed',job_id:firstId,checks:run.checks}));

    await page.locator('#thrust').fill('11'); await page.locator('#rerun').click();
    await page.waitForFunction(() => document.getElementById('job-id').textContent.includes('structured'));
    await page.waitForFunction(() => ['构建与验证通过','任务未通过','任务已中断'].includes(document.getElementById('status').textContent),null,{timeout:240000});
    assert.equal(await page.locator('#status').textContent(),'构建与验证通过',await page.locator('#error').textContent());
    const secondId = (await page.locator('#job-id').textContent()).match(/[0-9a-f]{32}/)[0];
    const second = jobs.get(secondId); assert.ok(second);
    assert.equal(second.detail.design.simulation.thrust_n,11);
    for (const stage of ['asset','personality','scene','optimizer']) assert.equal(second.detail.results[stage].reused,true);
    assert.equal(second.detail.results.runner.reused,false);
    await page.waitForFunction(() => {const im=document.getElementById('preview');return im.complete && im.naturalWidth>0;});
    await page.screenshot({path:path.join(root,'browser-force-success.png'),fullPage:true});
    fs.writeFileSync(path.join(root,'browser-force-job.json'),JSON.stringify(second,null,2));
    await page.setViewportSize({width:390,height:844});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true);
    await page.screenshot({path:path.join(root,'browser-mobile.png'),fullPage:true});
    await page.setViewportSize({width:1440,height:1050});
    assert.deepEqual(errors,[]);
    const report = {status:'passed',model,agent_job:firstId,structured_followup:secondId,
      auth_rejection:true,color_import:testConcept ? true : 'not_tested',concept_community_disabled:testConcept ? true : 'not_tested',actual_preview:true,
      report_download:true,four_stages_reused:true,mobile_no_horizontal_overflow:true,
      browser_page_errors:errors,scope:'Real browser controls through SSH tunnel to five Skills and Isaac; not live streaming or a human keyboard test.'};
    fs.writeFileSync(path.join(root,'frontend-acceptance.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report)); passed = true;
  } catch(error) {
    await page.screenshot({path:path.join(root,'browser-failure.png'),fullPage:true}).catch(() => {});
    fs.writeFileSync(path.join(root,'frontend-failure.json'),JSON.stringify({error:error.message,jobs:[...jobs.values()],page_errors:errors},null,2));
    throw error;
  } finally {
    if (passed && process.env.KEEP_OPEN === '1') {
      console.log('Verified browser window left open for up to 2 hours.');
      await new Promise(resolve => setTimeout(resolve,7200000));
    }
    await context.close();
  }
}
main().catch(e => {console.error(e.message);process.exitCode=1;});
