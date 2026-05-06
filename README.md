# 🧠 Claude Memory Manager

Веб-интерфейс для просмотра, редактирования и аудита всего, что Claude Code держит локально: auto-memory, глобальный и проектные `CLAUDE.md`, MCP-серверы, settings и сессионные логи.

## Проблема

Хабр-статья [«Я случайно нашёл собственное досье у Claude. И залип на 3 часа в его памяти»](https://habr.com/ru/articles/1031382/) хорошо суммирует, что Claude параллельно ведёт **пять независимых уровней памяти**:

1. `CLAUDE.md` — постоянно подгружаемый контекст
2. **Auto-memory** в `~/.claude/projects/<id>/memory/` — Claude сам решает, что записать про тебя и проект
3. **Auto-compact** — сжимает историю длинной сессии, иногда теряя детали
4. **Subagents** — отдельные сессии со своим контекстом
5. **MCP Memory / hooks** — долгоживущие внешние хранилища

Из этого вытекают практические боли:

- **Непрозрачность.** Какие правила Claude уже записал про твой стиль, привычки, проекты — неясно. Автор статьи прямо советует *«раз в неделю-две стоит зайти в папку и посмотреть, что Claude себе записал»*. Через файловый менеджер делать это невозможно — там сотни файлов, разбитых по encoded-путям проектов, плюс глобальные конфиги ещё в трёх местах.
- **Устаревшие правила.** Записи деградируют — фидбек, который был верен полгода назад, мешает сегодня. Их надо периодически чистить — но руками `cat` + `vim` это душно.
- **Контекст-нагрузка.** Файлы памяти грузятся в **каждый** промпт. Чем больше — тем дороже сессия и быстрее съедается context window. Размер в токенах нигде не показан.
- **Конфигурация раскидана.** Глобальный `~/.claude/CLAUDE.md`, проектные `<repo>/CLAUDE.md`, `~/.claude/.mcp.json`, `~/.claude/settings.json`, `<repo>/.claude/settings.json` — у каждого свой путь, разные форматы (md / json), и нигде нет сводного вида.
- **Чёрный ящик аудита.** Что Claude **реально** прочитал/правил в твоей сессии — лежит в JSONL-логах `~/.claude/projects/<id>/*.jsonl`, но без UI это нечитаемо.

## Решение

### Memory Files
- Все memory-файлы сгруппированы по проектам, с фронтматтером (`name`, `description`, `type`) и markdown-превью
- **Preview / Edit / RAW** — три режима: рендер, редактор с парсингом frontmatter, и прямая правка исходного `.md`
- Полнотекстовый поиск по всем memory сразу (Ctrl+K)
- Реальный путь к файлу на хосте прямо в шапке — копируй и открывай в редакторе

### Global Config
Отдельная секция «Global Config» с быстрым доступом и редактированием:
- `~/.claude/CLAUDE.md` — глобальные инструкции
- `~/.claude/settings.json`, `settings.local.json`
- `~/.claude/.mcp.json` — глобальные MCP-серверы

### Project Config
Внутри каждого проекта подсекция «Config» — для файлов, лежащих в **реальном** рабочем каталоге проекта, а не в `~/.claude/`:
- `<project>/CLAUDE.md`
- `<project>/.claude/settings.json`, `settings.local.json`

### Token Counter
У каждого markdown-файла есть оценка размера в **токенах** (heuristic: ASCII / 4 + non-ASCII / 1.5). Сразу видно, какие memory-файлы тяжёлые и грузят контекст. Сумма по проекту в сайдбаре, общая сумма по секции в заголовке.

### Activity — аудит сессий
Просмотрщик JSONL-логов с **lazy-парсингом**: список сессий открывается мгновенно (только `stat()` + первые 30 строк для превью), полный парсинг — только при клике на конкретную сессию. Per-file mtime-кэш делает повторные открытия моментальными.

Для каждой сессии — два таба:
- **Token Burn** — Chart.js stacked-bar по дням; четыре дорожки: input / output / cache create / cache read. Видно, на что реально уходят токены
- **File Graph** — force-directed граф (Cytoscape + fcose). Узлы = файлы, размер = сколько раз их трогали, цвет = по расширению. Рёбра = временная близость двух файлов в потоке tool-calls. Hover подсвечивает соседей и показывает breakdown по тулзам (Read / Edit / Write)

### Безопасность
- Перед каждой записью или удалением — автобэкап `.bak` рядом с файлом
- Опциональный `READ_ONLY=true` в `docker-compose.yml`
- Path traversal защита, валидация имён файлов

## Запуск

Нужен только Docker.

```bash
./run.sh
```

Скрипт находит свободный порт, билдит образ, поднимает контейнер, ждёт готовности и открывает браузер. Работает на macOS, Linux, Git Bash / WSL под Windows.

Если хочется фиксированный порт:
```bash
HOST_PORT=8081 docker compose up -d --build
```

## Поддержка ОС

Пути определяются автоматически по формату `HOST_HOME_REAL`:

| ОС | `~/.claude` mount | Глобальный CLAUDE_DIR |
|----|-------------------|------------------------|
| macOS / Linux | `~/.claude` | `~/.claude` |
| Windows (Git Bash / WSL) | `${USERPROFILE}/.claude` | `${USERPROFILE}/.claude` |

В контейнере `~/.claude` смонтирован как `/data:rw`, а домашняя директория — как `/host-home:ro` (нужна для доступа к `<project>/CLAUDE.md` в реальных рабочих каталогах). Внутреннему коду пути транслируются обратно в host-формат для UI — пользователь видит знакомые `/Users/alex/...` или `C:\Users\alex\...`, а не Docker-внутренние `/host-home/...`.

## Карта памяти Claude

```
~/.claude/                          ← глобальный config-dir
├── CLAUDE.md                       ← глобальные инструкции          [Global Config → CLAUDE.md]
├── settings.json                   ← глобальные настройки           [Global Config → settings.json]
├── settings.local.json                                              [Global Config → settings.local.json]
├── .mcp.json                       ← глобальные MCP-серверы         [Global Config → .mcp.json]
└── projects/<encoded-path>/
    ├── *.jsonl                     ← transcripts сессий              [Activity → Sessions]
    ├── memory/                     ← auto-memory                     [Projects → <project> → Memory Files]
    │   ├── MEMORY.md               ← индекс
    │   ├── user_*.md
    │   ├── feedback_*.md
    │   ├── project_*.md
    │   └── reference_*.md
    └── ...

<project-root>/                     ← реальный каталог проекта
├── CLAUDE.md                       ← инструкции уровня проекта       [Projects → <project> → Config]
└── .claude/
    ├── settings.json                                                 [Projects → <project> → Config]
    └── settings.local.json
```

## Архитектура

- **FastAPI** + uvicorn — REST API, сервит SPA
- **Alpine.js + Tailwind (CDN)** — без бандлера, всё в одном `index.html`
- **Cytoscape.js** + `fcose` — force-directed граф файлов
- **Chart.js** — стэк-бар токенов
- **Парсинг JSONL** — стримом, кэш per-file по mtime
- **Резолвинг хостовых путей** — BFS по `/host-home` со сравнением encoded-пути (Claude кодирует non-ASCII-alnum символы как `-`); работает с кириллицей и любыми non-Latin путями

## API

| Метод | URL | Назначение |
|-------|-----|------------|
| `GET` | `/api/projects` | Список проектов с подсчётом токенов |
| `GET` | `/api/memories?project_id=` | Список memory-файлов |
| `GET/PUT/POST/DELETE` | `/api/memories/file?project_id=&filename=` | CRUD memory с парсингом frontmatter |
| `GET/PUT` | `/api/memories/raw?project_id=&filename=` | RAW-доступ к содержимому |
| `GET/PUT` | `/api/global/file?name=` | Глобальные конфиги |
| `GET/PUT` | `/api/project-config/file?project_id=&name=` | Конфиги уровня проекта |
| `GET` | `/api/logs/sessions?project_id=&days=` | Список сессий (lazy) |
| `GET` | `/api/logs/session-detail?session_id=&project_id=` | Полный парсинг одной сессии |
| `GET` | `/api/search?q=` | Полнотекстовый поиск по memory |

## Структура проекта

```
.
├── app/
│   ├── main.py                  # FastAPI app, регистрация роутеров
│   ├── config.py                # CLAUDE_DIR, OS detection, host-path translation
│   ├── models.py                # Pydantic модели
│   ├── services/
│   │   ├── fs.py                # CRUD файлов, поиск проектного пути на хосте
│   │   ├── parser.py            # frontmatter parse/render
│   │   └── logs.py              # JSONL parser + per-file mtime cache
│   └── router/
│       ├── projects.py          # /api/projects
│       ├── memories.py          # /api/memories[/raw|/file]
│       ├── global_files.py      # /api/global
│       ├── project_config.py    # /api/project-config
│       ├── search.py            # /api/search
│       └── logs.py              # /api/logs
├── frontend/
│   └── index.html               # SPA: Alpine + Tailwind + Chart.js + Cytoscape
├── docker-compose.yml
├── Dockerfile
└── run.sh                       # auto-port + browser open
```

## Ссылки

- [Хабр: «Я случайно нашёл собственное досье у Claude. И залип на 3 часа в его памяти»](https://habr.com/ru/articles/1031382/) — статья, после которой захотелось сделать UI для всего этого

## Лицензия

MIT
