# Unified Data Collector

Одна локальная команда для всех текущих наборов данных D2Helper:

- `hero_matchups.new.json` — STRATZ, последние три завершённые недели;
- `hero_stats.new.json` и `hero_detailed_stats.new.json` — один подробный
  STRATZ-запрос без дублирования;
- `dota_builds.new.json` — проверенный экспорт Dota2ProTracker;
- `collection-report.json` — общий отчёт о сборе.

Все результаты создаются в `.runtime/data-collector/`; рабочие файлы проекта,
staging и production команда не изменяет.

## Dota2ProTracker

Прямой запрос D2PT API из Python сейчас получает Cloudflare `403`. Поэтому
первым запускается существующий браузерный скрипт D2PT: на странице сервиса он
скачивает `dota_builds.json`. Этот файл передаётся общей команде через
`--d2pt-input`; она проверит полный набор героев, поля сборок и согласованность
win rate перед тем, как добавить его к результатам.

## macOS

```bash
source .venv/bin/activate
export STRATZ_API_TOKEN="..."
python -m tools.data_collector \
  --project-root . \
  --d2pt-input ~/Downloads/dota_builds.json \
  --output-dir ./.runtime/data-collector
```

После успешной команды проверь `collection-report.json` и новые JSON-файлы.
Публикация на staging и production остаётся отдельным ручным действием.
