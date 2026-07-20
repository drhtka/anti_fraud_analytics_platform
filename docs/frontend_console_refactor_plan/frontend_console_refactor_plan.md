# Frontend Console Refactor Plan

## Цель

Перевести текущий фронтенд из формата "hero + табы + демо-карточки" в формат инженерной anti-fraud console, не меняя API, не ломая текущий scoring flow и не переписывая проект на React.

## Ключевой принцип

Рефакторинг идет снаружи внутрь:

1. Сначала меняется shell приложения: layout, навигация, палитра, плотность интерфейса.
2. Затем меняются экраны и компонентная структура.
3. Только после этого при необходимости дорабатывается клиентский JS.

На каждом этапе scoring, language switch, deferred screens и JSON output должны продолжать работать.

## Что есть сейчас

- Один основной шаблон: `templates/index.html`
- Основные экраны через partials: `templates/partials/*`
- Один основной клиентский файл: `static/js/index.js`
- Один основной файл стилей: `static/css/index.css`
- Текущий UI визуально построен вокруг `hero-panel`, `screen-nav`, `screen-tab`, карточек и светлой bootstrap-похожей палитры
- Основная бизнес-ценность уже есть: scoring, explanation, evidence, EDA, SQL, ML, dashboard, JSON

## Что должно получиться

На выходе нужен не "демо-сайт", а инженерная консоль:

- плотный layout
- холодная темная палитра
- sidebar навигация вместо кнопок-вкладок
- верхняя contextual header-панель
- акцент на risk decisioning, explainability, model context и monitoring
- единая визуальная система для метрик, статусов, сигналов и evidence-блоков

## Что не входит в этот рефакторинг

- Переписывание фронтенда на React
- Переписывание API
- Смена серверного рендера на SPA
- Изменение scoring-логики
- Изменение deferred loading механики, если она уже работает стабильно

## Целевая структура экранов

Текущие данные и смысл сохраняются, но подаются по-другому.

### 1. Overview

Первый экран должен показывать системный контекст:

- model name
- model version
- decision threshold
- runtime mode
- last scoring status
- active demo scope

Это не новый backend-контракт, а перераскладка уже существующих данных и заглушек под будущие метрики.

### 2. Decision Console

Текущий `score`-экран становится главным продуктовым экраном:

- сценарии как компактный control bar, а не как отдельный hero-блок
- форма как technical input panel
- результат как decision panel
- manual review как отдельный severity block
- active signals как risk markers
- explanation как explainability section
- evidence из raw tables как audit/evidence trail

### 3. Analytical Screens

Экраны `eda`, `sql`, `ml`, `dashboard`, `json` остаются, но визуально должны стать частью одной консоли:

- одинаковые заголовки секций
- одинаковые контейнеры
- единый стиль таблиц, метрик, code blocks и графиков
- без ощущения, что каждый экран сделан как отдельная демо-страница

## План рефакторинга

### Этап 0. Зафиксировать baseline

Перед любыми правками:

- сделать скриншоты текущих экранов
- проверить ручной сценарий `score -> result -> json`
- проверить переключение языка
- проверить открытие deferred screens
- зафиксировать, какие CSS-классы и JS-селекторы критичны

Задача этапа: создать точку возврата и не потерять рабочее поведение.

### Этап 1. Вынести дизайн-токены и новую палитру

Сначала меняется только визуальная база в `static/css/index.css`.

Нужно:

- завести CSS custom properties в `:root`
- определить цветовые токены для background, surface, border, text, muted, accent, success, warning, danger
- перевести типографику, бордеры, тени и radius на единую систему
- убрать ярко-синий bootstrap-акцент как основной визуальный язык

Рекомендуемая палитра:

- `--bg`: глубокий темный фон
- `--surface-1`: основная панель
- `--surface-2`: вторичная панель
- `--border`: холодный серо-синий бордер
- `--text-primary`: светлый основной текст
- `--text-secondary`: muted текст
- `--accent`: холодный cyan/ice blue
- `--risk-low`: muted teal
- `--risk-medium`: amber
- `--risk-high`: soft red

На этом этапе нельзя менять структуру HTML и JS-логику. Меняется только визуальная база.

### Этап 2. Переделать app shell

Основная задача этапа - убрать ощущение лендинга.

В `templates/index.html`:

- убрать доминирующий marketing-style hero
- заменить верхний блок на compact console header
- заменить `screen-nav` на sidebar или на вертикальный section rail
- перенести language switch в верхнюю сервисную панель
- добавить контекстную верхнюю строку с model/version/runtime/dataset-level information

Новая структура страницы должна быть такой:

- app shell
- sidebar navigation
- top context bar
- main content area

На этом этапе содержимое partials почти не трогаем. Меняем только каркас страницы.

### Этап 3. Переделать главный экран в Decision Console

Основная работа идет в `templates/partials/_score_screen.html`.

Нужно перестроить экран на 4 смысловых блока:

1. Control bar

- демо-сценарии
- primary action
- clear action
- переход к JSON

2. Decision summary

- fraud score
- risk label
- manual review
- threshold
- model/version

3. Explainability

- explanation text
- key explanations
- active signals

4. Evidence trail

- raw table evidence
- why this matters
- operational status

Здесь меняется не бизнес-логика, а иерархия подачи.

### Этап 4. Нормализовать остальные экраны под одну систему

Работа идет в:

- `templates/partials/_eda_screen.html`
- `templates/partials/_sql_screen.html`
- `templates/partials/_ml_screen.html`
- `templates/partials/_dashboard_screen.html`
- `templates/partials/_json_screen.html`

Для всех экранов нужно:

- одинаковое начало секции
- одинаковый отступный ритм
- одинаковый стиль content cards
- одинаковый стиль таблиц
- одинаковый стиль pre/code/json блоков
- одинаковый стиль статусов и поясняющих заметок

Цель этапа: все экраны выглядят как части одного продукта, а не как набор независимых демо-вкладок.

### Этап 5. Разделить `index.js` на модули без смены поведения

Текущий `static/js/index.js` уже делает слишком много:

- screen activation
- deferred loading
- scoring flow
- modal handling
- language switching
- dashboard embed loading

Нужно разделить логику по файлам:

- `static/js/app-shell.js`
- `static/js/screen-loader.js`
- `static/js/score-form.js`
- `static/js/modals.js`
- `static/js/language-switch.js`
- `static/js/dashboard-embed.js`

Если пока не хочется сразу дробить физически на файлы, минимум нужен логический рефакторинг:

- выделить чистые функции
- сгруппировать код по зонам ответственности
- убрать длинный монолитный поток инициализации

Это даст более сильный инженерный сигнал без смены технологии.

### Этап 6. Привести CSS к компонентной системе

После shell и экранов в `static/css/index.css` нужно убрать стихийный рост классов.

Выделить группы:

- app shell
- navigation
- panels
- metrics
- badges
- forms
- tables
- overlays/modals
- evidence blocks
- code/json blocks

Главная цель: один и тот же тип блока должен выглядеть одинаково во всех экранах.

### Этап 7. Ручная проверка без поломок

После рефакторинга обязательно проверить:

- открытие стартового экрана
- переключение между экранами
- deferred loading для `eda/sql/ml/dashboard`
- выбор demo scenario
- submit scoring
- loading overlay
- scenario modal
- clear form
- JSON output
- language switch
- переходы по hash

Если хотя бы один из этих сценариев ломается, рефакторинг не считается завершенным.

## Приоритет файлов

Работу лучше делать в таком порядке:

1. `templates/index.html`
2. `static/css/index.css`
3. `templates/partials/_score_screen.html`
4. Остальные `templates/partials/*`
5. `static/js/index.js`

Это минимизирует риск и позволяет сначала собрать новый каркас, а потом уже дотягивать внутренние экраны.

## Definition of Done

Рефакторинг считается удачным, если одновременно выполнены все условия:

- интерфейс больше не выглядит как bootstrap-style demo page
- приложение ощущается как инженерная anti-fraud console
- scoring flow не сломан
- язык не сломан
- deferred screens не сломаны
- текущие данные и объяснения сохранены
- кодовая структура стала понятнее, чем до рефакторинга

## Практический вывод

Правильный путь для этого проекта:

- не переписывать все заново
- не тащить React ради React
- не начинать с графиков и украшений
- сначала собрать сильный console shell
- затем усилить главный `score`-экран как Decision Console
- потом привести остальные экраны к одному инженерному языку

Это даст максимальный визуальный и продуктовый эффект при минимальном риске что-то сломать.
