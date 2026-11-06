const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage();const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  const packets=JSON.parse(fs.readFileSync(path.join(__dirname,'tests/fixtures/encoder-ten-right.json'),'utf8')).packets;
  const events=packets.map((bytes,index)=>({seq:index+1,report:1,bytes,changed:[5]}));
  // Only this isolated browser receives replay data. No device endpoint is called.
  await page.route('**/api/status',route=>route.fulfill({json:{connected:false,events,packets:0,writes:0}}));
  await page.goto('http://127.0.0.1:8765/');
  await page.waitForFunction(()=>document.querySelector('#usb-encoder')?.textContent.includes('saldo 10'));
  const text=await page.locator('#usb-encoder').textContent();
  assert.match(text,/clique solto/);assert.match(text,/posição 0\/15/);
  assert.deepEqual(errors,[]);
  console.log('Browser replay passed: '+text);
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
