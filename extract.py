"""posts.json -> events (events.auto.json, or events.json with --write).

Gemini turns free-text channel posts into structured events. Anti-hallucination:
every event must carry a `quote` copied from its post, and is dropped if that quote is not in the post text;
reg_url must be one of the post's own links. Results are cached per post, so reruns only send new posts.
Key and proxy come from env, falling back to ../kld-events/.env (values are never printed)."""
import difflib, hashlib, json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=2))  # Kaliningrad
WINDOW_DAYS = 21
CHUNK = 15
WRITE = "--write" in sys.argv
# typos made by the organizers themselves in their posts (a general speller damages names, so only known ones)
TYPOS = {"Неприрывность": "Непрерывность", "фукцию": "функцию", "Разбирёмся": "Разберёмся", "Cуспирия": "Суспирия", "Ксмонавта": "Космонавта"}
RU_WD = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]


def env(name):
    if os.environ.get(name):
        return os.environ[name]
    try:
        for line in open(os.path.join("..", "kld-events", ".env"), encoding="utf8"):
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return None


KEY = env("GEMINI_API_KEY")
MODEL = os.environ.get("EXTRACT_MODEL") or "gemini-3.1-flash-lite"  # fast; flash/pro hit free-tier limits
PROXY = env("EXTRACT_PROXY") or "http://127.0.0.1:10809"  # Gemini is not reachable directly from RU; EXTRACT_PROXY=none disables
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({} if PROXY.lower() == "none" else {"https": PROXY}))
if not KEY:
    sys.exit("GEMINI_API_KEY is not set")

S = lambda nullable=False: {"type": "STRING", "nullable": nullable}
SCHEMA = {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "post": {"type": "INTEGER"}, "quote": S(), "date": S(), "start": S(True), "end": S(True),
    "title": S(), "kind": S(), "venue": S(), "desc": S(), "price": S(True), "reg_url": S(True),
    "age": S(True), "series": S(True)},
    "required": ["post", "quote", "date", "title", "kind", "venue", "desc"]}}

PROMPT = """Ты извлекаешь анонсы событий из постов Telegram-канала арт-пространства «Сигнал» (Калининград).
Для каждого поста дан календарь: «сегодня» и «завтра» относительно даты публикации, и ближайшие дни недели.
Правила:
- Одно событие = одна дата и время. Программа фестиваля из нескольких пунктов даёт несколько событий.
- date строго YYYY-MM-DD. Относительные даты считай ТОЛЬКО по календарю из заголовка поста. Если год не указан, это 2026.
- start и end в формате HH:MM или null. Время бери только из текста. Не выдумывай.
- quote: точный фрагмент текста поста (до 120 символов), подтверждающий событие и его дату или время. Копируй символ в символ.
- title: короткое название из текста поста. Не придумывай названий.
- kind: одно из: кино, настолки, лекция, мастер-класс, питчинг, музыка, ярмарка, квиз, другое.
- venue: «Сигнал, Леонова 22» по умолчанию; «Башня, Горького 116» если в посте Башня; иначе адрес из поста.
- desc: 2-3 предложения (150-350 символов) по тексту поста: что будет, кто ведёт или выступает, формат, для кого. Только факты из поста, без рекламных штампов. price: как написано или null. age: например «14+» или null.
- reg_url: только ссылка из списка ссылок этого поста (регистрация, билеты) или null. series: название цикла или фестиваля, иначе null.
- Если пост не анонс будущего события (отчёт, фото, благодарность, реклама книг), события нет. Не включай то, что уже прошло на момент публикации поста.
- Одно и то же событие из нескольких постов (анонс и напоминание) верни один раз.
Верни JSON-массив.

Посты:
"""


def calendar_hint(dt):
    out = [f"сегодня={dt:%Y-%m-%d} ({RU_WD[dt.weekday()]})", f"завтра={dt + timedelta(days=1):%Y-%m-%d}"]
    for k in range(2, 8):
        d = dt + timedelta(days=k)
        out.append(f"{RU_WD[d.weekday()]}={d:%Y-%m-%d}")
    return ", ".join(out)


def call(posts):
    blocks = []
    for p in posts:
        dt = datetime.fromisoformat(p["date"]).astimezone(TZ)
        blocks.append(f'### post {p["id"]} | опубликован {dt:%Y-%m-%d %H:%M}\nкалендарь: {calendar_hint(dt)}\n'
                      f'{p["text"][:3500]}\nссылки: {p["links"]}')
    body = json.dumps({"contents": [{"parts": [{"text": PROMPT + "\n\n".join(blocks)}]}],
                       "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                            "responseSchema": SCHEMA,
                                            "thinkingConfig": {"thinkingLevel": "low"} if "gemini-3" in MODEL
                                            else {"thinkingBudget": 0}}}).encode()
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        body, {"content-type": "application/json", "x-goog-api-key": KEY})
    for attempt in range(6):
        try:
            data = json.load(OPENER.open(req, timeout=300))
            return json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf8", "ignore")
            m = re.search(r'retryDelay"?:\s*"?(\d+)', msg)
            wait = int(m.group(1)) + 2 if m else 20 * (attempt + 1)
            print(f"  HTTP {e.code}, wait {wait}s (attempt {attempt + 1})")
            time.sleep(wait)
        except Exception as e:
            print("  error:", type(e).__name__, str(e)[:80])
            time.sleep(10)
    raise RuntimeError("gave up")


norm = lambda t: re.sub(r"\s+", " ", re.sub(r"[^\w:+]+", " ", (t or "").lower())).strip()


def valid(e, post):
    q, txt = norm(e.get("quote")), norm(post["text"])
    words = q.split()
    # exact fragment, or (tolerating small typos and emoji) at least 80% of its words occur in the post
    if not q or not (q in txt or (len(words) >= 3 and sum(w in txt for w in words) / len(words) >= 0.8)):
        return "quote not in post"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", e.get("date") or ""):
        return "bad date"
    pd = datetime.fromisoformat(post["date"]).astimezone(TZ).date()
    d = datetime.strptime(e["date"], "%Y-%m-%d").date()
    if d < pd - timedelta(days=1) or d > pd + timedelta(days=150):
        return "date out of range"
    for f in ("start", "end"):
        if e.get(f) and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", e[f]):
            e[f] = None
    if e.get("reg_url") and e["reg_url"] not in post["links"]:
        e["reg_url"] = None
    return None


posts = json.load(open("posts.json", encoding="utf8"))
cut = (datetime.now(TZ) - timedelta(days=WINDOW_DAYS)).isoformat()
posts = [p for p in posts if len(p["text"]) > 40 and datetime.fromisoformat(p["date"]) >= datetime.fromisoformat(cut)]
by_id = {p["id"]: p for p in posts}
h = lambda p: hashlib.md5((PROMPT + p["text"]).encode()).hexdigest()  # prompt change invalidates the cache
try:
    cache = json.load(open("cache.json", encoding="utf8"))
except OSError:
    cache = {}

todo = [p for p in posts if cache.get(str(p["id"]), {}).get("h") != h(p)]
print(f"{len(posts)} posts in window, {len(todo)} new or changed, model {MODEL}")
for i in range(0, len(todo), CHUNK):
    chunk = todo[i:i + CHUNK]
    got = call(chunk)
    for p in chunk:
        cache[str(p["id"])] = {"h": h(p), "events": []}
    for e in got:
        p = by_id.get(e.get("post"))
        if not p:
            continue
        why = valid(e, p)
        if why:
            print("  drop:", why, "|", (e.get("title") or "")[:50])
            continue
        cache[str(p["id"])]["events"].append(e)
    json.dump(cache, open("cache.json", "w", encoding="utf8"), ensure_ascii=False)

events = [e for p in posts for e in cache.get(str(p["id"]), {}).get("events", [])]
out = []
for e in events:
    def same(o):
        a, b = norm(o["title"]), norm(e["title"])
        contained = o.get("start") and o["start"] == e.get("start") and (a in b or b in a)  # "Питчинг" vs "Питчинг городских проектов"
        return difflib.SequenceMatcher(None, a, b).ratio() > .6 or contained
    dup = next((o for o in out if o["date"] == e["date"] and same(o)), None)
    if dup:
        for f in ("start", "end", "price", "reg_url", "age", "desc", "series"):
            if not dup.get(f) and e.get(f):
                dup[f] = e[f]
        continue
    out.append(dict(e))
all_posts = json.load(open("posts.json", encoding="utf8"))


def image_for(post):
    """The post's own photo, else the photo of a neighbouring album part (same minutes, nearby ids)."""
    if post.get("image"):
        return post["image"]
    t0 = datetime.fromisoformat(post["date"])
    near = [q for q in all_posts if q.get("image") and abs(q["id"] - post["id"]) <= 6
            and abs((datetime.fromisoformat(q["date"]) - t0).total_seconds()) <= 600]
    return min(near, key=lambda q: abs(q["id"] - post["id"]))["image"] if near else None


EMOJI = re.compile("[\U0001F000-\U0001FAFF←-⇿⌀-⏿①-➿⬀-⯿️‍﻿]")


def clean_text(t):
    """Original announcement text without emoji, hashtag and sign-up footer lines."""
    lines = []
    for ln in EMOJI.sub("", t.replace("—", "-").replace("–", "-")).split("\n"):
        ln = ln.strip()
        if re.fullmatch(r"(#\S+\s*)+", ln) or "König" in ln or re.fullmatch(r"(TG|ВК|Max|МАХ|\W)+", ln):
            continue
        lines.append(ln)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()[:2200]


def locate(text, quote):
    """Start of the line where the event's quote begins in the raw post text, or None."""
    words = re.sub(r"\s+", " ", quote or "").strip()[:30].split(" ")
    m = re.search(r"\s+".join(map(re.escape, words)), text, re.I) if words and words[0] else None
    return text.rfind("\n", 0, m.start()) + 1 if m else None


by_post = {}
for e in out:
    by_post.setdefault(e["post"], []).append(e)
for pid, group in by_post.items():
    raw = by_id[pid]["text"]
    if len(group) == 1:
        group[0]["text"] = clean_text(raw)
        continue
    # several events in one post: give each only its own part, between its quote and the next event's quote
    pos = [(locate(raw, e.get("quote")), e) for e in group]
    starts = sorted(p for p, _ in pos if p is not None)
    for p, e in pos:
        if p is None:
            e["text"] = ""
            continue
        nxt = [s for s in starts if s > p]
        seg = clean_text(raw[p:nxt[0]] if nxt else raw[p:])
        e["text"] = seg if len(seg) >= 120 else ""  # too short to read alone: the page falls back to desc

for e in out:
    e["image"] = image_for(by_id[e["post"]])
    e["url"] = by_id[e["post"]]["url"]
    e["source"] = "Сигнал"
    e.pop("quote", None)
    for f in ("title", "desc", "price", "venue", "series", "text"):  # the page style bans long dashes
        if e.get(f):
            e[f] = e[f].replace("—", "-").replace("–", "-")
            for bad, good in TYPOS.items():
                e[f] = e[f].replace(bad, good)
# hand-checked corrections that survive reruns: overrides.json = [{"date":..., "title_contains":..., "drop":true | "set":{...}}]
try:
    overrides = json.load(open("overrides.json", encoding="utf8"))
except OSError:
    overrides = []
for ov in overrides:
    for e in [e for e in out if e["date"] == ov.get("date") and ov.get("title_contains", "").lower() in e["title"].lower()]:
        if ov.get("drop"):
            out.remove(e)
            print("override: dropped", e["date"], e["title"][:40])
        else:
            e.update(ov.get("set", {}))
            print("override: patched", e["date"], e["title"][:40])
out.sort(key=lambda e: (e["date"], e.get("start") or ""))
target = "events.json" if WRITE else "events.auto.json"
if WRITE and os.path.exists("events.json"):  # a failed or partial run must not wipe the live list
    prev = len(json.load(open("events.json", encoding="utf8")))
    if prev >= 10 and len(out) < prev * 0.6:
        sys.exit(f"abort: {len(out)} events against {prev} before, looks like a failed run. events.json kept.")
json.dump(out, open(target, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print(len(out), "events ->", target)
