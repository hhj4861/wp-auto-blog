const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const script=fs.readFileSync('src/category_reader.js','utf8');
const html=`<body class="single-post postid-999"><div class="wpab-menu-reader" data-reader-category="건강">
<section id="quick-answer"><p>핵심 답변</p></section><nav data-reader-menu><a href="#quick-answer">전체 보기</a><a href="#overview">이해</a><a href="#details">상세</a></nav>
<div data-reader-panels><section data-reader-panel id="overview"><h2>이해</h2><p>설명</p></section><section data-reader-panel id="details"><h2>상세</h2><ul data-visual="checklist"><li>개인 점검</li></ul></section></div>
<div data-monetization="ad"><a href="https://ad.example/">광고</a><ins data-ad-slot="test"></ins></div>
<section id="verified-sources"><a href="https://official.example/path?private=value">공식 자료</a></section>
<div data-monetization="related"><a href="https://trendpulse.blog/other/">관련 글</a></div>
<a rel="sponsored" href="https://retailer.example/buy?private=value">제휴</a></div></body>`;
const dom=new JSDOM(html,{url:'https://trendpulse.blog/test/?private=value',runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window,d=w.document,calls=[],timers=new Map();let seq=0,visibility='visible',observer;
w.scrollBy=()=>{};w.requestAnimationFrame=()=>0;
w.setTimeout=fn=>{timers.set(++seq,fn);return seq};w.clearTimeout=id=>timers.delete(id);
Object.defineProperty(d,'visibilityState',{get:()=>visibility});
w.IntersectionObserver=class{constructor(cb){observer=this;this.cb=cb;this.nodes=[];}observe(n){this.nodes.push(n)}};
w.gtag=(...args)=>calls.push(args);
w.eval(script);d.dispatchEvent(new w.Event('DOMContentLoaded'));
function expose(nodes){observer.cb(nodes.map(target=>({target,isIntersecting:true,intersectionRatio:1})));}
function tick(){for(const [id,fn] of [...timers]){timers.delete(id);fn();}}
const tabs=[...d.querySelectorAll('[role=tab]')],headings=[...d.querySelectorAll('[data-reader-panel] h2')],summary=d.querySelector('#quick-answer p');
assert.equal(calls.length,0);
expose([summary,headings[0]]);assert.equal(calls.length,0);tick();
assert.deepEqual(calls.map(c=>c[1]),['summary_view','reader_section_view']);
expose([summary,headings[0]]);tick();assert.equal(calls.length,2);
tabs[1].click();expose([headings[1]]);tick();
assert.equal(calls.filter(c=>c[1]==='reader_section_view').length,1); // hidden detail never counted
assert.equal(calls.at(-1)[1],'reader_menu_select');
tabs[2].click();expose([headings[1]]);visibility='hidden';d.dispatchEvent(new w.Event('visibilitychange'));tick();
assert.equal(calls.filter(c=>c[1]==='reader_section_view').length,1);
visibility='visible';d.dispatchEvent(new w.Event('visibilitychange'));tick();
assert.equal(calls.filter(c=>c[1]==='reader_section_view').length,2);
const before=calls.length;d.querySelector('input').click();assert.equal(calls.length,before); // private checks excluded
for(const link of d.querySelectorAll('a')){link.addEventListener('click',e=>e.preventDefault());link.click();}
assert.equal(calls.filter(c=>c[1]==='official_source_click').length,1);
assert.equal(calls.filter(c=>c[1]==='affiliate_outbound_click').length,1);
assert.equal(calls.filter(c=>c[1]==='related_article_click').length,1);
assert.ok(!JSON.stringify(calls).includes('private'));
assert.ok(calls.every(c=>c[2].article_id==='999' && c[2].article_category==='건강'));
assert.equal(d.querySelectorAll('ins[data-ad-slot="test"]').length,1);
const count=calls.length;w.wpabReaderMeasurement=false;tabs[0].click();assert.equal(calls.length,count);
w.wpabReaderMeasurement=true;delete w.gtag;assert.doesNotThrow(()=>tabs[1].click());
assert.equal(w.localStorage.length,0);assert.equal(w.sessionStorage.length,0);
w.eval(script);assert.equal(d.querySelectorAll('input').length,1);
dom.window.close();
console.log('PASS: active exposure, hidden/duplicate exclusion, GA dispatch, click classes, no private check/query data or ad changes');
