(function () {
  'use strict';

  var STORAGE_KEY = 'tema';
  var root = document.documentElement;
  var button = document.getElementById('theme-toggle');
  if (!button) return;

  var label = button.querySelector('[data-theme-label]');
  var systemDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');

  var NAMES = {
    system: 'automatico, come il sistema',
    light: 'chiaro',
    dark: 'scuro'
  };

  function readStored() {
    try {
      var stored = localStorage.getItem(STORAGE_KEY);
      return stored === 'light' || stored === 'dark' ? stored : 'system';
    } catch (e) {
      return 'system';
    }
  }

  function store(state) {
    try {
      if (state === 'system') localStorage.removeItem(STORAGE_KEY);
      else localStorage.setItem(STORAGE_KEY, state);
    } catch (e) {

    }
  }

  function nextState(current) {
    var isSystemDark = !!(systemDark && systemDark.matches);
    var opposite = isSystemDark ? 'light' : 'dark';
    if (current === 'system') return opposite;
    if (current === opposite) return isSystemDark ? 'dark' : 'light';
    return 'system';
  }

  function render(state) {
    if (state === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', state);

    button.setAttribute('data-theme-state', state);

    var text = 'Tema: ' + NAMES[state] + '. Passa a: ' + NAMES[nextState(state)];
    if (label) label.textContent = text;
    button.setAttribute('title', text);
  }

  var current = readStored();
  render(current);
  button.hidden = false;

  button.addEventListener('click', function () {
    current = nextState(current);
    store(current);
    render(current);
  });

  if (systemDark && systemDark.addEventListener) {
    systemDark.addEventListener('change', function () { render(current); });
  }
})();
