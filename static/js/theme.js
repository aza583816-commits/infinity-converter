window.currentLang = 'en';

function toggleTheme() {
  document.body.classList.toggle('light-theme');
  const btn = document.getElementById('theme-btn');
  const s = window.VInfinityI18n.STRINGS[window.currentLang];
  btn.innerText = document.body.classList.contains('light-theme') ? s.themeToDark : s.themeToLight;
}

function applyLanguage(lang) {
  const { TOOL_OPTIONS_EN, TOOL_OPTIONS_AR, STRINGS } = window.VInfinityI18n;
  const s = STRINGS[lang];
  const selectElem = document.getElementById('conversion-type');
  const selectedVal = selectElem.value;

  document.dir = lang === 'ar' ? 'rtl' : 'ltr';
  document.getElementById('lang-btn').innerText = s.langToggle;
  selectElem.innerHTML = lang === 'ar' ? TOOL_OPTIONS_AR : TOOL_OPTIONS_EN;
  selectElem.setAttribute('dir', lang === 'ar' ? 'rtl' : 'ltr');

  document.getElementById('sub-title').innerText = s.subtitle;
  document.getElementById('lbl-tool').innerText = s.tool;
  document.getElementById('lbl-content').innerText = s.content;
  document.getElementById('input-data').placeholder = s.placeholder;
  document.getElementById('lbl-result').innerText = s.result;
  document.getElementById('label-chars').innerText = s.chars;
  document.getElementById('label-words').innerText = s.words;
  document.getElementById('lbl-upload-title').innerText = s.uploadTitle;
  document.getElementById('lbl-upload-sub').innerText = s.uploadSub;
  document.querySelector('.btn-execute').innerText = s.execute;
  document.getElementById('copy-btn').innerText = s.copy;
  document.getElementById('clear-btn').innerText = s.clear;

  if (selectedVal) selectElem.value = selectedVal;
}

function toggleLanguage() {
  window.currentLang = window.currentLang === 'en' ? 'ar' : 'en';
  applyLanguage(window.currentLang);
}

window.VInfinityTheme = { toggleTheme, toggleLanguage, applyLanguage };
