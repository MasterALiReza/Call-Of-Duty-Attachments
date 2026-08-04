# TODO ????? ????? ??????

????? ???????????: `2026-03-06`
????: [ARCHITECTURE_AUDIT_FA_2026-03-03.md](C:/Users/Dell/Documents/Ox-Loadout-main/ARCHITECTURE_AUDIT_FA_2026-03-03.md)
????? ??????: `Production Risk`

## ????? ???

- ??? `0-2 ????`: ?????? ???? ??? ? wave??? ????? ???? ??? ?????.
- wave ?????? ????: `Wave-1`
- ????? ???: `pytest -q` ???? `compileall` ???? CI subset ???? `ruff` ? `mypy` ???.

## Checklist ??????????

- `[done] TD-01` ???????????? ???? bootstrap ? ??? fallback??? legacy schema
  - `done`: ??? ???? ?????? `setup_database.sql` ?? [deploy.sh](C:/Users/Dell/Documents/Ox-Loadout-main/deploy.sh)
  - `done`: ??? ???? ?????? `setup_database.sql` ?? [scripts/ox-loadout](C:/Users/Dell/Documents/Ox-Loadout-main/scripts/ox-loadout)
  - `done`: ??????????? [scripts/health_check.py](C:/Users/Dell/Documents/Ox-Loadout-main/scripts/health_check.py) ???? `setup_database.py + init_postgres.sql + migrations`
  - `done`: ????? ??? `--migrate-only` ?? [scripts/setup_database.py](C:/Users/Dell/Documents/Ox-Loadout-main/scripts/setup_database.py)
  - `done`: executable bootstrap paths are migration-first only; remaining references to `setup_database.sql` are doc/test/shim only

- `[done] TD-02` ??????????? ??? deny??? ?????? ?? audit log
  - `done`: API ???? `log_permission_decision` ?? [core/audit.py](C:/Users/Dell/Documents/Ox-Loadout-main/core/audit.py)
  - `done`: helper??? audit deny ?? [handlers/admin/modules/base_handler.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/modules/base_handler.py)
  - `done`: deny audit ???? admin entry ?? [handlers/admin/admin_handlers_modular.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/admin_handlers_modular.py)
  - `done`: deny audit ???? channel management ?? [handlers/channel/channel_handlers.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/channel/channel_handlers.py) ? [handlers/channel/menu_handlers.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/channel/menu_handlers.py)
  - `done`: deny audit ???? data management ?? [handlers/admin/modules/system/data_management_handler.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/modules/system/data_management_handler.py)
  - `done`: deny audit ???? import/export ?? [handlers/admin/modules/system/import_export.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/modules/system/import_export.py)
  - `done`: deny audit ???? UA admin ?? [handlers/admin/user_attachments_admin/permissions.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/user_attachments_admin/permissions.py)
  - `done`: deny audit ???? notifications/tickets/faq/admin-management ?? [handlers/admin/modules/system/notification_handler.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/modules/system/notification_handler.py) ? [handlers/admin/modules/support/ticket_handler.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/modules/support/ticket_handler.py) ? [handlers/admin/modules/support/faq_handler.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/modules/support/faq_handler.py) ? [handlers/admin/modules/system/admin_management.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/modules/system/admin_management.py)
  - `next`: ???? deny audit ???? path??? ??????? content/user-management/direct-contact ? stats-backup

- `[done] TD-03` ???? edge-case??? ??? backup/restore/health
  - `done`: success / partial-success / get_file failure / download failure / subprocess failure
  - `done`: `ZIP -> pg_restore`
  - `done`: `SQLite restore success`
  - `done`: `archive without payload`
  - `done`: `archive with multiple payloads`
  - `done`: permission deny contract ???? health restore start ? data backup create
  - `done`: restore start/file state mismatch + missing message/document/file metadata + invalid ZIP archive hardening in [handlers/admin/modules/reports/data_health_report.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/modules/reports/data_health_report.py)

- `[done] TD-04` ???? AC-2 ?? ??? deterministic ???? `commit/rollback`
  - `done`: transaction boundary ???? ???? `delete_reported_attachment`
  - `done`: transaction boundary ???? ???? `warn_owner_about_report`
  - `done`: ??? commit/rollback ???? `dismiss/delete/warn` ?? [tests/test_smoke_admin_channel.py](C:/Users/Dell/Documents/Ox-Loadout-main/tests/test_smoke_admin_channel.py)
  - `done`: split-write ???? `approve_attachment` ??? ? stats update ??? ?? transaction داخلی repository ?? [handlers/admin/user_attachments_admin/review_handler.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/user_attachments_admin/review_handler.py)
  - `done`: ??? deterministic ??? repository path??? `approve/reject/delete/restore` ? handler path `edit weapon` ?? [tests/test_smoke_admin_channel.py](C:/Users/Dell/Documents/Ox-Loadout-main/tests/test_smoke_admin_channel.py)
  - `done`: repository-level deterministic coverage now includes approve/reject/delete/restore success+rollback paths in [tests/test_smoke_admin_channel.py](C:/Users/Dell/Documents/Ox-Loadout-main/tests/test_smoke_admin_channel.py)
  - `done`: handler-side side-effect failure paths for notification/cache are covered and no longer threaten write atomicity

- `[done] TD-05` ????? typed admin routing ? ??? `AdminHandlers.__getattr__`
  - `done`: contract ????? routing helper?? ?? [handlers/admin/admin_menu_routing.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/admin_menu_routing.py)
  - `done`: route-map??? explicit ?? [handlers/admin/admin_handlers_modular.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/admin_handlers_modular.py)
  - `done`: ??? `AdminHandlers.__getattr__` ? bind ???? method?? ????? registry
  - `done`: regression/test coverage ???? routing contract ?? [tests/test_admin_menu_routing.py](C:/Users/Dell/Documents/Ox-Loadout-main/tests/test_admin_menu_routing.py) ? [tests/test_regression_guards.py](C:/Users/Dell/Documents/Ox-Loadout-main/tests/test_regression_guards.py)
  - `done`: extraction ???? admin lifecycle ?? [handlers/admin/admin_entry_flow.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/admin_entry_flow.py)
  - `done`: extraction ???? initialization/setup ?? [handlers/admin/admin_handler_setup.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/admin_handler_setup.py)
  - `done`: ????? ?? [handlers/admin/admin_handlers_modular.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/admin_handlers_modular.py) ??? `165` ??? ?? `<500`
- [done] TD-06 ??? ???? legacy db.method() ? ??? DatabasePostgres.__getattr__
  - done: migration callsite??? legacy ?? access point??? ???? db.users/db.attachments/db.settings/db.analytics/db.cms/db.support
  - done: ??? fallback DatabasePostgres.__getattr__ ? ???? contract ??? repo access point??? canonical
  - done: ??? direct db.execute_query() ?? non-repository helper??? ? service??? ?? scope ??? wave
  - done: regression guard ??? zero legacy direct-call ?? [tests/test_regression_guards.py](C:/Users/Dell/Documents/Ox-Loadout-main/tests/test_regression_guards.py)
  - done: sync ??? smoke/flow test??? ?? repo-boundary ????
- [done] TD-07 freeze ? ??? ???? dead-code ????? ?? core/database/mixins
  - done: guard ??? ??? import ??? ?? core.database.mixins.* ?? [tests/test_regression_guards.py](C:/Users/Dell/Documents/Ox-Loadout-main/tests/test_regression_guards.py)
  - done: ??? file??? dead legacy ??? core/database/mixins/*.py ?? runtime path
  - done: ??? dependency/runtime import ???? ??? repo
- `[in_progress] TD-08` ????? error taxonomy ? ???? ????????? `except Exception`
  - `done`: typed restore error contract + UA admin/review cleanup + channel stats cleanup
  - `done`: FAQ schema-repair path in [core/database/repositories/support_repository.py](C:/Users/Dell/Documents/Ox-Loadout-main/core/database/repositories/support_repository.py) no longer uses bare `except:` and now raises typed `InfrastructureError`
  - `done`: UA admin handlers [banned_handler.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/user_attachments_admin/banned_handler.py), [settings_handler.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/user_attachments_admin/settings_handler.py), and [stats_handler.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/user_attachments_admin/stats_handler.py) now use boundary logging and no longer keep raw `except:` blocks in touched paths
  - `done`: user-facing browse flows in [browse_handler.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/user/user_attachments/browse_handler.py) and [my_attachments_handler.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/user/user_attachments/my_attachments_handler.py) now use explicit boundary logging instead of raw swallow/fallback paths
  - `next`: continue reducing boundary catch-all in remaining live repositories/handlers, especially `user_repository.py`, `analytics_repository.py`, `inline_handler.py`, and `contact_handlers.py`

- `[done] TD-09` ????? guard??? async/missing-await
  - `done`: guard??? regex ???? system/support modules ?? [tests/test_regression_guards.py](C:/Users/Dell/Documents/Ox-Loadout-main/tests/test_regression_guards.py)
  - `done`: ??? دوم AST-based ??? await ??? call??? permission/auth ?? system/support modules ?? [tests/test_regression_guards.py](C:/Users/Dell/Documents/Ox-Loadout-main/tests/test_regression_guards.py)
  - `done`: AST guard now covers permission/auth plus async repository/db calls across the targeted system/support modules

- `[done] TD-10` type-hardening ???????? ? ???? AC-6 ??? live scope
  - `done`: mypy live scope for 50 source files is now green locally
  - `done`: CI type gate updated from narrow subset to live scope
  - `done`: `warn_return_any = true` is now enabled in [pyproject.toml](C:/Users/Dell/Documents/Ox-Loadout-main/pyproject.toml) and the live-scope type gate stays green
  - `done`: targeted ruff cleanup completed for UA admin live-scope handlers [banned_handler.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/user_attachments_admin/banned_handler.py), [settings_handler.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/user_attachments_admin/settings_handler.py), and [stats_handler.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/user_attachments_admin/stats_handler.py)
  - `done`: `ruff check` now passes across the same live scope enforced by CI

- `[blocked] TD-11` ??? guard??? ???? compatibility ?? runtime ??? ?? verify ??? cutover
  - `done`: `--require-migration` ?? [scripts/verify_canonical_bootstrap.py](C:/Users/Dell/Documents/Ox-Loadout-main/scripts/verify_canonical_bootstrap.py)
  - `done`: enforce ??? ?? ?? [.github/workflows/ci.yml](C:/Users/Dell/Documents/Ox-Loadout-main/.github/workflows/ci.yml)
  - `blocked`: ??? runtime compatibility guard?? ??????? evidence ????? rollout ???

## ??? ???? ????

1. ????? `TD-04` ??? `review_handler` ? ???? transaction determinism ???? review path.
2. ??????? extraction ???? ???? ??? [handlers/admin/admin_handlers_modular.py](C:/Users/Dell/Documents/Ox-Loadout-main/handlers/admin/admin_handlers_modular.py) ?? ????? criterion `TD-05`.
3. ??? ?? ?? ???? ?? `TD-06` ???? ??? `db.method()` ? `DatabasePostgres.__getattr__`.





