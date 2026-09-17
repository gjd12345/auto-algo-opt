// Real Chromium rendering and interaction checks; Node built-ins only.
const fs = require('node:fs');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {pathToFileURL} = require('node:url');
const assert = require('node:assert/strict');
const root=__dirname, profile=path.join(root,'.edge-profile');
const target=path.resolve(process.argv[2]||'knowledge_store/releases/20260914-main-d6433549-kb-v0/dashboard.html');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 fs.mkdirSync(profile,{recursive:true});
 const active=path.join(profile,'DevToolsActivePort');
 if(fs.existsSync(active))fs.unlinkSync(active);
 const child=spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',[
  '--headless','--disable-gpu','--no-first-run','--no-default-browser-check',
  '--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'
 ],{windowsHide:true,stdio:'ignore'});
 let ws;
 try{
  for(let i=0;i<100&&!fs.existsSync(active);i++)await sleep(100);
  assert(fs.existsSync(active),'Edge debugging endpoint must start');
  const port=fs.readFileSync(active,'utf8').split('\n')[0];
  const pages=await (await fetch('http://127.0.0.1:'+port+'/json')).json();
  ws=new WebSocket(pages.find(x=>x.type==='page').webSocketDebuggerUrl);
  await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
  let seq=0;const calls=new Map(),errors=[];
  ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const c=calls.get(m.id);if(c){calls.delete(m.id);m.error?c.reject(m.error):c.resolve(m.result);}}if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);};
  const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq;calls.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
  const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
  await send('Page.enable');await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  await send('Page.navigate',{url:pathToFileURL(target).href});
  for(let i=0;i<50;i++){await sleep(100);if(await evaluate("!!document.querySelector('#cards .card')"))break;}
  const initial=await evaluate("({cards:document.querySelectorAll('#cards .card').length,title:document.querySelector('#readerTitle')?.textContent,overflow:document.documentElement.scrollWidth>innerWidth,expanded:document.querySelectorAll('.family-group[open]').length})");
  assert(initial.cards>0);assert(initial.title);assert.equal(initial.overflow,false);assert.equal(initial.expanded,0);
  const capture=async name=>{const s=await send('Page.captureScreenshot',{format:'png'});fs.writeFileSync(path.join(root,name),Buffer.from(s.data,'base64'));};
  await capture('desktop.png');
  const code=await evaluate("md('~~~python\\nif x < 2:\\n    print(x)\\n~~~\\n\\nAfter code')");
  assert(code.includes('<pre><code>if x &lt; 2:'));assert(code.includes('</code></pre><p>After code</p>'));assert.equal((code.match(/<pre>/g)||[]).length,1);
  assert(!(await evaluate("md('<img src=x onerror=alert(1)>')")).includes('<img'));
  assert.equal(await evaluate("safeURL('javascript:alert(1)')"),'');
  await evaluate("document.querySelector('[data-family=tsp]').click()");
  const before=await evaluate("({family,kind,problem,count:filtered().length})");
  await evaluate("document.querySelector('#cards .card').click()");
  assert.deepEqual(await evaluate("({family,kind,problem,count:filtered().length})"),before);
  await evaluate("document.querySelector('[data-view=sources]').click()");
  assert(await evaluate("!document.querySelector('#sourceView').hidden && document.querySelectorAll('#sourceView .source-card').length>0"));
  await evaluate("document.querySelector('[data-view=coverage]').click()");
  assert(await evaluate("!document.querySelector('#coverageView').hidden"));
  await evaluate("document.querySelector('[data-view=methods]').click()");
  await evaluate("byId('q').value='2-opt';byId('q').dispatchEvent(new Event('input'))");
  assert((await evaluate("filtered().length"))>0);
  await evaluate("byId('clearSearch').click()");
  const id=await evaluate("Object.values(DATA).find(x=>x.body.includes('~~~')||x.body.includes(String.fromCharCode(96).repeat(3)))?.id");
  if(id){await evaluate("openEntry("+JSON.stringify(id)+")");assert(await evaluate("!!document.querySelector('#reader pre code')"));}
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await evaluate("closeReader()");
  assert(await evaluate("getComputedStyle(byId('familyFilter')).display!=='none'"));
  assert.equal(await evaluate("document.documentElement.scrollWidth>innerWidth"),false);
  await capture('mobile-list.png');
  await evaluate("document.querySelector('#cards .card').click()");
  assert(await evaluate("byId('reader').classList.contains('open')"));
  await capture('mobile-reader.png');
  await evaluate("document.querySelector('[data-close]').click()");
  assert.equal(await evaluate("byId('reader').classList.contains('open')"),false);
  assert.equal(errors.length,0);
  const review={};
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
  review.filteredReader=await evaluate("family='tsp';problem='all';kind='method';query='';apply();openEntry(filtered()[0].id);document.querySelector('[data-family=cvrp]').click();({listFamily:family,readerFamily:DATA[openId].family,selectedVisible:filtered().some(d=>d.id===openId)})");
  review.hiddenRelation=await evaluate("const cross=Object.values(DATA).find(d=>d.family==='tsp'&&d.kind==='implementation');openEntry(cross.id);({kindFilter:kind,familyFilter:family,readerKind:DATA[openId].kind,readerFamily:DATA[openId].family,selectedVisible:filtered().some(d=>d.id===openId)})");
  await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  review.mobileSubproblem=await evaluate("closeReader();({treeVisible:getComputedStyle(document.querySelector('.tree')).display!=='none',problemSelectorsOutsideTree:document.querySelectorAll('select[data-problem], .toolbar [data-problem]').length})");
  review.mobileClose=await evaluate("openEntry(Object.values(DATA).sort((a,b)=>b.body.length-a.body.length)[0].id);byId('reader').scrollTop=byId('reader').scrollHeight;(()=>{const r=document.querySelector('[data-close]').getBoundingClientRect();return {closeTop:r.top,closeVisible:r.bottom>0&&r.top<innerHeight,scrollTop:byId('reader').scrollTop};})()");
  fs.writeFileSync(path.join(root,'review-probes.json'),JSON.stringify(review,null,2));
  console.log(JSON.stringify(review));

  fs.writeFileSync(path.join(root,'browser-results.json'),JSON.stringify({target,initial,passed:['desktop-layout','collapsed-taxonomy','fenced-code','html-escaping','safe-links','stable-filters','sources-view','coverage-view','keyword-search','code-entry-rendering','mobile-layout','mobile-open-close'],errors},null,2));
  console.log('PASS: desktop, mobile, reading, filtering, source views, markdown safety; no browser exceptions.');
  await send('Browser.close').catch(()=>{});ws.close();
 }finally{if(ws)ws.close();child.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
