"""events.json + posts.json -> review.md: upcoming events worth a human look before they are trusted.
Rules are simple on purpose. A flag is a question to the editor, not a verdict."""
import json, re
from datetime import date, datetime

WD = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']
today = date.today()
events = json.load(open('events.json', encoding='utf8'))
posts = {p['id']: p for p in json.load(open('posts.json', encoding='utf8'))}
CANCEL = re.compile(r'отмен|перен[её]с|не состоится|изменени[ея] (?:времени|даты)|вместо', re.I)


def sig_words(t):
    return {w[:5] for w in re.findall(r'[\w]{5,}', (t or '').lower())}


def flags(e):
    out = []
    d = date.fromisoformat(e['date'])
    p = posts.get(e.get('post'))
    if 'питчинг' in (e['title'] + ' ' + (e.get('series') or '')).lower() and d.weekday() != 0:
        out.append(f'питчинг обычно по понедельникам, а это {WD[d.weekday()]}')
    if not e.get('start'):
        out.append('нет времени начала')
    if p:
        age = (today - datetime.fromisoformat(p['date']).date()).days
        if (d - today).days > 30 and age > 14:
            out.append(f'дата через {(d - today).days} дн., а пост ему {age} дн.: могло устареть')
        tw = sig_words(e['title'])
        for q in posts.values():
            if q['id'] > p['id'] and CANCEL.search(q.get('text') or '') and len(tw & sig_words(q['text'])) >= 2:
                out.append(f'в более позднем посте {q["url"]} есть слова про отмену или перенос')
                break
    if e['kind'] == 'другое':
        out.append('тип события не определён')
    return out


rows = []
for e in sorted(events, key=lambda e: (e['date'], e.get('start') or '')):
    if e['date'] < today.isoformat():
        continue
    f = flags(e)
    if f:
        rows.append((e, f))

upcoming = [e for e in events if e['date'] >= today.isoformat()]
untyped = sum(1 for e in upcoming if e['kind'] == 'другое')
rows = [(e, [x for x in f if x != 'тип события не определён']) for e, f in rows]
rows = [(e, f) for e, f in rows if f]
lines = [f'# Проверка событий на {today.isoformat()}', '']
lines.append(f'Ближайших событий: {len(upcoming)}. Есть вопросы по {len(rows)}. Без определённого типа: {untyped}.')
lines.append('')
for e, f in rows:
    lines.append(f'- **{e["date"]} {e.get("start") or "время ?"}, {e["title"]}** ([пост]({e.get("url")}))')
    lines.extend(f'  - {x}' for x in f)
if not rows:
    lines.append('Подозрительного не нашлось.')
text = '\n'.join(lines) + '\n'
open('review.md', 'w', encoding='utf8').write(text)
print(text)
