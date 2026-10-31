/* Theme: light/dark with system default, persisted. */
(function () {
    const KEY = 'tc_theme';

    function systemTheme() {
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    function refreshLabel(theme) {
        const btn = document.getElementById('themeBtn');
        if (!btn) return;
        const zh = (window.t ? window.t('themeLight') : '浅色');
        const other = (window.t ? window.t('themeDark') : '深色');
        btn.textContent = theme === 'dark' ? zh : other;
        btn.title = btn.textContent;
    }

    function apply(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        refreshLabel(theme);
    }

    const current = localStorage.getItem(KEY) || systemTheme();
    apply(current);

    window.tcTheme = {
        get current() { return document.documentElement.getAttribute('data-theme') || systemTheme(); },
        toggle: function () {
            const next = this.current === 'dark' ? 'light' : 'dark';
            localStorage.setItem(KEY, next);
            apply(next);
        },
        apply: apply,
    };

    document.addEventListener('DOMContentLoaded', function () { apply(window.tcTheme.current); });
    document.addEventListener('tc:lang', function () { refreshLabel(window.tcTheme.current); });
})();
