'use strict';
// UI contract tests. All fixtures below are test-only; index.html has no demo data.
// Run: CSP_PLAYWRIGHT_PATH=<absolute playwright package> node static/tests.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require(process.env.CSP_PLAYWRIGHT_PATH || 'playwright');
const htmlPath = path.join(__dirname, 'index.html');
const tests = [];
const test = (name, fn) => tests.push({name, fn});
const bootstrap = {
  csrf: 'test-csrf', version: '1.0.0',
  regions: [{id:'jp',name:'日本'},{id:'sg',name:'新加坡'},{id:'hk',name:'香港'},{id:'kr',name:'韩国'},{id:'tw',name:'台湾'},{id:'us',name:'美国'},{id:'other',name:'其他'}],
  sites: [{id:'chatgpt',name:'ChatGPT',url:'https://chatgpt.com/cdn-cgi/trace',statuses:[200],validator:'chatgpt-trace'}, {id:'test-site',name:'TEST 网站',url:'https://example.com/',statuses:[200],validator:'none'}],
  options: {regions:['jp','sg'],group:'',provider:'',include:'',exclude:'',limit:0,rounds:3,workers:4,timeout:8,node_names:[]},
  connection: {config_path:'',binary_path:'',core_dir:'',controller:'',unix_socket:'',interface:''},
  last_report:null
};
async function setup(browser, responses = {}) {
  const page = await browser.newPage();
  page.setDefaultTimeout(3500);
  const calls = [], errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/**', async route => {
    const req = route.request();
    const endpoint = new URL(req.url()).pathname;
    const payload = req.postData() ? JSON.parse(req.postData()) : null;
    calls.push({endpoint, method:req.method(), headers:req.headers(), payload});
    const handler = responses[endpoint];
    let result;
    if (typeof handler === 'function') result = await handler(payload, calls);
    else if (handler) result = handler;
    else if (endpoint === '/api/bootstrap') result = bootstrap;
    else if (endpoint === '/api/job') result = {id:null,running:false,events:[],report:null,error:null,progress:{completed:0,total:0}};
    else result = {httpStatus:400, error:'TEST 未配置的 API'};
    const {httpStatus = 200, ...body} = result;
    await route.fulfill({status:httpStatus, contentType:'application/json', body:JSON.stringify(body)});
  });
  await page.goto(global.baseURL);
  return {page,calls,errors};
}
const waitFor = async (fn, message) => {
  for(let i=0;i<60;i++) { if(await fn()) return; await new Promise(r=>setTimeout(r,50)); }
  assert.fail(message);
};
test('bootstrap renders Chinese configuration, default regions and ChatGPT only', async browser => {
  const {page,errors} = await setup(browser);
  await waitFor(async()=>await page.locator('#region-jp').count(), 'Bootstrap must render Japan checkbox');
  assert.equal(await page.title(),'ProxySprint · 代理节点测速 · 按网站挑选线路');
  assert.equal(await page.locator('#region-jp').isChecked(),true);
  assert.equal(await page.locator('#region-sg').isChecked(),true);
  assert.equal(await page.locator('#region-hk').isChecked(),false);
  assert.equal(await page.locator('input[data-site-id="chatgpt"]').isChecked(),true);
  assert.equal(await page.locator('input[data-site-id="test-site"]').isChecked(),false);
  assert.equal(await page.locator('#export-json').getAttribute('aria-disabled'),'true');
  assert.match(await page.locator('#results-empty').innerText(),/尚未开始/);
  assert.deepEqual(errors,[]);
  await page.close();
});
test('configuration discovers catalog, previews scope, saves settings before start, and stops', async browser => {
  const testNodes = [{name:'TEST 日本 <script>window.injected=1</script>',region:'jp',provider:'TEST 订阅',type:'ss'}, {name:'TEST 新加坡',region:'sg',provider:'TEST 订阅',type:'ss'}];
  let running=false;
  const {page,calls,errors} = await setup(browser, {
    '/api/catalog': {connection:{...bootstrap.connection,controller:'http://127.0.0.1:9090'},nodes:testNodes,groups:[{name:'TEST 策略组',now:'TEST 新加坡',all:['TEST 子组']}],providers:['TEST 订阅'],warnings:['TEST catalog warning'],version:'1.0.0'},
    '/api/preview': payload => ({nodes:payload.options.node_names.length?testNodes.filter(n=>payload.options.node_names.includes(n.name)):testNodes,total:payload.options.node_names.length||2,catalog:{nodes:testNodes,groups:[],providers:[]},warnings:[]}),
    '/api/settings': payload => payload,
    '/api/start': () => {running=true;return {id:'test-job',running:true};},
    '/api/job': () => ({id:running?'test-job':null,running,events:running?[{seq:1,event:'start',total:6},{seq:2,event:'progress',text:'TEST 正在探测'}]:[],report:null,error:null,progress:{completed:0,total:6}}),
    '/api/stop': () => {running=false;return {stopping:true};}
  });
  await page.locator('#refresh-catalog').click();
  await waitFor(async()=>await page.locator('#group option[value="TEST 策略组"]').count(), 'Catalog group must be available');
  assert.equal(await page.locator('#controller').inputValue(),'http://127.0.0.1:9090');
  await page.locator('#all-regions').click();
  for(const region of bootstrap.regions) assert.equal(await page.locator('#region-'+region.id).isChecked(),true);
  await page.locator('#default-regions').click();
  await page.locator('#group').selectOption('TEST 策略组');
  await page.locator('#provider').selectOption('TEST 订阅');
  await page.locator('#include').fill('TEST, <script>');
  await page.locator('#exclude').fill('到期, 流量');
  await page.locator('#preview-button').click();
  await waitFor(async()=>/2/.test(await page.locator('#preview-line').innerText()), 'Preview must show real node count');
  await page.locator('#manual-open').click();
  await page.locator('#manual-dialog').waitFor({state:'visible'});
  assert.equal(await page.locator('#manual-list input:checked').count(),0);
  assert.equal(await page.evaluate(()=>window.injected),undefined);
  await page.locator('#manual-list input').first().check();
  await page.locator('#manual-apply').click();
  assert.match(await page.locator('#manual-summary').innerText(),/已手动限定 1 个/);
  await page.locator('input[data-site-id="test-site"]').check();
  await page.locator('#start-button').click();
  await waitFor(()=>calls.some(c=>c.endpoint==='/api/start'), 'Start endpoint must be called');
  const saveIndex=calls.findIndex(c=>c.endpoint==='/api/settings');
  const startIndex=calls.findIndex(c=>c.endpoint==='/api/start');
  assert.ok(saveIndex>=0&&saveIndex<startIndex);
  assert.deepEqual(calls[startIndex].payload.site_ids,['chatgpt','test-site']);
  assert.deepEqual(calls[startIndex].payload.options.regions,['jp','sg']);
  assert.equal(calls[startIndex].payload.options.include,'TEST, <script>');
  assert.deepEqual(calls[startIndex].payload.options.node_names,[testNodes[0].name]);
  for(const call of calls.filter(c=>c.method==='POST')) {
    assert.equal(call.headers['x-csrf-token'],'test-csrf');
    assert.equal(call.headers['content-type'],'application/json');
  }
  assert.equal(await page.locator('#start-button').isDisabled(),true);
  await page.locator('#stop-button').click();
  await waitFor(()=>calls.some(c=>c.endpoint==='/api/stop'),'Stop must call API');
  await waitFor(async()=>!(await page.locator('#start-button').isDisabled()),'Polling must restore controls after stop');
  assert.deepEqual(errors,[]);
  await page.close();
});
test('real report retains failed rows, sorts, filters websites and shows safe sample details', async browser => {
  const row = overrides => ({name:'TEST successful',region:'jp',provider:'TEST provider',site_id:'chatgpt',site_name:'ChatGPT',url:'https://chatgpt.com/cdn-cgi/trace',success_rate:1,successes:3,total:3,median_ms:150,jitter_ms:20,samples:[{ok:true,status:200,ttfb_ms:150,total_ms:200,reason:''}],eligible:true,...overrides});
  const failed=row({name:'TEST <img src=x onerror="window.injected=1">',site_id:'test-site',site_name:'TEST 网站',success_rate:0,successes:0,median_ms:null,jitter_ms:null,eligible:false,samples:[{ok:false,status:403,ttfb_ms:10,total_ms:15,reason:'TEST denied <script>window.injected=1</script>'}]});
  const rows=[failed,row({name:'TEST partial',success_rate:0.5,successes:1,total:2,median_ms:50,eligible:false}),row({name:'TEST best'})];
  const report={created_at:'2026-10-14T10:00:00+08:00',rows,recommendations:[{site_id:'chatgpt',site_name:'ChatGPT',name:'TEST best',median_ms:150,success_rate:1}],warnings:['TEST warning'],note:'TEST 实际报告说明',options:bootstrap.options};
  const {page,errors} = await setup(browser, {'/api/bootstrap':{...bootstrap,last_report:report}});
  await waitFor(async()=>await page.locator('#result-rows tr').count()===3,'Report rows must render');
  assert.match(await page.locator('#result-rows tr').first().innerText(),/TEST best/);
  assert.match(await page.locator('#result-rows tr').last().innerText(),/TEST <img/);
  assert.equal(await page.locator('#export-json').getAttribute('aria-disabled'),'false');
  assert.match(await page.locator('#recommendations').innerText(),/TEST best/);
  assert.match(await page.locator('#warnings').innerText(),/TEST warning/,'Stored report warnings must survive reload');
  await page.locator('#result-site').selectOption('test-site');
  assert.equal(await page.locator('#result-rows tr').count(),1);
  await page.locator('#result-rows .node-button').click();
  await page.locator('#detail-dialog').waitFor({state:'visible'});
  assert.match(await page.locator('#sample-rows').innerText(),/403/);
  assert.match(await page.locator('#sample-rows').innerText(),/TEST denied <script>/);
  assert.equal(await page.locator('#sample-rows script').count(),0);
  assert.equal(await page.locator('#result-rows img').count(),0);
  assert.equal(await page.evaluate(()=>window.injected),undefined);
  await page.keyboard.press('Escape');
  await page.locator('#result-site').selectOption('');
  await page.locator('#result-search').fill('TEST best');
  assert.equal(await page.locator('#result-rows tr').count(),1);
  await page.locator('#result-search').fill('no matching node');
  assert.match(await page.locator('#results-empty').innerText(),/没有符合/);
  await page.locator('#result-search').fill('');
  assert.equal(await page.locator('#result-rows tr').count(),3);
  await page.locator('#tab-compare').click();
  assert.equal(await page.locator('#configuration').isVisible(),false);
  await page.locator('#tab-configure').click();
  assert.equal(await page.locator('#configuration').isVisible(),true);
  assert.deepEqual(errors,[]);
  await page.close();
});
test('invalid numeric settings are rejected before any settings write', async browser => {
  const {page,calls} = await setup(browser, {'/api/settings':payload=>payload});
  await waitFor(async()=>!(await page.locator('#save-button').isDisabled()),'Ready to save');
  for(const [id,value] of [['workers','0'],['workers','17'],['rounds','11'],['limit','201'],['timeout','0.5'],['timeout','121']]) {
    await page.locator('#workers').fill('4');
    await page.locator('#rounds').fill('3');
    await page.locator('#limit').fill('0');
    await page.locator('#timeout').fill('8');
    await page.locator('#'+id).fill(value);
    await page.locator('#save-button').click();
    await page.waitForTimeout(80);
    assert.equal(calls.filter(c=>c.endpoint==='/api/settings').length,0,`Invalid ${id} ${value} must not be saved`);
    assert.equal(await page.locator('#notice').isVisible(),true);
  }
  await page.close();
});
test('reconnects active job, consumes each event once, and stops polling on completion', async browser => {
  const row={name:'TEST live node',region:'jp',provider:'TEST provider',site_id:'chatgpt',site_name:'ChatGPT',url:'https://chatgpt.com/cdn-cgi/trace',success_rate:1,successes:1,total:1,median_ms:12,jitter_ms:0,samples:[{ok:true,status:200,ttfb_ms:12,total_ms:15,reason:''}],eligible:true};
  const report={created_at:'2026-10-14T10:00:00+08:00',rows:[row],recommendations:[],warnings:[],note:'TEST done',options:bootstrap.options};
  const oldReport={...report,recommendations:[{site_id:'chatgpt',site_name:'ChatGPT',name:'TEST stale recommendation',median_ms:12,success_rate:1}]};
  let jobCalls=0;
  const {page,calls,errors}=await setup(browser, {
    '/api/bootstrap':{...bootstrap,last_report:oldReport},
    '/api/job':()=>{jobCalls++;return {id:'test-active',running:jobCalls<3,events:[{seq:1,event:'start',total:1},{seq:2,event:'row',row,completed:1,total:1}],report:jobCalls<3?null:report,error:null,progress:{completed:1,total:1}};}
  });
  await waitFor(()=>jobCalls>=1,'Existing job must load');
  await waitFor(async()=>await page.locator('#result-rows tr').count()===1,'Live row must render');
  assert.equal(await page.locator('#recommendations').isVisible(),false,'Previous report recommendation must not appear for a new running job');
  assert.equal(await page.locator('#export-json').getAttribute('aria-disabled'),'false','Export targets last complete report, even while another job is active');
  assert.equal(await page.locator('#start-button').isDisabled(),true);
  await waitFor(()=>jobCalls>=2,'750ms poll must run');
  assert.equal(await page.locator('#result-rows tr').count(),1,'Repeated seq must not duplicate rows');
  await waitFor(async()=>!(await page.locator('#start-button').isDisabled()),'Completed job must unlock UI');
  assert.equal(await page.locator('#result-rows tr').count(),1);
  assert.equal(await page.locator('#export-csv').getAttribute('aria-disabled'),'false');
  const count=calls.filter(call=>call.endpoint==='/api/job').length;
  await page.waitForTimeout(950);
  assert.equal(calls.filter(call=>call.endpoint==='/api/job').length,count,'No polling when idle');
  assert.deepEqual(errors,[]);
  await page.close();
});
test('desktop keeps run controls visible and mobile reflows without page overflow', async browser => {
  const {page,errors}=await setup(browser);
  await page.setViewportSize({width:1280,height:900});
  await waitFor(async()=>!(await page.locator('#start-button').isDisabled()),'Ready for responsive check');
  const box=await page.locator('#start-button').boundingBox();
  assert.ok(box.y+box.height<=900,'Desktop start control must remain in the viewport');
  if(process.env.CSP_UI_EVIDENCE){fs.mkdirSync(process.env.CSP_UI_EVIDENCE,{recursive:true});await page.screenshot({path:path.join(process.env.CSP_UI_EVIDENCE,'desktop.png'),fullPage:true});}
  for(const width of [900,600,414,360]) {
    await page.setViewportSize({width,height:900});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`No page overflow at ${width}px`);
    assert.equal(await page.locator('#configuration').isVisible(),true);
  }
  if(process.env.CSP_UI_EVIDENCE)await page.screenshot({path:path.join(process.env.CSP_UI_EVIDENCE,'mobile.png'),fullPage:true});
  await page.locator('#add-site').click();
  await page.keyboard.press('Tab');
  assert.equal(await page.evaluate(()=>document.activeElement.closest('dialog')?.id),'site-dialog');
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('#site-dialog').isVisible(),false);
  assert.deepEqual(errors,[]);
  await page.close();
});
test('custom site add/edit/remove validates statuses and never changes built-in validator', async browser => {
  const {page,calls,errors}=await setup(browser,{'/api/settings':payload=>payload});
  await page.locator('#add-site').click();
  await page.locator('#site-name').fill('TEST <img src=x onerror="window.injected=1">');
  await page.locator('#site-url').fill('https://example.org/public');
  await page.locator('#site-statuses').fill('99,600');
  await page.locator('#site-form button[type=submit]').click();
  assert.equal(await page.locator('#site-error').isVisible(),true);
  await page.locator('#site-statuses').fill('200, 204,200');
  await page.locator('#site-form button[type=submit]').click();
  assert.equal(await page.locator('#site-dialog').isVisible(),false);
  const custom = page.locator('#site-list .site-row').last();
  assert.equal(await custom.locator('input').isChecked(),true);
  assert.equal(await custom.locator('img').count(),0);
  await custom.getByRole('button',{name:/编辑/}).click();
  await page.locator('#site-name').fill('TEST edited site');
  await page.locator('#site-form button[type=submit]').click();
  await page.locator('#save-button').click();
  await waitFor(()=>calls.some(call=>call.endpoint==='/api/settings'),'Save custom site');
  const saved=calls.find(call=>call.endpoint==='/api/settings').payload;
  const site=saved.sites.at(-1);
  assert.equal(site.name,'TEST edited site');
  assert.deepEqual(site.statuses,[200,204]);
  assert.equal(site.validator,'none');
  assert.equal(saved.sites[0].validator,'chatgpt-trace');
  assert.equal(await page.locator('#site-list .site-row').first().locator('button').count(),0);
  await waitFor(async()=>!(await page.locator('#save-button').isDisabled()),'Save completion');
  page.once('dialog',dialog=>dialog.accept());
  await page.locator('#site-list .site-row').last().getByRole('button',{name:/移除/}).click();
  assert.equal(await page.locator('#site-list .site-row').count(),2);
  assert.equal(await page.evaluate(()=>window.injected),undefined);
  assert.deepEqual(errors,[]);
  await page.close();
});
test('bootstrap and POST API failures are visible, and failed save cannot start a job', async browser => {
  let current=await setup(browser,{'/api/bootstrap':{httpStatus:403,error:'TEST 请重新打开本地工具'}});
  await waitFor(async()=>await current.page.locator('#notice').isVisible(),'Bootstrap error must be visible');
  assert.match(await current.page.locator('#notice-text').innerText(),/TEST 请重新打开/);
  assert.equal(await current.page.locator('#start-button').isDisabled(),true);
  await current.page.close();
  current=await setup(browser,{'/api/preview':{httpStatus:400,error:'TEST 找不到核心配置'},'/api/settings':{httpStatus:400,error:'TEST 保存失败'}});
  await current.page.locator('#preview-button').click();
  await waitFor(async()=>/TEST 找不到/.test(await current.page.locator('#notice-text').innerText()),'Preview failure must display backend text');
  assert.equal(await current.page.locator('#preview-button').isDisabled(),false);
  await current.page.locator('#start-button').click();
  await waitFor(async()=>/TEST 保存失败/.test(await current.page.locator('#notice-text').innerText()),'Failed save error must display');
  assert.equal(current.calls.filter(call=>call.endpoint==='/api/start').length,0);
  assert.equal(await current.page.locator('#start-button').isDisabled(),false);
  assert.deepEqual(current.errors,[]);
  await current.page.close();
});
test('a slow initial idle poll cannot overwrite a newly started job', async browser => {
  let running=false,jobCalls=0;
  const {page,calls}=await setup(browser,{
    '/api/settings':payload=>payload,
    '/api/start':()=>{running=true;return {id:'test-new',running:true};},
    '/api/job':async()=>{jobCalls++;if(jobCalls===1){await new Promise(resolve=>setTimeout(resolve,450));return {id:null,running:false,events:[],report:null,error:null,progress:{completed:0,total:0}};}return {id:'test-new',running,events:[],report:null,error:null,progress:{completed:0,total:3}};}
  });
  await waitFor(()=>jobCalls===1,'Initial poll started');
  await page.locator('#start-button').click();
  await waitFor(()=>calls.some(call=>call.endpoint==='/api/start'),'New job starts while initial GET pending');
  await page.waitForTimeout(550);
  assert.equal(await page.locator('#start-button').isDisabled(),true,'Stale idle snapshot cannot unlock a running job');
  await waitFor(()=>jobCalls>=2,'New job must continue polling after stale response');
  await page.close();
});
if(process.env.CSP_SERVER_PYTHON) test('live backend authenticates launch, persists UI settings, and reports missing config without demo data', async browser => {
  const {spawn}=require('node:child_process');
  assert.ok(process.env.CSP_UI_EVIDENCE,'CSP_UI_EVIDENCE must point to a scratch directory for live-server tests');
  const dataDir=path.join(process.env.CSP_UI_EVIDENCE,'live-data-'+Date.now());
  const child=spawn(process.env.CSP_SERVER_PYTHON,['-u','-c','from pathlib import Path; import sys,server; h=server.make_server(data_dir=Path(sys.argv[1])); print(h.url,flush=True); h.serve_forever()',dataDir],{cwd:path.join(__dirname,'..'),stdio:['ignore','pipe','pipe']});
  let stderr='';child.stderr.on('data',chunk=>stderr+=chunk.toString());
  const page=await browser.newPage();page.setDefaultTimeout(5000);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  try {
    const url=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(new Error('Live backend startup timed out: '+stderr)),8000);child.stdout.on('data',chunk=>{output+=chunk.toString();const match=output.match(/http:\/\/127\.0\.0\.1:\d+\/\?launch=[^\s]+/);if(match){clearTimeout(timer);resolve(match[0]);}});child.on('error',error=>{clearTimeout(timer);reject(error);});child.on('exit',code=>{clearTimeout(timer);reject(new Error('Live backend exited '+code+': '+stderr));});});
    await page.setViewportSize({width:1280,height:900});
    await page.goto(url);
    await waitFor(async()=>!(await page.locator('#save-button').isDisabled()),'Live bootstrap must complete');
    assert.equal(new URL(page.url()).search,'','One-time launch capability must be removed from URL');
    assert.equal(await page.locator('input[data-site-id="chatgpt"]').isChecked(),true);
    assert.equal(await page.locator('#export-json').getAttribute('aria-disabled'),'true');
    await page.locator('#rounds').fill('2');
    await page.locator('#include').fill('本机 UI smoke');
    await page.locator('.advanced summary').click();
    const missingPath=path.join(dataDir,'does-not-exist.yaml');
    await page.locator('#config_path').fill(missingPath);
    await page.locator('#save-button').click();
    await waitFor(async()=>/设置已保存/.test(await page.locator('#notice-text').innerText()),'Actual settings API must save');
    const saved=await page.evaluate(async()=>(await fetch('/api/bootstrap')).json());
    assert.equal(saved.options.rounds,2);
    assert.equal(saved.options.include,'本机 UI smoke');
    assert.equal(saved.connection.config_path,missingPath);
    const persisted=JSON.parse(fs.readFileSync(path.join(dataDir,'settings.json'),'utf8'));
    assert.deepEqual(saved.options,persisted.options);
    await page.reload();
    await waitFor(async()=>!(await page.locator('#save-button').isDisabled()),'Reload after live save');
    assert.equal(await page.locator('#rounds').inputValue(),'2');
    assert.equal(await page.locator('#include').inputValue(),'本机 UI smoke');
    await page.screenshot({path:path.join(process.env.CSP_UI_EVIDENCE,'live-desktop.png'),fullPage:true});
    await page.locator('#preview-button').click();
    await waitFor(async()=>await page.locator('#notice.error').isVisible(),'Missing config must return a visible actual server error');
    assert.equal(await page.locator('#result-rows tr').count(),0);
    assert.deepEqual(errors,[]);
  } finally {await page.close();child.kill();}
});
test('reloading a failed job retains its partial rows without mixing the previous report', async browser => {
  const row={name:'TEST partial failed job',region:'sg',provider:'TEST provider',site_id:'chatgpt',site_name:'ChatGPT',url:'https://chatgpt.com/cdn-cgi/trace',success_rate:0,successes:0,total:1,median_ms:null,jitter_ms:null,samples:[{ok:false,status:502,ttfb_ms:null,total_ms:10,reason:'TEST connection failed'}],eligible:false};
  const previous={created_at:'2026-10-14T10:00:00+08:00',rows:[{...row,name:'TEST old report'}],recommendations:[{site_id:'chatgpt',site_name:'ChatGPT',name:'TEST stale',median_ms:1,success_rate:1}],warnings:[],note:'TEST old',options:bootstrap.options};
  const {page}=await setup(browser,{
    '/api/bootstrap':{...bootstrap,last_report:previous},
    '/api/job':{id:'test-failed',running:false,events:[{seq:1,event:'row',row,completed:1,total:2},{seq:2,event:'error',text:'TEST job failed'}],report:null,error:'TEST job failed',progress:{completed:1,total:2}}
  });
  await waitFor(async()=>/TEST job failed/.test(await page.locator('#notice-text').innerText()),'Failed job must show error');
  assert.equal(await page.locator('#result-rows tr').count(),1,'Only this job partial row should remain');
  assert.match(await page.locator('#result-rows').innerText(),/TEST partial failed job/);
  assert.equal(await page.locator('#recommendations').isVisible(),false);
  assert.equal(await page.locator('#export-json').getAttribute('aria-disabled'),'false','Old complete export remains accessible');
  await page.close();
});
(async()=>{
  const server = http.createServer((req,res)=>{
    res.setHeader('Content-Type','text/html; charset=utf-8');
    res.end(fs.existsSync(htmlPath)?fs.readFileSync(htmlPath):'<p>UI not implemented</p>');
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  global.baseURL = `http://127.0.0.1:${server.address().port}/`;
  const browser = await chromium.launch({channel:process.env.CSP_BROWSER_CHANNEL || 'chrome',headless:true});
  let failed=0;
  try {
    for(const {name,fn} of tests) {
      try { await fn(browser); console.log(`PASS ${name}`); }
      catch(error) { failed++; console.error(`FAIL ${name}\n${error.stack}`); }
    }
  } finally { await browser.close(); await new Promise(resolve=>server.close(resolve)); }
  console.log(`${tests.length-failed}/${tests.length} UI tests passed`);
  process.exitCode = failed?1:0;
})().catch(error=>{console.error(error);process.exitCode=1;});
