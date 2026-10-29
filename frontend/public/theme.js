// Applies the saved theme, or the system one on the first visit, before the page is drawn, so the page doesn't
// flash in the wrong theme. It is a separate file because the Content-Security-Policy blocks inline scripts.
const savedDarkMode = localStorage.getItem('darkMode');
if (savedDarkMode ? JSON.parse(savedDarkMode) : window.matchMedia('(prefers-color-scheme: dark)').matches) {
  document.documentElement.classList.add('dark');
}
