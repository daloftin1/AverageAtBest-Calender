// Change the page colors and keep the switch in sync.
function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    const button = document.getElementById('theme-toggle');
    if (button) {
        button.setAttribute('aria-checked', String(theme === 'dark'));
        button.title = theme === 'dark' ? 'Switch to day mode' : 'Switch to dark mode';
    }
}

// Change the theme and remember it for the next visit.
function toggleTheme() {
    const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(theme);
    try {
        localStorage.setItem('calendar-theme', theme);
    } catch (error) {
        // The switch still works when browser storage is turned off.
    }
}

// Start with the saved theme, or use day mode for a first visit.
let savedTheme = 'light';
try {
    if (localStorage.getItem('calendar-theme') === 'dark') savedTheme = 'dark';
} catch (error) {
    // Use day mode when browser storage is unavailable.
}
applyTheme(savedTheme);

document.addEventListener('DOMContentLoaded', () => {
    const button = document.getElementById('theme-toggle');
    if (!button) return;
    applyTheme(document.documentElement.dataset.theme);
    button.disabled = false;
    button.addEventListener('click', toggleTheme);
});

// Keep the theme the same in other open calendar tabs.
window.addEventListener('storage', event => {
    if (event.key === 'calendar-theme' || event.key === null) {
        applyTheme(event.newValue === 'dark' ? 'dark' : 'light');
    }
});

// Close the profile panel when clicking outside it or pressing Escape.
function closeProfileMenu(event) {
    const menu = document.getElementById('profile-menu');
    if (!menu || !menu.open) return;
    if (event.type === 'keydown' && event.key === 'Escape') {
        menu.open = false;
        menu.querySelector('summary').focus();
    } else if (event.type === 'click' && !menu.contains(event.target)) {
        menu.open = false;
    }
}

document.addEventListener('click', closeProfileMenu);
document.addEventListener('keydown', closeProfileMenu);
