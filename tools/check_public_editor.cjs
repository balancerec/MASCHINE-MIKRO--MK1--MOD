const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const url=process.env.MK1_TEST_URL||'http://127.0.0.1:8766/control-studio/dist/';
 assert.equal(new URL(url).hostname,'127.0.0.1');
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url);
  await page.waitForFunction(()=>document.querySelector('#fl-native-status')?.textContent.includes('opcional'));
  assert.equal(await page.locator('.control[data-id]').count(),45);
  assert.equal(await page.locator('#fl-native-load').isDisabled(),true);
  assert.deepEqual(errors,[]);
  console.log('Clean public editor: 45 controls, optional template handled, no page errors.');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
