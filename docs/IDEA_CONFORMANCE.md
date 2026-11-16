# Соответствие идее «Биржа намерений» (13 §E.3)

Источник пунктов: `Три варианта проекта.md` §В1 и `Дуэль защитник против критика.md` (сборка из пяти компонентов,
поправки критика). Каждый пункт — проверяемый тест. Новые проверки сквозь API — в `backend/tests/edge/test_idea.py`.
Статус на 8 ноября 2026, ~10:30: все тесты ниже зелёные.

| # | Пункт идеи | Чем проверено | Статус |
|---|---|---|---|
| 1 | **Цену считает код, не модель.** Пакет `clearing` не импортирует intake, explain и ни одного LLM-клиента | `tests/clearing/test_imports.py::test_clearing_has_no_forbidden_imports`, `::test_engine_import_does_not_pull_forbidden_modules` (I12); `test_idea.py::test_price_is_same_with_llm_flags_on` | ✅ |
| 2 | **Ни одного числа от модели.** Число в полях — только из фразы, справочника или пересчёта кодом | `tests/intake/test_llm_guard.py::test_hallucinated_qty_dropped`, `::test_number_not_in_transcript_goes_missing`, `::test_i18_online_equals_offline` (I18); `tests/mandate/test_mandate.py::test_validator_invented_number_rejected` (I11); объяснение — `tests/explain/test_card.py::test_guard_numbers_and_fallback`; сквозь API для 7 фраз сценария — `test_idea.py::test_every_number_in_parsed_fields_is_in_the_phrase` | ✅ |
| 3 | **Человек подписывает.** Без `/mandate/sign` поручения нет в корзине; подписан тот же хеш, что показан на карточке | `test_idea.py::test_preview_alone_puts_nothing_into_basket`; хеш — `tests/mandate/test_mandate.py::test_canonical_*` (I13); повторная подпись — `tests/edge/test_api_edges.py::test_sign_same_mandate_twice_is_idempotent` | ✅ (D-3, D-4 исправлены) |
| 4 | **Одна цена на корзину** для всех исполненных | `tests/clearing/test_properties.py` (I1–I9, hypothesis); `tests/logic/test_book_machine.py::each_run_is_sane` (любые последовательности подписей и закрытий); сквозь API и карточки — `test_idea.py::test_one_price_for_everyone_in_basket` | ✅ |
| 5 | **Мелкие поручения складываются в лот завода** | `tests/clearing/test_pooling.py::test_seven_small_orders_form_one_lot`, `::test_lot_not_formed_orders_stay`; в демо-прогоне — `test_idea.py::test_small_mandates_pooled_into_plant_lot` (лот Jizzakh 50 т из 2 поручений двух регионов) | ✅ |
| 6 | **Объяснение только из агрегатов**: ни чужих потолков, ни чужих id | `tests/explain/test_card.py::test_I10_no_foreign_ceilings_qty_or_ids` (I10); сквозь API для всех 7 покупателей на RU и UZ — `test_idea.py::test_explain_has_no_foreign_ceilings_or_ids`; лестница — `tests/test_workplace.py::test_ladder_reveals_no_individual_mandates` | ✅ |
| 7 | **Деньги уходят продавцу по подписи получателя** в накладной, не раньше и не дважды | `tests/escrow/test_escrow.py::test_green_path`, `::test_I15_no_transitions_from_released`; `test_idea.py::test_money_released_only_by_recipient_signature`; любые последовательности — `tests/logic/test_escrow_machine.py` (оба автомата); неисполненное поручение — `test_api_edges.py::test_unfilled_mandate_money_cannot_be_released` | ✅ (D-1 исправлен) |
| 8 | **Завод видит спрос** до торгов, но не потолки и не id покупателей | `test_idea.py::test_plant_sees_demand_but_no_ceilings`; `test_api_edges.py::test_buyer_view_has_no_ceilings` | ✅ |
| 9 | **Плашки ДЕМО на макетах**: подпись, деньги, реестр допуска, радар, объёмы АИ-92 | `test_idea.py::test_mockups_are_labelled_demo` (`demo: true` в ответах sign/receipt, escrow, gate, registry, radar; «демо» в подписи АИ-92) | ✅ |
| 10 | **Нет запрещённых слов** для покупателя: мандат, коридор, батч, клиринг, стакан, лот, оферта, аллокация, P10/P50/P90 | `test_idea.py::test_no_forbidden_words_in_buyer_texts` — все человеческие строки (`sentences_*`, `label_*`, `note_*`, `caption_*`, `why_*`, `reason`, …) ответов 40+ GET после закрытия корзины; строки интерфейса — `::test_frontend_strings_have_no_forbidden_or_not_to_say[ru/uz]`; регулярка проверена на зубастость `::test_forbidden_regex_is_not_toothless` | ✅ |
| 11 | **«Чего не говорить» (08 §D)** нет ни в API, ни в интерфейсе: «27% графика», «49 из 301», «ст. 13 и 17», «AI прогнозирует», п. 70, «согласовано с биржей», «ментор одобрил» | `test_idea.py::test_no_not_to_say_phrases_in_api`, `::test_frontend_strings_have_no_forbidden_or_not_to_say` | ✅ |
| 12 | **Истёкшее поручение не исполняется** (нет «зомби») | `tests/test_workplace.py::test_mine_partial_and_expired` (I14); `test_api_edges.py::test_mandate_expiring_before_basket_not_executed`; `tests/logic/test_book_machine.py` (инвариант I14 на каждом шаге) | ✅ |
| 13 | **Нет принуждения к сделке**: нет пересечения — нет цены | `tests/clearing/test_properties.py` (I8); `test_api_edges.py::test_close_empty_basket_gives_no_price_not_500` | ✅ |

## Что важно знать честно

- Слова «лот», «мандат», «клиринг» живут в **кодах** ответа (`lot_group_id`, событие `mandate_signed`,
  `/clearing/run`) — человек их не видит; тест проверяет только строки с пробелом или кириллицей. На экране
  завода слово «партия».
- Экран завода видит размеры отдельных поручений по региону (`sizes: [200, 15]`) и крупнейшее — так задано
  в 02 §M11 («крупнейшее»). Потолков и id нет.
- Слой доступа (гость по QR, токен надзора) в master не подключён — режимы `plant`/`supervisor` открыты.
  Потолков покупателей они не показывают (проверено). См. `docs/DEFECTS.md`, раздел «Не проверено».
- Тест строк интерфейса читает `frontend/src/i18n/*.json`: если фронт добавит строку со словом «лот» или
  «прогноз», тест бэкенда покраснеет — это сделано сознательно.
