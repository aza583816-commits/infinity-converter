const fs=require('node:fs');const vm=require('node:vm');const assert=require('node:assert/strict');const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/js/app.js'),'utf8');const code=source.slice(source.indexOf('const browserWorkspace ='),source.indexOf('/* Infinity 7.0 — one contextual'));
async function calculate(id,values){
 const output={value:''};const run={addEventListener:(_e,cb)=>run.click=cb};const fields={'#browser-output':output,'#browser-run':run};
 for(const [k,v] of Object.entries(values)) fields['#browser-'+k]={value:String(v)};
 const context=vm.createContext({document:{querySelector:()=>({dataset:{browserTool:id}})},$:key=>fields[key],clearInterval:()=>{}});
 vm.runInContext(code,context,{timeout:1000});await run.click();return output.value;
}
(async()=>{
 assert.match(await calculate('gpa-calculator',{courses:'A,3\nB,3'}),/GPA: 3\.50/);
 assert.match(await calculate('gpa-calculator',{courses:''}),/Enter at least one/);
 assert.match(await calculate('gpa-calculator',{courses:'A,-3'}),/positive credits/);
 assert.match(await calculate('weighted-grade-calculator',{items:'80,50\n100,50'}),/90%/);
 assert.match(await calculate('weighted-grade-calculator',{items:''}),/positive weights/);
 assert.match(await calculate('temperature-converter',{value:0,from:'c',to:'f'}),/32 F/);
 assert.match(await calculate('temperature-converter',{value:'',from:'c',to:'f'}),/valid number/);
 assert.match(await calculate('pace-calculator',{minutes:5.999,distance:1}),/6:00 min\/km/);
 assert.match(await calculate('study-session-planner',{minutes:30,topics:3}),/Topic 1: 6 minutes/);
 assert.match(await calculate('study-session-planner',{minutes:10,topics:5}),/fewer topics/);
 console.log('10 known-answer and negative browser-calculation tests passed');
})().catch(e=>{console.error(e);process.exitCode=1});
