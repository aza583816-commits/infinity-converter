/* Full-site browser acceptance: exercise the rendered page and real JS handler
 * for every browser tool and inspect every server tool page. Unlike the VM
 * matrix, this verifies assets, labels, buttons, DOM wiring and download UI
 * in actual Chromium. Functional response != a universal semantic oracle.
 */
const fs = require('node:fs');
const assert = require('node:assert/strict');
const { chromium } = require('playwright-core');

const origin = process.env.IC_E2E_BASE_URL || 'http://127.0.0.1:5000';
const browsers = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const serverTools = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const samples = {
  'deadline-countdown': {deadline:'2026-12-01T10:00'},
  'jwt-decoder': {token:'eyJhbGciOiJub25lIn0.eyJzdWIiOiJ0ZXN0In0.'},
  'participation-tracker': {entries:'Alice,2\nBob,3'},
  'gpa-calculator': {courses:'A,3\nB,3'},
  'weighted-grade-calculator': {items:'80,50\n100,50'},
  'temperature-converter': {value:'0',from:'c',to:'f'},
  'percentage-change': {old:'100',new:'125'},
  'word-character-counter': {text:'Hello world'},
  'query-string-parser-builder': {query:'name=Infinity&lang=en'},
  'focus-timer': {minutes:'0.05'},
};
const known = {
  'gpa-calculator': /GPA: 3\.50/,
  'weighted-grade-calculator': /90%/,
  'temperature-converter': /32 F/,
  'percentage-change': /25%/,
  'word-character-counter': /Words: 2/,
};
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR30AAAAASUVORK5CYII=', 'base64');

function validText(v) {
  return Boolean(v) && !/\b(?:ReferenceError|TypeError|SyntaxError):|\bis not defined\b|unavailable|Enter |Choose |Invalid|must be|Use grades|at least/.test(v) &&
    !/(?:^|[\s:=])(?:NaN|[-+]?Infinity)(?=$|[\s,;])/.test(v);
}
async function main() {
  const browser = await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox']});
  const context = await browser.newContext({viewport:{width:390,height:844},acceptDownloads:true});
  const page = await context.newPage();
  const failures=[]; const report={origin,server_total:serverTools.length,browser_total:browsers.length,server_pass:0,browser_pass:0,browser_known_answers:0,failures};
  try {
    for (const entry of serverTools) {
      const id=entry.id;
      try {
        const res=await page.goto(origin+'/tool/'+encodeURIComponent(id),{waitUntil:'domcontentloaded',timeout:20000});
        assert.equal(res.status(),200,'tool HTTP response');
        assert.equal(await page.locator('#tool-id').inputValue(),id,'wrong tool rendered');
        assert(await page.locator('#converter-form button[type="submit"]').count()>0,'submit button missing');
        if (entry.input_required) assert(await page.locator('#files[type="file"]').count()===1,'file upload missing');
        report.server_pass++;
        console.log('SITE SERVER PAGE PASS '+id);
      } catch (error) { failures.push({id,scope:'server_page',reason:String(error).slice(0,260)});console.error('SITE SERVER PAGE FAIL '+id+': '+error.message); }
    }

    for (const tool of browsers) {
      const id=tool.id;
      try {
        const response=await page.goto(origin+'/browser-tools/'+encodeURIComponent(id),{waitUntil:'domcontentloaded',timeout:20000});
        assert.equal(response.status(),200,'browser tool HTTP response');
        assert.equal(await page.locator('[data-browser-tool]').getAttribute('data-browser-tool'),id,'wrong tool rendered');
        const button=page.locator('#browser-run');
        assert(await button.isVisible(),'run button hidden');
        for (const field of tool.fields) {
          const input=page.locator('#browser-'+field.key);
          assert.equal(await input.count(),1,'missing input '+field.key);
          if(field.type==='file') {
            await input.setInputFiles({name:'pixel.png',mimeType:'image/png',buffer:png});
          } else if(field.type==='select') {
            const sample=samples[id]?.[field.key];
            if(sample && await input.locator('option[value="'+sample+'"]').count())await input.selectOption(sample);
          } else {
            const fallback=field.type==='datetime-local'?'2026-12-01T10:00':field.type==='date'?'2026-12-01':field.type==='number'?'10':'Example';
            let value=String(samples[id]?.[field.key]??(field.value||field.placeholder||fallback));
            if(field.type==='number'&&!Number.isFinite(Number(value))) value='10';
            await input.fill(value);
          }
        }
        await button.click();
        await page.waitForFunction(()=>Boolean(document.querySelector('#browser-output')?.value?.trim())||!document.querySelector('#browser-download')?.hidden,null,{timeout:9000});
        const value=await page.locator('#browser-output').inputValue();
        const downloaded=!(await page.locator('#browser-download').isHidden());
        if(id==='light-background-cleanup') assert(downloaded,'image download link missing');
        else assert(validText(value),'invalid output: '+value.slice(0,200));
        if(known[id]) { assert(known[id].test(value),'wrong expected value: '+value); report.browser_known_answers++; }
        report.browser_pass++;
        console.log('SITE BROWSER TOOL PASS '+id);
      } catch(error) { failures.push({id,scope:'browser_tool',reason:String(error).slice(0,260)});console.error('SITE BROWSER TOOL FAIL '+id+': '+error.message); }
    }
    console.log('SITE E2E RESULT '+report.server_pass+'/'+serverTools.length+' server pages, '+report.browser_pass+'/'+browsers.length+' browser tools, '+report.browser_known_answers+' known-answer assertions');
    fs.writeFileSync(process.env.IC_E2E_REPORT||'/tmp/site-e2e-report.json',JSON.stringify(report,null,2));
    if(failures.length) process.exitCode=1;
  } finally {await browser.close();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
