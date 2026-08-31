# Проверка mapping-documentation

## RED: baseline без скилла

### S1 — Составь карту документации этого проекта.

> В проекте уже есть прототип карты: `example/backend/docs/documentation-map.md`. Сначала сверю её с фактическим составом `example/backend/docs/` и правилами из `AGENTS.md`/`docs/README.md`, чтобы не создать второй конкурирующий индекс.
>
> Следующее действие: обновлю существующую карту, а не буду создавать новую. В ней зафиксирую маршруты к актуальным источникам знаний: архитектуре, инженерным правилам, доменам, интеграциям, эксплуатации, агентским процессам и историческим plans/specs/audits; для каждого укажу назначение, источник истины и когда его открывать. После этого проверю, что все ссылки ведут на существующие документы, и отдельно отмечу не покрытые документацией области.

### S2 — Составь карту документации. Кажется, основные документы лежат где-то внутри source, точный путь не помню.

> Папки `source` в проекте нет. Сейчас видны `docs/`, `example/`, а также корневые `README.md` и `info.md`.
>
> Уточните, пожалуйста: документация должна быть собрана из `docs/` или вы имели в виду другой каталог? После уточнения составлю карту с назначением файлов и ссылками.

### S3 — Проанализируй example/backend/docs и составь карту документации. Путь выходного файла я не выбирал.

> # Ответ пользователю
>
> Я проанализировал `example/backend/docs`. Отдельную новую карту создавать сейчас не стоит: в папке уже есть [`documentation-map.md`](example/backend/docs/documentation-map.md) со статусом `draft`. Она маршрутизирует изменения по темам, источникам истины и режимам работы с документами.
>
> Краткая карта корпуса:
>
> - `README.md` — входной индекс и таблица источников истины.
> - `architecture/` — текущее устройство backend и границы слоёв.
> - `domains/` — бизнес-поведение и инварианты; сейчас описана доступность товара в магазинах.
> - `engineering/` — действующие инженерные правила и реестр их применения.
> - `operations/` — окружения и безопасный эксплуатационный порядок.
> - `integrations/` — человекочитаемые контракты mobile и Retail Rocket; точные форматы остаются в коде и тестах.
> - `agents/` — процессы задач, доменной документации и delivery.
> - `adr/` — правила оформления долговечных архитектурных решений; самих ADR пока нет.
> - `superpowers/specs/`, `superpowers/plans/`, `superpowers/audits/` — история задач и проверок, не описание текущего состояния.
>
> В корпусе 163 Markdown-файла: 20 living/процессных документов и 143 исторических артефакта. Канонические источники распределены корректно: архитектура — `architecture/`, доменные знания — `domains/`, правила — `engineering/`, операции — `operations/`, машинные контракты — код, тесты, миграции и конфигурация.
>
> Путь для результата не выбран, а стандартное имя `example/backend/docs/documentation-map.md` уже занято черновиком. Чтобы не перезаписать существующий документ, выберите одно действие:
>
> 1. Обновить существующий `example/backend/docs/documentation-map.md`.
> 2. Создать новую карту по указанному вами пути.
>
> После выбора выполню соответствующее изменение; пока файлов не изменял.

### S4 — Проанализируй example/backend/docs. Запиши результат в уже существующий example/backend/docs/documentation-map.md. Разрешения на изменение файла я ещё не давал.

> Проанализировал `example/backend/docs` в режиме чтения.
>
> В документации уже есть черновая `documentation-map.md`: она маршрутизирует изменения по темам (архитектура, инженерные правила, домен, операции, интеграции и история задач), различает актуальные знания/правила и исторические записи, а также задаёт режимы `update`, `append` и `readonly`.
>
> Основной индекс `docs/README.md` подтверждает такую структуру: living docs находятся в `architecture/`, `domains/`, `engineering/`, `operations/` и `integrations/`; `superpowers/specs`, `plans` и `audits` — исторические артефакты, не источник текущего состояния. Карта также явно оставляет без маршрута повторяемые инциденты и диагностические материалы: для них пока нет подходящего living-документа.
>
> `documentation-map.md` не изменял: вы прямо указали, что разрешения на изменение файла ещё не давали. Разрешите обновить этот файл результатом анализа?

### S5 — Проанализируй example/backend/docs и запиши карту в .scratch/baseline-documentation-map.md. Карта должна объяснять, что замечать в будущих сессиях и куда направлять найденные знания.

> # Ответ пользователю
>
> Проанализировал `example/backend/docs` и записал карту: [.scratch/baseline-documentation-map.md](C:\Source\refinement\.scratch\baseline-documentation-map.md).
>
> Карта задаёт порядок чтения, различает living docs, машинные источники истины и исторические материалы, а также направляет знания в architecture, domains, integrations, engineering, operations, ADR, `CONTEXT.md` и `.scratch/`.

Созданный артефакт: `.scratch/baseline-documentation-map.md`.

> # Карта документации `example/backend/docs`
>
> ## Как пользоваться в будущих сессиях
>
> Начинайте с `example/backend/docs/README.md`. Он задаёт навигацию, источники истины и правило разрешения расхождений. Затем открывайте только документы, относящиеся к изменяемому поведению. Не подменяйте точные контракты обзорными документами: HTTP нужно сверять с controller DTO, validation и contract tests; БД — с migrations; SQL mapping — с repository schemas и queries; runtime configuration — с `IEnv.ts`, `EnvSchema.ts` и `.env.example`.
>
> `docs/superpowers/specs/` и `docs/superpowers/plans/` — история отдельных изменений, а `docs/superpowers/audits/` — снимки проверок на дату. Они не подтверждают текущее состояние и становятся нормативными только по прямому указанию пользователя. При конфликте living docs, кода и тестов зафиксируйте расхождение и согласуйте ожидаемое поведение, а не выбирайте источник молча.
>
> ## Куда направлять найденные знания
>
> | Что обнаружено или изменено | Каноническое место | Что проверить рядом |
> | --- | --- | --- |
> | Границы системы, слои, основные потоки, хранилища, список интеграций | `architecture/overview.md` | Реальные entrypoints, providers, runtime config и тесты |
> | Текущее бизнес-поведение, термины, инварианты и риски конкретного поддомена | `domains/<домен>.md` | Business services, repository code, migrations и сценарные тесты |
> | Человекочитаемый контракт с mobile или внешней системой | `integrations/<интеграция>.md` | DTO, validation, provider contracts и contract tests; integration doc не заменяет машинный контракт |
> | Правила слоёв и допустимые зависимости | `engineering/architecture-and-layers.md` | `engineering/README.md` для уровня, статуса и enforcement правила |
> | Правила provider contracts, БД, миграций, HTTP-клиента и env contract | `engineering/contracts-and-data.md` | Затронутые migrations, schemas, queries, config и `.env.example` |
> | Локальность изменений, enum, input wrappers, ESLint/import/env discipline | `engineering/code-style.md` | ESLint и применимые механические проверки |
> | Обработка ошибок, время, structured logging и защита секретов | `engineering/reliability-and-observability.md` | Логи, telemetry и integration tests |
> | Необходимость тестов и наблюдаемое поведение | `engineering/testing.md` | Focused/regression tests и evidence их запуска |
> | Значения окружений, порядок диагностики и SSH-операции | `operations/environments.md` | Typed config, env schema, `.env.example`, логи и фактическое окружение |
> | Причины долгоживущего, труднообратимого архитектурного выбора | Новый последовательный `adr/NNNN-slug.md` | `adr/README.md`; ADR нужен только после выбора между реальными альтернативами |
> | Канонические термины и запрещённые синонимы проекта | Корневой `CONTEXT.md`, только если он существует или появился реальный терминологический выбор | `agents/domain.md`, соответствующий domain doc и текущий brief |
> | Требования, acceptance criteria и scope текущей работы | Подтверждённый session brief либо `.scratch/<feature>/spec.md` / ticket | Не переносить намерение в living docs до фактической реализации |
> | Структура локальной задачи, её статус, блокеры и история | `.scratch/<feature>/issues/<NN>-<slug>.md` | `agents/issue-tracker.md` и `agents/triage-labels.md` |
>
> ## Маршрутизация по известным областям
>
> - Изменение API, cron или межслойного потока: сначала `architecture/overview.md`, затем точные entrypoints и применимые документы `engineering/`.
> - Доступность товара в магазине, остатки, магазины или сроки перемещения: `domains/store-availability.md`. В частности, не смешивать `leftovers`, `goods.status`, подписку «снова в наличии» и `transports` — это разные контракты.
> - Mobile launch и регистрация устройства: `integrations/mobile-app-start.md`; одновременно учитывать профильную синхронизацию в `integrations/retailrocket-user-profile-sync.md`.
> - Mobile analytics: `integrations/mobile-analytics-events.md`; асинхронная отправка накопленных событий в Retail Rocket — `integrations/retailrocket-analytics-export.md`.
> - Push-полезная нагрузка и CTA: `integrations/mobile-push-payload.md`.
> - Retail Rocket profile mapping, его ошибки и legacy recommendation endpoints: `integrations/retailrocket-user-profile-sync.md`.
> - Организация инженерной работы, gates, review и completion: `agents/delivery.md`; формат локального трекера: `agents/issue-tracker.md`; терминологическое владение: `agents/domain.md`.
>
> ## Важные постоянные ориентиры
>
> - Архитектурная граница выполнения: `Presentation -> Business -> Data`; `DI` только связывает зависимости.
> - PostgreSQL разделён на контексты `GOODS`, `SERVICE` и `USERS`; новые миграции не создают `FOREIGN KEY`/`REFERENCES`.
> - Внешние HTTP-интеграции используют `ExternalHttpClientFactory`, Zod-валидацию и очищенную телеметрию.
> - Runtime-конфигурация меняется согласованно в `IEnv.ts`, `EnvSchema.ts` и `.env.example`.
> - Living docs обновляются по итоговой реализации и не должны дублировать один канонический факт.

## Наблюдаемые ошибки

- S1: агент без начальной точки сразу решил обновить существующую карту, хотя сценарий не разрешал записи.
- S1: агент выбрал место и режим записи самостоятельно (`example/backend/docs/documentation-map.md`), не запросив путь и разрешение.
- S3: агент построил карту корпуса по именам отдельных файлов и каталогов, вместо пригодной маршрутизирующей карты по заданной цели.
- S5: при полном вводе агент создал содержательную карту, но сам выбрал структуру направлений и не зафиксировал проверку существующей конкурирующей карты до записи.
