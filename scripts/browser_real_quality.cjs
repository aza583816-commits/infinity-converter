/* Real Chromium regression tests for the four browser-only tools that cannot
 * be exercised by the Node VM smoke suite. Uses synthetic files/data only.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright-core');

const source = fs.readFileSync(path.join(__dirname, '../static/js/app.js'), 'utf8');
const start = source.indexOf('const browserWorkspace =');
const end = source.indexOf('/* Infinity 7.0 — one contextual', start);
if (start < 0 || end < start) throw Error('Browser workspace code not found');
const script = 'const $ = (selector) => document.querySelector(selector);\n' + source.slice(start, end);
const tests = [
  { id: 'html-tag-stripper', fields: { text: '<p>First <b>bold</b> &amp; safe</p>' } },
  { id: 'html-entity-converter', fields: { text: '&lt;b&gt;سلام&lt;/b&gt; &amp; World' } },
  { id: 'focus-timer', fields: { minutes: '0.05' } },
  { id: 'light-background-cleanup', fields: { image: '' } },
];

async function pageFor(browser, spec) {
  const page = await browser.newPage();
  const fields = Object.entries(spec.fields).map(([key, value]) =>
    key === 'image' ? '<input type="file" id="browser-image">' :
    '<textarea id="browser-' + key + '"></textarea>').join('');
  await page.setContent('<main data-browser-tool="' + spec.id + '"></main>' + fields +
    '<textarea id="browser-output"></textarea><button id="browser-run">Run</button>' +
    '<a id="browser-download" hidden></a><button id="browser-copy"></button>');
  for (const [key, value] of Object.entries(spec.fields)) if (key !== 'image')
    await page.locator('#browser-' + key).fill(value);
  await page.addScriptTag({ content: script });
  return page;
}

async function main() {
  const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--no-sandbox'] });
  let completed = 0;
  try {
    for (const spec of tests) {
      const page = await pageFor(browser, spec);
      try {
        if (spec.id === 'light-background-cleanup') {
          const result = await page.evaluate(async () => {
            const canvas = document.createElement('canvas');
            canvas.width = 3; canvas.height = 1;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, 1, 1);
            ctx.fillStyle = '#000000'; ctx.fillRect(1, 0, 1, 1);
            ctx.fillStyle = '#e6e6e6'; ctx.fillRect(2, 0, 1, 1);
            const file = await new Promise(resolve => canvas.toBlob(blob => resolve(new File([blob], 'pixels.png', { type: 'image/png' }))));
            Object.defineProperty(document.querySelector('#browser-image'), 'files', { configurable: true, value: [file] });
            document.querySelector('#browser-run').click();
            await new Promise((resolve, reject) => {
              const started = Date.now();
              const poll = () => {
                if (!document.querySelector('#browser-download').hidden) return resolve();
                if (Date.now() - started > 5000) return reject(new Error(document.querySelector('#browser-output').value || 'No result'));
                setTimeout(poll, 30);
              }; poll();
            });
            const link = document.querySelector('#browser-download');
            const rendered = await createImageBitmap(await (await fetch(link.href)).blob());
            const target = document.createElement('canvas');
            target.width = 3; target.height = 1;
            const context = target.getContext('2d');
            context.drawImage(rendered, 0, 0);
            const pixels = [...context.getImageData(0, 0, 3, 1).data];
            URL.revokeObjectURL(link.href);
            return { text: document.querySelector('#browser-output').value, pixels };
          });
          assert.match(result.text, /3 x 1px/);
          assert.equal(result.pixels[3], 0, 'Pure white must become transparent');
          assert.equal(result.pixels[7], 255, 'Dark foreground must remain opaque');
          assert(result.pixels[11] > 0 && result.pixels[11] < 255, 'Near-white background must be partially transparent');
        } else if (spec.id === 'focus-timer') {
          await page.clock.install();
          await page.locator('#browser-run').click();
          assert.match(await page.locator('#browser-output').inputValue(), /0:03/);
          await page.clock.runFor(1000);
          assert.match(await page.locator('#browser-output').inputValue(), /0:02/);
          await page.clock.runFor(2500);
          assert.equal(await page.locator('#browser-output').inputValue(), 'Focus session complete.');
        } else {
          await page.locator('#browser-run').click();
          const value = await page.locator('#browser-output').inputValue();
          if (spec.id === 'html-tag-stripper') assert.equal(value, 'First bold & safe');
          else assert.equal(value, '<b>سلام</b> & World');
        }
        completed++;
        console.log('CHROMIUM QUALITY PASS ' + spec.id);
      } finally { await page.close(); }
    }
    assert.equal(completed, tests.length);
    console.log('CHROMIUM RESULT ' + completed + '/' + tests.length + ' passed');
  } finally { await browser.close(); }
}

main().catch(err => { console.error(err); process.exitCode = 1; });
