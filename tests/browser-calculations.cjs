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
 // Lesson allocation must preserve the user's actual available time:
 // separately rounded percentage buckets previously totaled 51 for 50 minutes.
 for (const minutes of [1, 5, 30, 50, 120]) {
   const output=await calculate('lesson-timing-planner',{minutes});
   const groups=[...output.matchAll(/(?:Opening|Instruction|Practice|Review): (\d+) min/g)].map(x=>Number(x[1]));
   assert.equal(groups.length,4,'All four lesson sections must be present');
   assert(groups.every(Number.isInteger),'Allocated minutes must be integral');
   assert(groups.every(value=>value>=0),'No section may receive negative minutes');
   assert.equal(groups.reduce((a,b)=>a+b,0),minutes,'Lesson allocation must exactly fit available minutes');
 }
 assert.equal(await calculate('lesson-timing-planner',{minutes:50}),
   'Opening: 5 min\nInstruction: 33 min\nPractice: 8 min\nReview: 4 min');
 assert.match(await calculate('lesson-timing-planner',{minutes:1.5}),/whole number of minutes/);
 // Independently specified arithmetic examples, not checks for merely nonempty output.
 assert.equal(await calculate('score-to-percentage',{score:18,total:20}),'90%');
 assert.equal(await calculate('vat-calculator',{amount:100,rate:15}),'VAT: 15\nTotal: 115');
 assert.equal(await calculate('profit-margin-calculator',{cost:80,revenue:120}),'Profit: 40\nMargin: 33.33%');
 assert.equal(await calculate('break-even-calculator',{fixed:1000,price:25,variable:10}),'Break-even units: 67');
 assert.equal(await calculate('expense-splitter',{amount:250,people:5}),'Each person pays: 50');
 assert.equal(await calculate('discount-calculator',{price:100,rate:20}),'Discount: 20\nFinal price: 80');
 assert.equal(await calculate('commission-calculator',{sales:5000,rate:5}),'Commission: 250');
 assert.equal(await calculate('roi-calculator',{cost:1000,return:1250}),'ROI: 25%\nNet gain: 250');
 assert.equal(await calculate('tip-calculator',{bill:100,rate:15,people:2}),'Tip: 15\nTotal: 115\nPer person: 57.5');
 assert.equal(await calculate('date-difference',{start:'2026-09-01',end:'2026-09-11'}),'Difference: 10 days');
 assert.equal(await calculate('pace-calculator',{minutes:30,distance:5}),'Pace: 6:00 min/km');
 assert.equal(await calculate('fuel-cost-calculator',{distance:250,efficiency:8,price:2}),'Fuel needed: 20 L\nEstimated cost: 40');
 assert.equal(await calculate('bmi-calculator',{weight:70,height:175}),'BMI: 22.86\nCategory: Healthy range');
 console.log('Browser source-to-known-answer and exact lesson allocation regression cases passed');
})().catch(e=>{console.error(e);process.exitCode=1});
