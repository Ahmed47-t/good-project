/* BENRO INDUSTRIES — shared JavaScript (Task 7)
   Handles language switching, sticky header, mobile nav, reveal animations,
   counters, year updates, and optional homepage hero localization hooks. */
(function(){
  'use strict';

  const LANG_LABEL = { en:'EN', fr:'FR', ar:'AR' };
  const SUPPORTED_LANGS = ['en','fr','ar'];

  function normalizeLang(lang){
    return SUPPORTED_LANGS.includes(lang) ? lang : 'en';
  }

  function getDict(lang){
    lang = normalizeLang(lang);
    return Object.assign(
      {},
      (window.I18N && window.I18N[lang]) || {},
      (window.BLOG_I18N && window.BLOG_I18N[lang]) || {},
      (window.PRODUCT_I18N && window.PRODUCT_I18N[lang]) || {}
    );
  }

  function applyLang(lang){
    lang = normalizeLang(lang);
    const dict = getDict(lang);
    const html = document.documentElement;
    html.lang = lang;
    html.dir = (lang === 'ar') ? 'rtl' : 'ltr';

    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (dict[key] == null) return;
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') el.placeholder = dict[key];
      else el.textContent = dict[key];
    });

    document.querySelectorAll('[data-i18n-html]').forEach(el => {
      const key = el.getAttribute('data-i18n-html');
      if (dict[key] != null) el.innerHTML = dict[key];
    });

    const current = document.getElementById('langCurrent');
    if (current) current.textContent = LANG_LABEL[lang];
    document.querySelectorAll('#langMenu [data-lang]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.lang === lang);
    });

    if (typeof window.onBenroLangApplied === 'function') {
      try { window.onBenroLangApplied(lang, dict); } catch(e) { console.warn('Language hook failed', e); }
    }

    try { localStorage.setItem('benroLang', lang); } catch(e) {}
    return dict;
  }

  function initLangSwitch(){
    const wrap = document.getElementById('langSwitch');
    const trigger = document.getElementById('langTrigger');
    const menu = document.getElementById('langMenu');
    if (!wrap || !trigger || !menu) {
      const guess = (navigator.language || 'en').slice(0,2).toLowerCase();
      applyLang(SUPPORTED_LANGS.includes(guess) ? guess : 'en');
      return;
    }
    const close = () => { wrap.classList.remove('open'); trigger.setAttribute('aria-expanded','false'); };
    const open = () => { wrap.classList.add('open'); trigger.setAttribute('aria-expanded','true'); };

    trigger.addEventListener('click', e => {
      e.stopPropagation();
      wrap.classList.contains('open') ? close() : open();
    });
    menu.querySelectorAll('[data-lang]').forEach(btn => {
      btn.addEventListener('click', () => { applyLang(btn.dataset.lang); close(); });
    });
    document.addEventListener('click', e => { if (!wrap.contains(e.target)) close(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });

    let saved = null;
    try { saved = localStorage.getItem('benroLang'); } catch(e) {}
    const guess = (navigator.language || 'en').slice(0,2).toLowerCase();
    applyLang(saved || (SUPPORTED_LANGS.includes(guess) ? guess : 'en'));
  }

  function initStickyHeader(){
    const header = document.getElementById('siteHeader');
    if (!header) return;
    const onScroll = () => header.classList.toggle('is-scrolled', window.scrollY > 8);
    window.addEventListener('scroll', onScroll, { passive:true });
    onScroll();
  }

  function initMobileMenu(){
    const burger = document.getElementById('burger');
    const mnav = document.getElementById('mnav');
    const scrim = document.getElementById('scrim');
    const closeBtn = document.getElementById('mnavClose');
    if (!burger || !mnav || !scrim || !closeBtn) return;
    const toggleMenu = (open) => {
      mnav.classList.toggle('open', open);
      scrim.classList.toggle('show', open);
      burger.setAttribute('aria-expanded', String(open));
      document.body.style.overflow = open ? 'hidden' : '';
    };
    burger.addEventListener('click', () => toggleMenu(!mnav.classList.contains('open')));
    closeBtn.addEventListener('click', () => toggleMenu(false));
    scrim.addEventListener('click', () => toggleMenu(false));
    mnav.querySelectorAll('a').forEach(a => a.addEventListener('click', () => toggleMenu(false)));
  }

  function initReveal(){
    const els = document.querySelectorAll('.reveal');
    if (!els.length) return;
    if (!('IntersectionObserver' in window)) {
      els.forEach(el => el.classList.add('in'));
      return;
    }
    const io = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    els.forEach(el => io.observe(el));
  }

  function formatNum(n){
    const lang = document.documentElement.lang || 'en';
    const loc = lang === 'ar' ? 'ar-DZ' : (lang === 'fr' ? 'fr-FR' : 'en-US');
    try { return n.toLocaleString(loc); } catch(e) { return n.toLocaleString('en-US'); }
  }

  function animateCounter(el){
    const target = Number(el.dataset.target || 0);
    const duration = 1600;
    const start = performance.now();
    const tick = (t) => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = formatNum(Math.floor(eased * target));
      if (p < 1) requestAnimationFrame(tick);
      else el.textContent = formatNum(target);
    };
    requestAnimationFrame(tick);
  }

  function initCounters(){
    const counters = document.querySelectorAll('.counter');
    if (!counters.length) return;
    if (!('IntersectionObserver' in window)) {
      counters.forEach(animateCounter);
      return;
    }
    const ioCount = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          animateCounter(entry.target);
          ioCount.unobserve(entry.target);
        }
      });
    }, { threshold: 0.4 });
    counters.forEach(counter => ioCount.observe(counter));
  }

  function initYear(){
    const year = document.getElementById('yr');
    if (year) year.textContent = new Date().getFullYear();
  }

  function init(){
    initLangSwitch();
    initStickyHeader();
    initMobileMenu();
    initReveal();
    initCounters();
    initYear();
  }

  window.LANG_LABEL = LANG_LABEL;
  window.applyLang = applyLang;
  window.BenroShared = {
    LANG_LABEL,
    getDict,
    applyLang,
    init,
    initLangSwitch,
    initStickyHeader,
    initMobileMenu,
    initReveal,
    initCounters,
    initYear,
    formatNum,
    animateCounter
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
