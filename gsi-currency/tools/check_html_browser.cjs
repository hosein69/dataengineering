// Usage: GSI_CHROMIUM=/path/to/chromium node tools/check_html_browser.cjs samples/FULLSTACK_QA.html audit
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(process.env.GSI_PLAYWRIGHT||'playwright');
(async()=>{
 const input=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]||'audit');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:process.env.GSI_CHROMIUM||undefined,headless:true,args:process.env.GSI_CHROMIUM_ARGS?JSON.parse(process.env.GSI_CHROMIUM_ARGS):['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
 const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});let errors=[],checks=[];
 page.on('pageerror',e=>errors.push(e.message));
 try{
 await page.goto('file://'+input);
 assert.equal(await page.evaluate(()=>window.UNSAFE),undefined);checks.push('source comments safely escaped');
 const pane=page.locator('#pane_supply_material');assert(await pane.isVisible());
 assert.equal(await pane.locator('tbody[id] tr').count(),5);checks.push('material default tab and display cap');
 assert.equal(await page.evaluate(()=>rows(TAB_META[active]).length),175);checks.push('all 175 matches retained for aggregation/export');
 await page.locator('#q').fill('۱۷۰');assert.equal(await pane.locator('tbody[id] tr').count(),1);
 assert((await pane.innerText()).includes('MAT-170'));checks.push('Persian-digit search finds late material beyond cap');
 await page.locator('#q').fill('');
 let download=page.waitForEvent('download');await page.locator('#pane_supply_material [data-role="export"]').click();await (await download).saveAs(path.join(out,'browser_material.xlsx'));checks.push('material Excel download');
 await page.locator('button[data-pane="pane_financial"]').click();assert(await page.locator('#pane_financial').isVisible());assert(!(await pane.isVisible()));
 download=page.waitForEvent('download');await page.evaluate(()=>downloadFilteredXlsx());await (await download).saveAs(path.join(out,'browser_financial.xlsx'));checks.push('financial Excel download');
 const tab=page.locator('button[data-pane="pane_financial"]');await tab.focus();await tab.press('ArrowLeft');assert(await pane.isVisible());checks.push('RTL keyboard tab navigation');
 await page.screenshot({path:path.join(out,'desktop.png')});
 await page.setViewportSize({width:390,height:844});await pane.locator('.material-mobile').scrollIntoViewIfNeeded();
 assert(await pane.locator('.material-mobile').isVisible());assert(!(await pane.locator('.material-table').isVisible()));
 assert.equal(await pane.locator('.material-card').count(),5);assert((await pane.locator('.material-mobile').innerText()).includes('کامنت NTSW'));
 assert(await page.evaluate(()=>document.body.scrollWidth<=innerWidth));checks.push('390px mobile cards show both source comments without page overflow');
 await page.screenshot({path:path.join(out,'mobile.png')});assert.deepEqual(errors,[]);checks.push('no JavaScript runtime errors');
 fs.writeFileSync(path.join(out,'BROWSER_RESULTS.json'),JSON.stringify({status:'passed',checks,errors},null,2));console.log(JSON.stringify({status:'passed',checks},null,2));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
