/* Progressive enhancement: HTML retains every section if scripts are filtered. */
(() => {
  function start() {
    document.querySelectorAll('.wpab-menu-reader').forEach(article => {
      if (article.dataset.readerReady) return;
      const panels = [...article.querySelectorAll(':scope > [data-reader-panels] > [data-reader-panel]')];
      const nav = article.querySelector(':scope > [data-reader-menu]');
      const container = article.querySelector(':scope > [data-reader-panels]');
      if (!nav || !container || panels.length < 2) return;
      const links = [...nav.querySelectorAll('a')];
      if (links.length !== panels.length + 1) return;
      // IDs generated per instance avoid collisions on multi-article pages.
      const prefix = 'wpab-reader-' + [...document.querySelectorAll('.wpab-menu-reader')].indexOf(article);
      container.id = prefix + '-all';
      panels.forEach((panel, i) => panel.id = prefix + '-panel-' + i);
      const tabs = links.map((link, i) => {
        const tab = document.createElement('button');
        tab.type = 'button'; tab.textContent = link.textContent;
        tab.id = prefix + '-tab-' + i;
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-controls', i < panels.length ? panels[i].id : container.id);
        link.replaceWith(tab); return tab;
      });
      nav.setAttribute('role', 'tablist');
      function activate(index, focus = false) {
        const all = index === panels.length;
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
          panel.hidden = !all && i !== index;
          ['role', 'aria-labelledby', 'tabindex'].forEach(name => panel.removeAttribute(name));
          if (!all) {
            panel.setAttribute('role', 'tabpanel');
            panel.setAttribute('aria-labelledby', tabs[i].id); panel.tabIndex = 0;
          }
        });
        if (focus) tabs[index].focus();
      }
      tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => activate(index));
        tab.addEventListener('keydown', event => {
          const next = {ArrowRight:(index+1)%tabs.length, ArrowLeft:(index+tabs.length-1)%tabs.length, Home:0, End:tabs.length-1};
          if (Object.prototype.hasOwnProperty.call(next, event.key)) {
            event.preventDefault(); activate(next[event.key], true);
          }
        });
      });
      function revealHash() {
        let id;
        try { id = decodeURIComponent(location.hash.slice(1)); } catch (_) { return false; }
        if (!id) return false;
        const target = [...article.querySelectorAll('[id]')].find(node => node.id === id);
        const index = panels.findIndex(panel => panel === target || panel.contains(target));
        if (index < 0) return false;
        activate(index);
        return true;
      }
      // Anchor links from inside the post still reveal their destination panel.
      article.addEventListener('click', event => {
        const link = event.target.closest('a[href^="#"]');
        if (!link) return;
        const id = link.getAttribute('href').slice(1);
        const target = [...article.querySelectorAll('[id]')].find(node => node.id === id);
        const index = panels.findIndex(panel => panel === target || panel.contains(target));
        if (index >= 0) activate(index);
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
