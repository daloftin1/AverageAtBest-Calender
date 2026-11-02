// Show three complete cards, with additional events inside the scroll region.
const agendaPanel = document.querySelector('.agenda-scroll');
if (agendaPanel) {
    const cards = [...agendaPanel.querySelectorAll('.event-row')];
    const sidebar = document.querySelector('.calendar-sidebar');
    const sizeAgenda = () => {
        const calendarHeight = sidebar.getBoundingClientRect().height;
        agendaPanel.closest('.agenda').style.setProperty('--calendar-panel-height', `${calendarHeight}px`);
        if (cards.length < 3) return;
        const panelTop = agendaPanel.getBoundingClientRect().top;
        const thirdBottom = cards[2].getBoundingClientRect().bottom;
        const threeCardHeight = Math.ceil(thirdBottom - panelTop + agendaPanel.scrollTop);
        agendaPanel.style.maxHeight = `${threeCardHeight}px`;
    };
    const observer = new ResizeObserver(sizeAgenda);
    cards.slice(0, 3).forEach(card => observer.observe(card));
    observer.observe(sidebar);
    sizeAgenda();
}
