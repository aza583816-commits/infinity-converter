/* Runs browser-tool calculation handlers in a Node VM with synthetic form fields.
 * This verifies calculations/wiring, not layout, canvas, clipboard or downloads.
 * Generate catalog: python scripts/export_browser_catalog.py /path/catalog.json
 */
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const { webcrypto } = require('node:crypto');
const source = fs.readFileSync(path.join(__dirname, '../static/js/app.js'), 'utf8');
const start = source.indexOf('const browserWorkspace =');
const end = source.indexOf('/* Infinity 7.0 — one contextual', start);
if (start < 0 || end < 0) throw Error('Browser handler entry points missing');
const catalog = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const excludedReasons = new Map([
  ['light-background-cleanup', 'requires real browser canvas'],
  ['focus-timer', 'requires a real browser timer lifecycle'],
  ['html-entity-converter', 'requires browser DOMParser'],
  ['html-tag-stripper', 'requires browser DOMParser'],
]);
const samples = {
  'deadline-countdown': {deadline: new Date(Date.now()+86400000).toISOString().slice(0,16)},
  'jwt-decoder': {token:'eyJhbGciOiJub25lIn0.eyJzdWIiOiJ0ZXN0In0.'},
  'participation-tracker': {entries:'Alice,2\nBob,3'},
  'gpa-calculator': {courses: 'A,3\nB,3'},
  'weighted-grade-calculator': {items: '80,50\n100,50'},
  'temperature-converter': {value:'0',from:'c',to:'f'},
  'percentage-change': {old:'100',new:'125'},
  'word-character-counter': {text:'Hello world'},
  'query-string-parser-builder': {query:'name=Infinity&lang=en'},
};
const expected = {
  'gpa-calculator': /GPA: 3\.50/,
  'weighted-grade-calculator': /90%/,
  'temperature-converter': /32 F/,
  'percentage-change': /25%/,
  'word-character-counter': /Words: 2/,
  'query-string-parser-builder': /name|Infinity/,
};
(async () => {
  const results=[];
  for (const tool of catalog) {
    if (excludedReasons.has(tool.id)) {
      results.push({id:tool.id,status:'not_tested',reason:excludedReasons.get(tool.id)});
      continue;
    }
    const fields = {};
    for (const field of tool.fields) {
      const fallback = field.type === 'datetime-local' ? '2026-09-01T10:00' : field.type === 'date' ? '2026-09-01' : field.type === 'number' ? '10' : 'Example';
      fields['#browser-'+field.key] = {value: String(samples[tool.id]?.[field.key] ?? (field.value || field.placeholder || fallback))};
    }
    const output={value:''}; const run={addEventListener:(_event,cb)=>run.click=cb};
    Object.assign(fields,{'#browser-output':output,'#browser-run':run,'#browser-download':{hidden:true,dataset:{}},'#browser-copy':{addEventListener:()=>{}}});
    const context = vm.createContext({
      document:{querySelector:()=>({dataset:{browserTool:tool.id}})},
      $:key=>fields[key], crypto:webcrypto, TextDecoder, TextEncoder, atob, btoa,
      URL, URLSearchParams, Blob, setInterval:()=>1, clearInterval:()=>{}, navigator:{}, console,
    });
    try {
      vm.runInContext(source.slice(start,end),context,{timeout:2000});
      await run.click();
      const value=String(output.value);
      const runtimeError = /\b(?:ReferenceError|TypeError|SyntaxError):|\bis not defined\b/.test(value);
      const invalidNumber = /(?:^|[\s:=])(?:NaN|[-+]?Infinity)(?=$|[\s,;])/.test(value);
      if (!value || runtimeError || invalidNumber || /unavailable|Enter |Choose |Invalid|must be|Use grades|at least/.test(value)) throw Error(value || 'empty result');
      if (expected[tool.id] && !expected[tool.id].test(value)) throw Error('incorrect known answer: '+value);
      results.push({id:tool.id,status:'passed',sample_output:value.slice(0,250),known_answer:Boolean(expected[tool.id])});
    } catch(error) {results.push({id:tool.id,status:'failed',reason:error.message.slice(0,250)});}
  }
  console.log(JSON.stringify(results,null,2));
  const failed=results.filter(r=>r.status==='failed');
  const passed=results.filter(r=>r.status==='passed').length;
  const notTested=results.filter(r=>r.status==='not_tested').length;
  console.error(`VM ${passed}/${catalog.length} passed; ${failed.length} failed; ${notTested} not tested`);
  if(failed.length) process.exitCode=1;
})();
