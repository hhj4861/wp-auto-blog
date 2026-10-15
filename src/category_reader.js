/* Progressive enhancement: HTML retains every section if scripts are filtered. */
(() => {
  // Exposure is a visible heading/summary for one active second, never a completion claim.
  function installMeasurement(article, panels) {
    const id = [...document.body.classList].find(name => /^postid-[0-9]+$/.test(name));
    const categories = ['취업','건강','리뷰','생활정보','생산성','테크','뷰티','비즈니스'];
    if (!id) return {select:()=>{},refresh:()=>{}};
    const category = article.dataset.readerCategory;
    const base = {article_id:id.slice(7),article_category:categories.includes(category) ? category : 'other',reader_version:'measurement-v1'};
    function send(name, params = {}) {
      if (window.wpabReaderMeasurement === false || typeof window.gtag !== 'function') return false;
      try { window.gtag('event', name, {...base,...params}); return true; } catch (_) { return false; }
    }
    function sectionId(panel) {
      const value = panel.querySelector('section[id]')?.id || panel.id;
      return /^[a-zA-Z][a-zA-Z0-9_-]{0,79}$/.test(value) ? value : 'section';
    }
    const targets = [];
    const summary = article.querySelector('#quick-answer');
    if (summary) targets.push({node:summary.querySelector('p') || summary,name:'summary_view',section:'quick-answer'});
    panels.forEach(panel => { const node = panel.querySelector('h2') || panel;
      targets.push({node,panel,name:'reader_section_view',section:sectionId(panel)}); });
    const visible = new Set(), sent = new Set(), timers = new Map();
    function refresh() {
      targets.forEach(target => {
        const key = target.name + ':' + target.section;
        const eligible = document.visibilityState === 'visible' && visible.has(target.node) && !target.node.closest('[hidden]');
        if (!eligible && timers.has(key)) { clearTimeout(timers.get(key)); timers.delete(key); }
        if (eligible && !sent.has(key) && !timers.has(key)) {
          timers.set(key,setTimeout(() => {
            timers.delete(key);
            if (document.visibilityState === 'visible' && visible.has(target.node) && !target.node.closest('[hidden]') &&
                send(target.name,{section_id:target.section,view_mode:article.querySelector('.wpab-all-view') ? 'all' : 'single'})) sent.add(key);
          },1000));
        }
      });
    }
    if (typeof IntersectionObserver === 'function') {
      const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => { if (entry.isIntersecting && entry.intersectionRatio >= 0.5) visible.add(entry.target); else visible.delete(entry.target); });
        refresh();
      },{threshold:[0,0.5]});
      targets.forEach(target => observer.observe(target.node));
      document.addEventListener('visibilitychange',refresh);
      window.addEventListener('pagehide',() => {timers.forEach(clearTimeout);timers.clear();});
    }
    article.addEventListener('click',event => {
      const link = event.target.closest('a[href]');
      if (!link || link.closest('[data-monetization="ad"]')) return;
      let url; try {url = new URL(link.href,location.href);} catch (_) {return;}
      if (!['https:','http:'].includes(url.protocol)) return;
      let name;
      if (link.closest('#verified-sources')) name = 'official_source_click';
      else if ((link.rel || '').split(/\s+/).includes('sponsored') || link.matches('[data-affiliate]')) name = 'affiliate_outbound_click';
      else if (link.closest('[data-monetization="related"]') && url.origin === location.origin) name = 'related_article_click';
      if (name) send(name,{link_domain:url.hostname});
    });
    return {select:index => send('reader_menu_select',{section_id:index === 0 ? 'all' : sectionId(panels[index-1])}),refresh};
  }
  function start() {
    document.querySelectorAll('.wpab-menu-reader').forEach(article => {
      if (article.dataset.readerReady) return;
      const panels = [...article.querySelectorAll(':scope > [data-reader-panels] > [data-reader-panel]')];
      const nav = article.querySelector(':scope > [data-reader-menu]');
      const container = article.querySelector(':scope > [data-reader-panels]');
      if (!nav || !container || 2 > panels.length) return;
      const originalLinks = [...nav.querySelectorAll('a')];
      if (originalLinks.length !== panels.length + 1) return;
      // Both existing (all last) and new (all first) article markup are supported.
      const allLink = originalLinks.find(link => link.getAttribute('href') === '#quick-answer');
      if (!allLink) return;
      const links = [allLink, ...originalLinks.filter(link => link !== allLink)];
      // IDs generated per instance avoid collisions on multi-article pages.
      const prefix = 'wpab-reader-' + [...document.querySelectorAll('.wpab-menu-reader')].indexOf(article);
      container.id = prefix + '-all';
      panels.forEach((panel, i) => { if (!panel.id || [...document.querySelectorAll('[id]')].filter(node => node.id === panel.id).length > 1) panel.id = prefix + '-panel-' + i; });
      const tabs = links.map((link, i) => {
        const tab = document.createElement('button');
        tab.type = 'button'; tab.textContent = link.textContent;
        tab.id = prefix + '-tab-' + i;
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-controls', i === 0 ? container.id : panels[i - 1].id);
        link.replaceWith(tab); return tab;
      });
      // Flatten any paragraphs inserted around anchors by WordPress wpautop.
      nav.replaceChildren(...tabs);
      nav.setAttribute('role', 'tablist');
      const layout = document.createElement('div'); layout.className = 'wpab-reader-layout';
      nav.before(layout); layout.append(nav, container);
      function measure() {
        // Existing WordPress/advertising fixed bars must not cover the reader controls.
        let inset = 600 >= innerWidth ? 8 : 16;
        document.querySelectorAll('ins[data-anchor-status="displayed"], #wpadminbar').forEach(bar => {
          const rect = bar.getBoundingClientRect(), css = getComputedStyle(bar);
          if (css.position === 'fixed' && css.visibility !== 'hidden' && 1 >= rect.top && rect.bottom > 0 && innerHeight / 2 > rect.height)
            inset = Math.max(inset, rect.bottom + 8);
        });
        const value = inset + 'px';
        if (article.style.getPropertyValue('--reader-top') !== value) article.style.setProperty('--reader-top', value);
        const side = getComputedStyle(layout).display === 'grid';
        nav.setAttribute('aria-orientation', side ? 'vertical' : 'horizontal');
        const top = parseFloat(getComputedStyle(nav).top) || 0;
        container.style.setProperty('--reader-scroll-offset', (side ? top + 16 : top + nav.getBoundingClientRect().height + 16) + 'px');
      }
      if (typeof ResizeObserver !== 'undefined') new ResizeObserver(measure).observe(nav);
      window.addEventListener('resize', measure);
      let pendingMeasure = false;
      function scheduleMeasure() {
        if (pendingMeasure) return;
        pendingMeasure = true;
        requestAnimationFrame(() => { pendingMeasure = false; measure(); });
      }
      window.addEventListener('scroll', scheduleMeasure, {passive:true});
      new MutationObserver(changes => {
        if (changes.some(change => change.type === 'childList' || change.target.matches('ins[data-anchor-status], #wpadminbar')))
          scheduleMeasure();
      }).observe(document.documentElement, {subtree:true, childList:true, attributes:true, attributeFilter:['style','data-anchor-status','data-anchor-shown']});
      measure();
      function showStart() {
        measure();
        const offset = parseFloat(getComputedStyle(container).getPropertyValue('--reader-scroll-offset')) || 150;
        const delta = container.getBoundingClientRect().top - offset;
        // A sticky menu can be clicked far down a long panel: reveal the new start.
        if (Math.abs(delta) > 2) window.scrollBy({top:delta, behavior:'instant'});
      }
      const measurement = installMeasurement(article, panels);
      function activate(index, focus = false, scroll = false) {
        const all = index === 0;
        tabs.forEach((tab, i) => {
          tab.setAttribute('aria-selected', String(i === index));
          tab.tabIndex = i === index ? 0 : -1;
        });
        container.classList.toggle('wpab-all-view', all);
        ['role', 'aria-labelledby', 'tabindex'].forEach(name => container.removeAttribute(name));
        if (all) {
          container.setAttribute('role', 'tabpanel');
          container.setAttribute('aria-labelledby', tabs[index].id); container.tabIndex = 0;
        }
        panels.forEach((panel, i) => {
          panel.hidden = !all && i + 1 !== index;
          ['role', 'aria-labelledby', 'tabindex'].forEach(name => panel.removeAttribute(name));
          if (!all) {
            panel.setAttribute('role', 'tabpanel');
            panel.setAttribute('aria-labelledby', tabs[i + 1].id); panel.tabIndex = 0;
          }
        });
        if (focus) tabs[index].focus({preventScroll:true});
        measurement.refresh();
        if (scroll) showStart();
      }
      tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => { measurement.select(index); activate(index, false, true); });
        tab.addEventListener('keydown', event => {
          const next = {ArrowRight:(index+1)%tabs.length, ArrowLeft:(index+tabs.length-1)%tabs.length, ArrowDown:(index+1)%tabs.length, ArrowUp:(index+tabs.length-1)%tabs.length, Home:0, End:tabs.length-1};
          if (Object.prototype.hasOwnProperty.call(next, event.key)) {
            event.preventDefault(); measurement.select(next[event.key]); activate(next[event.key], true, true);
          }
        });
      });
      function revealHash() {
        let id;
        try { id = decodeURIComponent(location.hash.slice(1)); } catch (_) { return false; }
        if (!id) return false;
        const target = [...article.querySelectorAll('[id]')].find(node => node.id === id);
        const index = panels.findIndex(panel => panel === target || panel.contains(target));
        if (0 > index) return false;
        activate(index + 1);
        return true;
      }
      // Anchor links from inside the post still reveal their destination panel.
      article.addEventListener('click', event => {
        const link = event.target.closest('a[href^="#"]');
        if (!link) return;
        const id = link.getAttribute('href').slice(1);
        const target = [...article.querySelectorAll('[id]')].find(node => node.id === id);
        const index = panels.findIndex(panel => panel === target || panel.contains(target));
        if (index >= 0) activate(index + 1);
      });
      window.addEventListener('hashchange', revealHash);
      activate(0); revealHash();
      article.dataset.readerReady = '1';
      // Personal check state stays only in this document; no storage or requests.
      article.querySelectorAll('[data-visual="checklist"]').forEach(list => {
        const items = [...list.children].filter(node => node.tagName === 'LI');
        if (!items.length) return;
        items.forEach(item => {
          const box = document.createElement('input'); box.type = 'checkbox';
          const label = document.createElement('label'); label.className = 'wpab-personal-check';
          const copy = document.createElement('span');
          while (item.firstChild) copy.append(item.firstChild);
          label.append(box, copy); item.append(label);
        });
        const progress = document.createElement('p'); progress.className = 'wpab-check-progress';
        progress.setAttribute('aria-live', 'polite');
        const update = () => progress.textContent = list.querySelectorAll('input:checked').length + ' / ' + items.length + ' 확인';
        list.addEventListener('change', update); update(); list.after(progress);
      });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true});
  else start();
})();
