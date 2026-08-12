// Theme toggle: persists selection in localStorage and applies a `dark-theme` class to <html>
(function () {
  const THEME_KEY = 'theme';

  function applyTheme(theme) {
    const el = document.documentElement;
    if (theme === 'dark') {
      el.classList.add('dark-theme');
    } else {
      el.classList.remove('dark-theme');
    }
  }

  function current() {
    return localStorage.getItem(THEME_KEY) || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }

  window.toggleTheme = function (to) {
    const theme = to || (current() === 'dark' ? 'light' : 'dark');
    localStorage.setItem(THEME_KEY, theme);
    applyTheme(theme);
    // update any toggles on the page
    const toggle = document.querySelector('[data-theme-toggle]');
    if (toggle) toggle.textContent = theme === 'dark' ? 'Switch to Light' : 'Switch to Dark';
  };

  // apply on load
  try {
    applyTheme(current());
  } catch (e) {
    // ignore
  }
})();
