"""Download recent posts of a public Telegram channel (t.me/s/<channel>) into posts.json,
and save each post's first photo into images/<post id>.jpg."""
import html, json, os, re, sys, urllib.request

CHANNEL = "signalkld"
PAGES = int(sys.argv[1]) if len(sys.argv) > 1 else 8
PROXIES = [None, "http://127.0.0.1:10809"]  # direct first, then local VPN proxy


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    err = None
    for proxy in PROXIES * 2:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": proxy} if proxy else {}))
        try:
            data = opener.open(req, timeout=20).read()
            return data if binary else data.decode("utf8")
        except OSError as e:
            err = e
    raise err


def parse(page):
    out = []
    for m in re.finditer(r'data-post="[^/]+/(\d+)"(.*?)(?=data-post="|\Z)', page, re.S):
        pid, body = int(m.group(1)), m.group(2)
        d = re.search(r'datetime="([^"]+)"', body)
        if not d:
            continue
        t = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', body, re.S)
        raw = t.group(1) if t else ""
        links = re.findall(r'href="(https?://[^"]+)"', raw)
        text = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br/?>", "\n", raw))).strip()
        ph = re.search(r"tgme_widget_message_(?:photo_wrap|video_thumb)[^>]*background-image:url\('([^']+)'\)", body)
        out.append({"id": pid, "date": d.group(1), "text": text, "links": links,
                    "photo": ph.group(1) if ph else None, "url": f"https://t.me/{CHANNEL}/{pid}"})
    return out


posts, before = {}, None
for _ in range(PAGES):
    page = fetch(f"https://t.me/s/{CHANNEL}" + (f"?before={before}" if before else ""))
    got = parse(page)
    if not got:
        break
    for p in got:
        posts[p["id"]] = p
    before = min(p["id"] for p in got)

os.makedirs("images", exist_ok=True)


def to_webp(raw_or_path, dest):
    """Poster -> WebP, longest side at most 1200 px (a 12 MB set becomes about 3 MB)."""
    from PIL import Image
    im = Image.open(raw_or_path).convert("RGB")
    im.thumbnail((1200, 1200))
    im.save(dest, "WEBP", quality=82, method=6)


for p in posts.values():
    url = p.pop("photo")
    p["image"] = None
    if not url:
        continue
    jpg, webp = f"images/{p['id']}.jpg", f"images/{p['id']}.webp"
    try:
        if not os.path.exists(webp):
            if os.path.exists(jpg):
                to_webp(jpg, webp)
            else:
                import io
                to_webp(io.BytesIO(fetch(url, binary=True)), webp)
        if os.path.exists(jpg):
            os.remove(jpg)
    except Exception as e:
        print("photo failed", p["id"], type(e).__name__)
        continue
    p["image"] = webp

res = sorted(posts.values(), key=lambda p: p["id"])
json.dump(res, open("posts.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
print(len(res), "posts,", sum(1 for p in res if p["image"]), "with photo,", res[0]["date"][:10], "->", res[-1]["date"][:10])
