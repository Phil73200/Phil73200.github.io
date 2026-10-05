"""Build a public race feed from the official FIS France alpine calendar."""
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
from zoneinfo import ZoneInfo

BASE = 'https://www.fis-ski.com/DB/services/public/icalendar-feed-fis-events.html'

def parse_calendar(text):
    text = re.sub(r'\r?\n[ \t]', '', text)
    if 'BEGIN:VCALENDAR' not in text or 'END:VCALENDAR' not in text:
        raise ValueError('Invalid FIS calendar response')
    races = []
    for block in text.split('BEGIN:VEVENT')[1:]:
        fields = {}
        for line in block.split('END:VEVENT')[0].splitlines():
            key, sep, value = line.partition(':')
            if sep:
                fields[key.split(';')[0]] = value
        if fields.get('STATUS') == 'CANCELLED':
            continue
        date = fields.get('DTSTART', '')[:8]
        if not re.fullmatch(r'\d{8}', date):
            raise ValueError('Missing race date')
        description = fields.get('DESCRIPTION', '')
        gender = re.search(r'Gender:\s*(Women|Men)', description)
        discipline = re.search(r'Event:\s*([^\\\n]+)', description)
        link = re.search(r'https://www\.fis-ski\.com/DB/general/results\.html\?[^\\\s]+', description)
        if not gender or not discipline or not link:
            raise ValueError('Missing race details')
        category = fields.get('CATEGORIES', '').removeprefix('FIS-calendar-AL-')
        category_name = re.search(r'Category:\s*([^\\\n]+)', description)
        location = fields.get('LOCATION', '').replace(r'\,', ',').replace(r'\;', ';')
        races.append({'date': f'{date[:4]}-{date[4:6]}-{date[6:8]}',
                      'place': location, 'gender': gender[1],
                      'discipline': discipline[1].strip(), 'category': category,
                      'categoryName': category_name[1].strip() if category_name else category,
                      'url': link[0]})
    return sorted(races, key=lambda r: (r['date'], r['place'], r['gender']))

def main():
    now = datetime.now(ZoneInfo('Europe/Paris'))
    season = now.year + (now.month >= 7)
    calendars = {}
    for key, query in [('france', 'nationcode=FRA'), ('ec', 'categorycode=EC'), ('wc', 'categorycode=WC')]:
        source = f'{BASE}?seasoncode={season}&sectorcode=AL&{query}'
        with urlopen(source, timeout=45) as response:
            races = parse_calendar(response.read().decode('utf-8-sig'))
        calendars[key] = {'source': source, 'races': races}
        print(f'{key}: {len(races)} races fetched from FIS')
    target = Path(__file__).resolve().parents[1] / 'assets/fis-france.json'
    target.write_text(json.dumps({'updatedAt': now.isoformat(), 'calendars': calendars},
                                ensure_ascii=False, indent=2) + '\n')

if __name__ == '__main__':
    main()
