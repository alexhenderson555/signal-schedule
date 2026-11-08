"""events.json -> inlined into index.html (works from file://) and signal.ics (calendar subscription)."""
import hashlib, json, re
from datetime import datetime, timedelta, timezone

ev = json.load(open("events.json", encoding="utf8"))
html = open("index.html", encoding="utf8").read()
data = "/*DATA*/window.EVENTS = " + json.dumps(ev, ensure_ascii=False) + ";/*END*/"
html = re.sub(r"/\*DATA\*/.*?/\*END\*/", lambda m: data, html, flags=re.S)
open("index.html", "w", encoding="utf8").write(html)
print(len(ev), "events inlined")

# ---- signal.ics: everything from a week ago onwards, so a subscribed calendar fills itself and stays current
KALININGRAD = timedelta(hours=2)   # UTC+2, no daylight saving
now = datetime.now(timezone.utc)
since = (now + KALININGRAD - timedelta(days=7)).date().isoformat()


def esc(s):
    return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r", "").replace("\n", "\\n")


def fold(line):
    """RFC 5545 line folding: at most 75 octets per line, never inside a UTF-8 character."""
    b, parts, limit = line.encode("utf8"), [], 75
    while len(b) > limit:
        cut = limit
        while (b[cut] & 0xC0) == 0x80:
            cut -= 1
        parts.append(b[:cut].decode("utf8"))
        b, limit = b[cut:], 74
    parts.append(b.decode("utf8"))
    return "\r\n ".join(parts)


def utc(day, hhmm):
    local = datetime.strptime(f"{day} {hhmm}", "%Y-%m-%d %H:%M")
    return (local - KALININGRAD).strftime("%Y%m%dT%H%M%SZ")


lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//signal-schedule//RU", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
         "X-WR-CALNAME:Расписание Сигнала", "X-WR-TIMEZONE:Europe/Kaliningrad",
         "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H"]
n = 0
for e in ev:
    if e["date"] < since:
        continue
    uid = hashlib.sha1((e["date"] + e["title"]).encode("utf8")).hexdigest()[:20] + "@signal-schedule"
    lines += ["BEGIN:VEVENT", f"UID:{uid}", "DTSTAMP:" + now.strftime("%Y%m%dT%H%M%SZ")]
    if e.get("start"):
        end = e.get("end")
        if not end or end <= e["start"]:   # no end given, or it wraps past midnight: assume an hour
            h, m = map(int, e["start"].split(":"))
            end = f"{min(h + 1, 23):02d}:{m:02d}"
        lines += ["DTSTART:" + utc(e["date"], e["start"]), "DTEND:" + utc(e["date"], end)]
    else:
        nxt = (datetime.strptime(e["date"], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
        lines += ["DTSTART;VALUE=DATE:" + e["date"].replace("-", ""), "DTEND;VALUE=DATE:" + nxt]
    desc = (e.get("desc") or "") + ("\n" + e["url"] if e.get("url") else "")
    lines += ["SUMMARY:" + esc(e["title"]), "LOCATION:" + esc(e["venue"] + ", Калининград"), "DESCRIPTION:" + esc(desc)]
    if e.get("url"):
        lines.append("URL:" + e["url"])
    lines.append("END:VEVENT")
    n += 1
lines.append("END:VCALENDAR")
open("signal.ics", "w", encoding="utf8", newline="").write("\r\n".join(fold(l) for l in lines) + "\r\n")
print(n, "events in signal.ics")
