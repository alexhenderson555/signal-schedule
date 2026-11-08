# Расписание Сигнала

Неофициальная афиша событий Сигнала и соседних площадок Калининграда. События и афиши взяты из открытых постов
канала https://t.me/signalkld, права на них у организаторов. Логотип Сигнала используется с их разрешения.

Сайт: https://alexhenderson555.github.io/signal-schedule/
Подписка на календарь: https://alexhenderson555.github.io/signal-schedule/signal.ics

## Как это работает

Дважды в день (05:00 и 15:00 UTC) GitHub Actions (`.github/workflows/update.yml`) запускает цепочку:

1. `fetch.py` читает публичную ленту канала и сохраняет афиши в `images/` (WebP).
2. `extract.py --write` разбирает свежие посты через Gemini в `events.json`. Каждое событие обязано
   нести цитату из поста, иначе оно отбрасывается. Разобранные посты кешируются в `cache.json`.
   Ручные поправки лежат в `overrides.json` и переживают обновления.
3. `build.py` вшивает данные в `index.html` и собирает `signal.ics`.
4. `review.py` пишет `review.md`: события, на которые стоит посмотреть глазами.
5. `make_og.py` рисует превью для ссылки (`og.png`).

Если разбор упал или вернул подозрительно мало событий, изменения не коммитятся и сайт остаётся прежним.

## Локально

```
pip install -r requirements.txt
python fetch.py 10
python extract.py --write      # нужен GEMINI_API_KEY в окружении
python build.py && python review.py && python make_og.py
```
