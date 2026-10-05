(async () => {
  const banner = document.querySelector('#upcoming-races');
  if (!banner) return;
  try {
    const response = await fetch('/assets/fis-france.json', {cache: 'no-cache'});
    if (!response.ok) return;
    const feed = await response.json();
    // Hide stale information if scheduled refreshes have stopped.
    if (Date.now() - Date.parse(feed.updatedAt) > 7 * 86400000) return;
    const today = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Europe/Paris', year: 'numeric', month: '2-digit', day: '2-digit'
    }).format(new Date());
    const list = banner.querySelector('.race-list');
    const buttons = [...banner.querySelectorAll('[data-circuit]')];
    const grouped = {};
    for (const [circuit, calendar] of Object.entries(feed.calendars)) {
    const races = calendar.races.filter(r => r.date >= today);
    const events = [];
    for (const race of races) {
      let event = events.find(e => e.place === race.place && e.discipline === race.discipline &&
        (Date.parse(race.date) - Date.parse(e.end)) <= 86400000);
      if (!event) {
        event = {...race, start: race.date, end: race.date, genders: new Set(), categories: new Map()};
        events.push(event);
      }
      event.end = race.date;
      event.genders.add(race.gender);
      event.categories.set(race.category, race.categoryName);
    }
    grouped[circuit] = events.slice(0, 2);
    }
    const format = date => new Intl.DateTimeFormat('fr-FR', {
      day: 'numeric', month: 'long', timeZone: 'UTC'
    }).format(new Date(date + 'T12:00:00Z'));
    const names = {'Amneville': 'Amnéville', 'Bonneval S/Arc': 'Bonneval-sur-Arc'};
    const disciplines = {'Slalom': 'Slalom', 'Giant Slalom': 'Géant', 'Downhill': 'Descente', 'Super G': 'Super-G'};
    function render(circuit) {
    list.replaceChildren();
    for (const button of buttons) button.setAttribute('aria-pressed', String(button.dataset.circuit === circuit));
    for (const event of grouped[circuit] || []) {
      const link = document.createElement('a');
      link.className = 'race-item';
      const url = new URL(event.url);
      if (url.origin !== 'https://www.fis-ski.com') continue;
      link.href = url.href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      const date = document.createElement('span');
      date.className = 'race-date';
      date.textContent = event.start === event.end ? format(event.start) :
        `${new Date(event.start + 'T12:00:00Z').getUTCDate()}–${format(event.end)}`;
      const details = document.createElement('span');
      const title = document.createElement('strong');
      title.textContent = names[event.place] || event.place;
      const category = document.createElement('span');
      category.className = 'race-category';
      category.textContent = ' · ' + [...event.categories.keys()].join(' / ');
      category.title = [...event.categories].map(([code, name]) => `${code} : ${name}`).join(' · ');
      title.append(category);
      const subtitle = document.createElement('span');
      subtitle.className = 'race-details';
      const gender = event.genders.size === 2 ? 'Dames et hommes' :
        event.genders.has('Women') ? 'Dames' : 'Hommes';
      subtitle.textContent = `${disciplines[event.discipline] || event.discipline} · ${gender}`;
      details.append(title, subtitle);
      const arrow = document.createElement('span');
      arrow.textContent = '↗';
      arrow.setAttribute('aria-hidden', 'true');
      link.append(date, details, arrow);
      list.append(link);
    }
    banner.hidden = !list.children.length;
    }
    for (const button of buttons) {
      button.disabled = !grouped[button.dataset.circuit]?.length;
      button.addEventListener('click', () => render(button.dataset.circuit));
    }
    const first = buttons.find(button => !button.disabled);
    if (first) render(first.dataset.circuit);
  } catch (_) {
    // The rest of the homepage stays usable when the feed is unavailable.
  }
})();
