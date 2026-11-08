"""events.json -> og.png (1200x630 preview card shown when the link is shared in Telegram etc.)."""
import html, json, os
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
today = date.today().isoformat()
ev = [e for e in json.load(open(os.path.join(HERE, 'events.json'), encoding='utf8')) if e['date'] >= today]
ev.sort(key=lambda e: (e['date'], e.get('start') or ''))
posters = [e for e in ev if e.get('image')][:3]
nxt = ev[:3]


def when(e):
    y, m, d = map(int, e['date'].split('-'))
    return f"{d} {MONTHS[m - 1]}" + (f", {e['start']}" if e.get('start') else '')


rows = ''.join(f'<div class="r"><span>{html.escape(when(e))}</span><b>{html.escape(e["title"][:46])}</b></div>' for e in nxt)
imgs = ''.join(
    f'<img src="file:///{os.path.join(HERE, e["image"]).replace(chr(92), "/")}" style="left:{650 + i * 180}px;top:{70 + i * 70}px">'
    for i, e in enumerate(posters))
page = f'''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="fonts/fonts.css">
<style>
*{{box-sizing:border-box}}
body{{margin:0;width:1200px;height:630px;background:#0c0d10;color:#f2f2f0;font-family:Onest,sans-serif;position:relative;overflow:hidden}}
.mark{{position:absolute;left:64px;top:60px}}
h1{{position:absolute;left:64px;top:172px;margin:0;font:700 64px/1 Unbounded,sans-serif;letter-spacing:-.04em}}
.sub{{position:absolute;left:64px;top:262px;width:520px;font-size:25px;line-height:1.3;color:#9a9fa9}}
.list{{position:absolute;left:64px;top:372px;width:540px}}
.r{{margin-bottom:20px}}
.r span{{display:block;font:600 19px "JetBrains Mono",monospace;color:#ff5a36}}
.r b{{display:block;font-weight:650;font-size:27px;line-height:1.2;margin-top:3px}}
img{{position:absolute;width:170px;height:212px;object-fit:cover;border-radius:10px;box-shadow:0 14px 36px rgba(0,0,0,.5)}}
</style>
<img class="mark" src="file:///{os.path.join(HERE, 'logo.webp').replace(chr(92), '/')}" style="width:150px;height:auto;filter:invert(1);left:64px;top:44px;border-radius:0;box-shadow:none">
<h1>Расписание</h1><div class="sub">Афиша Сигнала и соседних площадок Калининграда</div>
<div class="list">{rows}</div>{imgs}'''
tmp = os.path.join(HERE, '_og.html')
open(tmp, 'w', encoding='utf8').write(page)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    try:
        b = p.chromium.launch(channel='chrome')
    except Exception:          # CI runners: use the bundled Chromium
        b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 1200, 'height': 630})
    pg.goto('file:///' + tmp.replace('\\', '/'))
    pg.wait_for_timeout(1200)
    pg.screenshot(path=os.path.join(HERE, 'og.png'))
    b.close()
os.remove(tmp)
print('og.png', os.path.getsize(os.path.join(HERE, 'og.png')) // 1024, 'KB')
