// Theme toggle: persists selection in localStorage and applies a `dark-theme` class to <html>
(function () {
  const THEME_KEY = 'theme';

  function syncToggleButton() {
    const toggle = document.querySelector('[data-theme-toggle]');
    if (!toggle) return;

    const isDark = document.documentElement.classList.contains('dark-theme');
    toggle.textContent = isDark ? '☀️' : '🌙';
    toggle.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
    toggle.setAttribute('title', isDark ? 'Switch to light mode' : 'Switch to dark mode');
    toggle.setAttribute('aria-pressed', String(isDark));
  }

  function applyTheme(theme) {
    const el = document.documentElement;
    const isDark = theme === 'dark';
    el.classList.toggle('dark-theme', isDark);
    el.setAttribute('data-theme', theme);
    syncToggleButton();
  }

  function current() {
    return localStorage.getItem(THEME_KEY) || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  }

  window.toggleTheme = function (to) {
    const theme = to || (current() === 'dark' ? 'light' : 'dark');
    localStorage.setItem(THEME_KEY, theme);
    applyTheme(theme);
  };

  function toggleMobileMenu() {
    document.body.classList.toggle('mobile-nav-open');
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-theme-toggle]').forEach(function (button) {
      button.addEventListener('click', function () {
        window.toggleTheme();
      });
    });

    document.querySelectorAll('[data-mobile-menu-toggle]').forEach(function (button) {
      button.addEventListener('click', function () {
        toggleMobileMenu();
      });
    });

    try {
      applyTheme(current());
    } catch (e) {
      // ignore
    }
  });
})();
