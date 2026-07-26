# STRATZ Lane Collector

Локальный исследовательский сборщик данных `heroStats.laneOutcome`. Он создаёт
отдельный `hero_lanes.new.json` и не меняет текущую формулу драфтера, рабочие
JSON-файлы, staging или production.

## Какие данные собираются

Для трёх последних завершённых недель отдельно собираются:

- `with` — результаты линии при игре героев вместе;
- `against` — результаты линии друг против друга;
- позиции `POSITION_1`–`POSITION_5`;
- `matchCount`, обычные W/D/L, stomp W/L, победы в матче и CS.

Строки разных недель и рангов суммируются по направленной паре
`heroId1 → heroId2` и позиции. Никакой производный lane score в файл пока не
записывается: формулу можно исследовать отдельно на staging после проверки
покрытия и размеров выборки.

## Подготовка на macOS

Нужен Python 3.12.3. Можно использовать уже настроенное окружение STRATZ:

```bash
source .runtime/stratz-venv/bin/activate
python -m pip install -r tools/stratz_lane_collector/requirements.txt
export STRATZ_API_TOKEN="..."
```

Если STRATZ отвечает `403`, отключи VPN или прокси и повтори запуск.

## Запуск

```bash
python -m tools.stratz_lane_collector \
  --hero-reference ./.runtime/stratz/hero_matchups.json \
  --output ./.runtime/stratz/hero_lanes.new.json
```

Reference-файл используется только для полного списка игровых героев. Новый
файл записывается атомарно только после проверки, что оба набора (`with` и
`against`) содержат всех игровых героев и ненулевые данные.

## Тесты

```bash
python -m unittest discover -s tools/stratz_lane_collector/tests -v
```
