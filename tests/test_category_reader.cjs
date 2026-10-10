// DOM interaction checks only; this does not claim browser layout validation.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');
const script = fs.readFileSync('src/category_reader.js', 'utf8');
const article = n => `<div class="wpab-menu-reader"><nav data-reader-menu>
<a href="#p-${n}-1">이해</a><a href="#p-${n}-2">점검</a><a href="#quick-answer">전체 보기</a></nav>
<div data-reader-panels><section data-reader-panel><h2 id="p-${n}-1">이해</h2><p>중요 본문</p><a href="#p-${n}-2">점검 이동</a></section>
<section data-reader-panel><h2 id="p-${n}-2">점검</h2><ul data-visual="checklist"><li>공식 안내 확인</li><li>실제 설정 확인</li></ul><details><summary>질문</summary><p>답변</p></details></section></div></div>`;
const dom = new JSDOM(article(1) + article(2), {url:'https://example.org/post/#p-1-2', runScripts:'outside-only'});
const {window:w} = dom, d = w.document;
w.eval(script);d.dispatchEvent(new w.Event('DOMContentLoaded'));
const articles = [...d.querySelectorAll('.wpab-menu-reader')];
const first=articles[0], panels=[...first.querySelectorAll('[data-reader-panel]')], tabs=[...first.querySelectorAll('[role="tab"]')];
assert.equal(tabs.length,3);
assert.equal(panels[1].hidden,false); // initial deep link opens hidden destination
assert.equal(panels[0].hidden,true);
first.querySelector('input').click();
assert.equal(first.querySelector('.wpab-check-progress').textContent,'1 / 2 확인');
tabs[0].click();assert.equal(panels[0].hidden,false);assert.equal(panels[1].hidden,true);
first.querySelector('a').click();assert.equal(panels[1].hidden,false);
tabs[2].click();assert.ok(panels.every(p=>!p.hidden));
assert.equal(first.querySelector('input').checked,true);
assert.equal(articles[1].querySelector('input').checked,false);
assert.equal(w.localStorage.length,0);assert.equal(w.sessionStorage.length,0);
tabs[2].dispatchEvent(new w.KeyboardEvent('keydown',{key:'Home',bubbles:true}));
assert.equal(d.activeElement,tabs[0]);assert.equal(tabs[0].getAttribute('aria-selected'),'true');
tabs[0].dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true}));
assert.equal(d.activeElement,tabs[2]);assert.ok(panels.every(p=>!p.hidden));
const ids=[...d.querySelectorAll('[id]')].map(n=>n.id);assert.equal(ids.length,new Set(ids).size);
for(const tab of d.querySelectorAll('[role="tab"]'))assert.ok(d.getElementById(tab.getAttribute('aria-controls')));
w.eval(script);assert.equal(d.querySelectorAll('input').length,4); // repeated initializer is harmless
w.close();
console.log('PASS: default/deep-link panels, all view, keyboard, personal checks, no storage, multiple instances, repeat init');
