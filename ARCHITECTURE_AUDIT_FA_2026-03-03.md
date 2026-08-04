# ممیزی ساختاری/معماری Ox-Loadout (ریسک‌محور)
تاریخ ممیزی: 2026-03-03  
دامنه: کد + دیتابیس + DevOps  
معیار اولویت: Production Risk

## 1) Executive Summary
این پروژه از نظر وسعت، بزرگ و عملیاتی است (حدود `166` فایل پایتون و `48043` خط کد)، اما در وضعیت فعلی چند ریسک سطح تولید دارد که قبل از هر توسعه جدید باید کنترل شوند.

خلاصه وضعیت ریسک:
- `P0 بحرانی`: 3 مورد
- `P1 بالا`: 7 مورد
- `P2 متوسط`: 6 مورد
- `P3 پایین`: 2 مورد

مهم‌ترین جمع‌بندی:
- مسیرهای حساس ادمین/کانال دارای خطاهای جدی `async/await` هستند که هم می‌توانند کنترل دسترسی را دور بزنند و هم باعث شکست runtime شوند.
- ساختار لایه داده چندمنبعی است (Runtime DDL + دو SQL script) و drift اسکیما ایجاد شده/خواهد شد.
- کیفیت‌گیت فعلی مانع ورود رگرسیون نیست: تست واقعی وجود ندارد، CI موجود نیست، و تایپ‌چک خطاهای بسیار زیادی دارد.

اعداد کلیدی:
- `python -m compileall -q app core handlers main.py`: موفق (`COMPILE_OK`)
- `pytest -q`: اجرا شد اما تست مؤثر ندارد (`NO_TESTS_DIR`) و warning تنظیمات دارد
- `mypy`: `3354` خطا در `96` فایل
- الگوهای شکننده:
  - `except Exception`: `1013` مورد
  - خطوط `pass`: `138` مورد

---

## 2) Scope & Method
روش ممیزی:
1. تحلیل استاتیک کد و ساختار ماژول‌ها
2. صحت‌سنجی ارجاعات بحرانی با `file:line`
3. بررسی هم‌خوانی لایه دیتابیس و اسکریپت‌های استقرار
4. بررسی quality gates (compile/test/type/CI)

مدل شدت:
- `P0`: احتمال اختلال مستقیم در امنیت/دسترسی/پایداری production
- `P1`: ریسک بالا با اثر عملیاتی/توسعه‌ای قابل‌توجه
- `P2`: بدهی فنی مؤثر بر نگهداشت/سرعت توسعه
- `P3`: بهبودهای کم‌ریسک یا hygiene

فرمت هر یافته:
- `ID`, `Severity`, `Impact`, `Evidence(file:line)`, `Root Cause`, `Blast Radius`, `Fix Direction`, `Effort`, `Owner Suggestion`

---

## 3) Critical Findings (P0/P1)

### F-001
- `ID`: F-001
- `Severity`: P0
- `Impact`: احتمال bypass مجوز در مدیریت کانال (coroutine truthy) + رفتار غیرقابل پیش‌بینی در چک دسترسی
- `Evidence(file:line)`:
  - `handlers/channel/channel_handlers.py:32`
  - `handlers/channel/channel_handlers.py:42`
  - `handlers/channel/channel_handlers.py:49`
  - `handlers/channel/channel_handlers.py:52`
  - `handlers/channel/channel_handlers.py:123`
  - `core/security/role_manager.py:292`
  - `core/security/role_manager.py:341`
  - `core/database/database_pg.py:425`
- `Root Cause`: مهاجرت ناقص از APIهای sync به async در لایه permission/DB
- `Blast Radius`: تمام مسیرهای مدیریت کانال (`admin` و `channel management`)
- `Fix Direction`: تبدیل `check_channel_management_permission` به async و افزودن `await` در همه call-siteها + تست اجباری مسیر permission
- `Effort(S/M/L)`: M
- `Owner Suggestion`: تیم Backend/Handlers

### F-002
- `ID`: F-002
- `Severity`: P0
- `Impact`: فراخوانی DB بدون `await` در handler کانال باعث crash، خطای منطقی، و احتمال تغییر ناقص داده می‌شود
- `Evidence(file:line)`:
  - `handlers/channel/channel_handlers.py:145`
  - `handlers/channel/channel_handlers.py:269`
  - `handlers/channel/channel_handlers.py:273`
  - `handlers/channel/channel_handlers.py:627`
  - `handlers/channel/channel_handlers.py:680`
  - `handlers/channel/channel_handlers.py:929`
  - `handlers/channel/channel_handlers.py:1377`
  - `handlers/channel/channel_handlers.py:1444`
  - `handlers/channel/channel_handlers.py:1451`
  - `core/database/repositories/cms_repository.py:16`
  - `core/database/repositories/cms_repository.py:26`
  - `core/database/repositories/cms_repository.py:37`
  - `core/database/repositories/cms_repository.py:112`
  - `core/database/repositories/cms_repository.py:148`
- `Root Cause`: باقی‌ماندن الگوی قدیمی sync روی API جدید async
- `Blast Radius`: عملیات add/remove/reorder/list کانال
- `Fix Direction`: بازنویسی کامل channel handler با قرارداد async-safe + افزودن تست async integration برای مسیرهای CRUD کانال
- `Effort(S/M/L)`: M
- `Owner Suggestion`: تیم Backend + QA

### F-003
- `ID`: F-003
- `Severity`: P0
- `Impact`: استفاده اشتباه از context manager تراکنش (`async with await ...` و `with db.transaction()`) می‌تواند commit/rollback را خراب کند
- `Evidence(file:line)`:
  - `handlers/admin/user_attachments_admin/reports_handler.py:56`
  - `handlers/admin/user_attachments_admin/reports_handler.py:213`
  - `handlers/admin/user_attachments_admin/reports_handler.py:395`
  - `handlers/admin/user_attachments_admin/reports_handler.py:499`
  - `handlers/admin/user_attachments_admin/reports_handler.py:587`
  - `handlers/admin/user_attachments_admin/review_handler.py:841`
  - `handlers/admin/user_attachments_admin/review_handler.py:906`
  - `handlers/admin/user_attachments_admin/settings_handler.py:807`
  - `core/database/database_pg.py:115`
  - `core/database/database_pg.py:130`
- `Root Cause`: عدم یکسان‌سازی الگوی transaction در زمان refactor
- `Blast Radius`: فرآیند review/report/blacklist در پنل ادمین
- `Fix Direction`: تعریف و اعمال یک الگوی واحد transaction (`async with db.transaction() as conn`) + lint rule برای منع الگوهای غلط
- `Effort(S/M/L)`: M
- `Owner Suggestion`: تیم Backend

### F-004
- `ID`: F-004
- `Severity`: P1
- `Impact`: کلیدهای تکراری در map وضعیت conversation باعث overwrite خاموش و رفتار routing ناپایدار می‌شود
- `Evidence(file:line)`:
  - `app/registry/admin_registry_states.py:347`
  - `app/registry/admin_registry_states.py:353`
  - `app/registry/admin_registry_states.py:358`
  - `app/registry/admin_registry_states.py:622`
  - `app/registry/admin_registry_states.py:628`
  - `app/registry/admin_registry_states.py:633`
- `Root Cause`: تعریف state map بسیار بزرگ بدون guard برای uniqueness
- `Blast Radius`: جریان‌های Import/Export پنل ادمین
- `Fix Direction`: استخراج state registry به ساختار typed + validation تستی برای duplicate key
- `Effort(S/M/L)`: S
- `Owner Suggestion`: تیم Bot Flow

### F-005
- `ID`: F-005
- `Severity`: P1
- `Impact`: وجود dead code و refactor نیمه‌کاره خطر رگرسیون callbackها را بالا برده است
- `Evidence(file:line)`:
  - `handlers/user/modules/search/search_handler.py:283`
  - `handlers/user/modules/search/search_handler.py:288`
  - `handlers/user/modules/search/search_handler.py:289`
  - `handlers/user/modules/search/search_handler.py:301`
  - `app/registry/user_registry.py:264`
  - `app/registry/user_registry.py:271`
  - `app/registry/user_registry.py:273`
- `Root Cause`: ادغام ناتمام handlerهای قدیمی/جدید
- `Blast Radius`: مسیر callbackهای `attm_` و `qatt_` و نگهداشت ماژول جستجو
- `Fix Direction`: حذف شاخه‌های unreachable، تکمیل refactor مسیر callback، افزودن تست regression callback data
- `Effort(S/M/L)`: S
- `Owner Suggestion`: تیم User Handlers

### F-006
- `ID`: F-006
- `Severity`: P1
- `Impact`: چندمنبعی بودن تعریف schema احتمال اختلاف محیط‌ها و خطاهای deploy را بالا می‌برد
- `Evidence(file:line)`:
  - `core/database/database_pg.py:192`
  - `scripts/init_postgres.sql:9`
  - `scripts/setup_database.sql:26`
  - شمارش تقریبی جداول: `runtime_tables=41`, `init_tables=31`, `setup_tables=32`
- `Root Cause`: نبود single source of truth برای migration/schema
- `Blast Radius`: راه‌اندازی محیط جدید، بازیابی، و ارتقای نسخه
- `Fix Direction`: مهاجرت کامل به migration framework (Alembic یا معادل) و توقف runtime DDL به‌عنوان منبع اصلی
- `Effort(S/M/L)`: L
- `Owner Suggestion`: تیم Backend + DevOps

### F-007
- `ID`: F-007
- `Severity`: P1
- `Impact`: hardcoded credential و چاپ مستقیم پسورد در script ریسک امنیتی جدی دارد
- `Evidence(file:line)`:
  - `scripts/setup_database.py:25`
  - `scripts/setup_database.py:26`
  - `scripts/setup_database.py:27`
  - `scripts/setup_database.py:297`
- `Root Cause`: اسکریپت setup با مفروضات local توسعه‌ای در مسیر production
- `Blast Radius`: نشت credential در لاگ/ترمینال/اسکرین‌شات
- `Fix Direction`: حذف hardcoded secret، اجبار env var، ماسک‌کردن خروجی حساس
- `Effort(S/M/L)`: S
- `Owner Suggestion`: تیم DevOps/SRE

### F-008
- `ID`: F-008
- `Severity`: P1
- `Impact`: quality gate فعلی نمی‌تواند رگرسیون حیاتی را قبل از merge متوقف کند
- `Evidence(file:line)`:
  - `pyproject.toml:17`
  - `pyproject.toml:18`
  - `pyproject.toml:19`
  - `NO_TESTS_DIR` (عدم وجود مسیر tests)
  - `NO_WORKFLOWS_DIR` (عدم وجود CI workflow)
  - خروجی mypy: `Found 3354 errors in 96 files`
- `Root Cause`: نبود pipeline اجباری تست/تایپ/لینت
- `Blast Radius`: کل چرخه توسعه و انتشار
- `Fix Direction`: CI حداقلی اجباری: smoke tests + mypy incremental + lint
- `Effort(S/M/L)`: M
- `Owner Suggestion`: تیم Platform/DevEx

---

## 4) Major Structural/Architectural Findings (P1/P2)

### F-009
- `ID`: F-009
- `Severity`: P1
- `Impact`: فایل‌های بسیار بزرگ با چند مسئولیت، هزینه تغییر و ریسک خطا را بالا می‌برد
- `Evidence(file:line)`:
  - `handlers/channel/channel_handlers.py` (1555 خط)
  - `handlers/admin/admin_handlers_modular.py` (834 خط)
  - `handlers/admin/user_attachments_admin/review_handler.py` (958 خط)
  - `main.py` (502 خط)
- `Root Cause`: رشد ویژگی‌ها بدون modular decomposition مرحله‌ای
- `Blast Radius`: توسعه فیچر جدید، دیباگ، onboarding
- `Fix Direction`: شکستن بر اساس bounded context و تعریف interface ماژولی
- `Effort(S/M/L)`: L
- `Owner Suggestion`: Tech Lead + تیم Backend

### F-010
- `ID`: F-010
- `Severity`: P2
- `Impact`: هم‌زمانی الگوی container + bot_data + dynamic fallback خوانایی وابستگی‌ها را کم کرده است
- `Evidence(file:line)`:
  - `core/container.py:17`
  - `main.py:397`
  - `main.py:398`
  - `main.py:399`
  - `main.py:400`
  - `main.py:402`
  - `core/database/database_pg.py:510`
  - `core/database/database_pg.py:515`
- `Root Cause`: ترکیب Service Locator با DI ناقص و backward compatibility طولانی
- `Blast Radius`: تمام handlerهایی که db/service مصرف می‌کنند
- `Fix Direction`: contract-based DI، حذف تدریجی `db.__getattr__` fallback، تزریق صریح dependency
- `Effort(S/M/L)`: L
- `Owner Suggestion`: تیم Architecture

### F-011
- `ID`: F-011
- `Severity`: P2
- `Impact`: routing مبتنی بر regex بزرگ، traceability جریان ادمین را دشوار کرده است
- `Evidence(file:line)`:
  - `app/registry/admin_registry.py:96`
  - `app/registry/admin_registry.py:104`
  - `app/registry/admin_registry.py:106`
- `Root Cause`: تمرکز بیش از حد callback routing در یک نقطه
- `Blast Radius`: پنل ادمین و state transitions
- `Fix Direction`: router decomposition بر اساس domain module + تست routing map
- `Effort(S/M/L)`: M
- `Owner Suggestion`: تیم Bot Flow

### F-012
- `ID`: F-012
- `Severity`: P2
- `Impact`: exception swallowing زیاد، تشخیص علت ریشه‌ای خطا را کند می‌کند
- `Evidence(file:line)`:
  - شمارش کلی `except Exception`: 1013
  - شمارش کلی `pass`: 138
  - نمونه: `handlers/channel/channel_handlers.py:143`
  - نمونه: `handlers/channel/channel_handlers.py:144`
- `Root Cause`: الگوی defensive بیش‌ازحد بدون taxonomy خطا
- `Blast Radius`: قابلیت مشاهده خطاها و MTTR
- `Fix Direction`: تعریف خطاهای دامنه‌ای + حذف `except Exception` عمومی در مسیرهای حساس
- `Effort(S/M/L)`: M
- `Owner Suggestion`: تیم Backend + Observability

### F-013
- `ID`: F-013
- `Severity`: P2
- `Impact`: ناسازگاری کلید محیط (`ENV` در کد، `ENVIRONMENT` در env template) باعث رفتار غیرمنتظره توسعه می‌شود
- `Evidence(file:line)`:
  - `core/database/database_pg.py:530`
  - `.env.example:64`
- `Root Cause`: قرارداد env غیرمتمرکز
- `Blast Radius`: رفتار warning/deprecation در توسعه و پیکربندی محیط
- `Fix Direction`: یکپارچه‌سازی کلیدهای env در `config` و حذف کلیدهای موازی
- `Effort(S/M/L)`: S
- `Owner Suggestion`: تیم Platform

---

## 5) Data Layer & Schema Consistency Findings

### F-014
- `ID`: F-014
- `Severity`: P1
- `Impact`: coexistence لایه sync (mixins) و async (repositories) عامل مستقیم خطاهای `await` در handlerها شده است
- `Evidence(file:line)`:
  - `core/database/mixins/cms_mixin.py:22` (sync)
  - `core/database/mixins/cms_mixin.py:37` (sync)
  - `core/database/repositories/cms_repository.py:16` (async)
  - `core/database/repositories/cms_repository.py:26` (async)
  - `core/database/database_pg.py:510` (dynamic fallback)
- `Root Cause`: refactor نیمه‌تمام معماری دیتابیس
- `Blast Radius`: تمام call-siteهایی که `db.method()` مستقیم صدا می‌زنند
- `Fix Direction`: deprecate واقعی mixin API قدیمی + codemod call-siteها به repo API صریح
- `Effort(S/M/L)`: L
- `Owner Suggestion`: تیم Data/Backend

### F-015
- `ID`: F-015
- `Severity`: P1
- `Impact`: اختلاف مدل جداول guide بین منابع schema می‌تواند query/runtime mismatch ایجاد کند
- `Evidence(file:line)`:
  - `scripts/init_postgres.sql:172` (`guide_photos`)
  - `scripts/init_postgres.sql:178` (`guide_videos`)
  - `scripts/setup_database.sql:390` (`guide_media`)
  - `core/database/database_pg.py:243` (`guide_photos`)
  - `core/database/database_pg.py:244` (`guide_videos`)
- `Root Cause`: تغییر مدل داده بدون governance migration
- `Blast Radius`: فیچر راهنماها (Guides)
- `Fix Direction`: انتخاب مدل canonical + migration رسمی و حذف مدل جایگزین
- `Effort(S/M/L)`: M
- `Owner Suggestion`: تیم Data

### F-016
- `ID`: F-016
- `Severity`: P2
- `Impact`: مکانیزم migration رسمی موجود نیست (`migrations/` وجود ندارد)؛ rollback/upgrade پیش‌بینی‌پذیر نیست
- `Evidence(file:line)`:
  - `NO_MIGRATIONS_DIR`
  - `scripts/setup_database.sql:26` (`_migrations` table تعریف شده اما pipeline migration رسمی دیده نشد)
  - `core/database/database_pg.py:192` (`_ensure_schema` runtime DDL)
- `Root Cause`: reliance روی bootstrap script/runtime schema creation
- `Blast Radius`: release management و disaster recovery
- `Fix Direction`: migration pipeline versioned + checksum + rollback strategy
- `Effort(S/M/L)`: L
- `Owner Suggestion`: تیم DevOps + Data

### F-017
- `ID`: F-017
- `Severity`: P2
- `Impact`: کیفیت تایپ در لایه داده پایین است و خطاهای contract زودتر کشف نمی‌شوند
- `Evidence(file:line)`:
  - mypy گزارش گسترده روی mixins/repositories
  - نمونه: `utils/analytics_db_helper.py:25`
  - نمونه: `core/database/mixins/user_mixin.py:29`
  - نمونه: `core/database/mixins/settings_mixin.py:26`
- `Root Cause`: type contract شفاف بین BaseRepository/mixins/repositories تعریف نشده
- `Blast Radius`: reliability کد دیتابیس
- `Fix Direction`: تعریف Protocol/ABC برای عملیات پایه (`execute_query`, `transaction`, `get_connection`) + mypy strict-by-module
- `Effort(S/M/L)`: M
- `Owner Suggestion`: تیم Data Platform

---

## 6) DevOps/Runtime/Deploy Findings

### F-018
- `ID`: F-018
- `Severity`: P1
- `Impact`: نام دیتابیس/کاربر بین setup/deploy/compose ناهمخوان است و خطای عملیاتی ایجاد می‌کند
- `Evidence(file:line)`:
  - `scripts/setup_database.py:25` (`ox_loadout_attachments_db`)
  - `scripts/setup_database.py:26` (`ox_loadout_bot_user`)
  - `docker-compose.yml:18` (`ox_loadout_bot`, `ox_loadout_admin`)
  - `docker-compose.yml:79` (`POSTGRES_DB=ox_loadout_bot`)
  - `deploy.sh:49` (`DEFAULT_DB_NAME="ox_loadout_bot_db"`)
  - `deploy.sh:50` (`DEFAULT_DB_USER="ox_loadout_bot_user"`)
- `Root Cause`: قرارداد deployment/environment یکپارچه نشده
- `Blast Radius`: provisioning و troubleshooting محیط‌ها
- `Fix Direction`: تعریف canonical env contract و تولید همه scriptها از یک source
- `Effort(S/M/L)`: M
- `Owner Suggestion`: DevOps

### F-019
- `ID`: F-019
- `Severity`: P2
- `Impact`: کانتینر اصلی با کاربر root اجرا می‌شود
- `Evidence(file:line)`:
  - `Dockerfile:15`
  - `Dockerfile:39`
  - (عدم وجود دستور `USER`)
- `Root Cause`: hardening ناقص image
- `Blast Radius`: سطح حمله runtime
- `Fix Direction`: ساخت non-root user و کاهش capabilityها
- `Effort(S/M/L)`: S
- `Owner Suggestion`: DevOps/Security

### F-020
- `ID`: F-020
- `Severity`: P3
- `Impact`: پوشه‌های مستندسازی در `.gitignore` هستند و ممکن است گزارش‌های مهم versioned نشوند
- `Evidence(file:line)`:
  - `.gitignore:64` (`docs/`)
  - `.gitignore:77` (`/reports/`)
- `Root Cause`: سیاست ignore بیش‌ازحد
- `Blast Radius`: knowledge management
- `Fix Direction`: بازتعریف ignore با مسیرهای generated واقعی
- `Effort(S/M/L)`: S
- `Owner Suggestion`: Tech Lead

### F-021
- `ID`: F-021
- `Severity`: P3
- `Impact`: healthcheck bot صرفا DB connectivity را می‌سنجد و readiness واقعی اپ را پوشش نمی‌دهد
- `Evidence(file:line)`:
  - `docker-compose.yml:55`
- `Root Cause`: نبود readiness contract سطح اپلیکیشن
- `Blast Radius`: تشخیص کاذب سالم بودن سرویس
- `Fix Direction`: health endpoint با dependency checks و graceful degradation
- `Effort(S/M/L)`: S
- `Owner Suggestion`: DevOps + Backend

---

## 7) Improvement Roadmap (0-2w / 1-2m / 3-6m)

### 7.1 Top 10 اصلاح فوری (0-2 هفته)

| # | اقدام | Value | Complexity | Dependencies | Risk | Measurable Outcome |
|---|---|---|---|---|---|---|
| 1 | async کردن `check_channel_management_permission` و await همه call-siteها | حذف ریسک bypass مجوز | M | RoleManager + channel handlers | متوسط | عبور تست مجوز: 0 مورد bypass |
| 2 | اصلاح همه DB callهای بدون await در channel handlers | رفع crash/logic bug | M | CMSRepository API | متوسط | 0 خطای `unused-coroutine` در فایل |
| 3 | استانداردسازی transaction pattern در reports/review/settings | حفظ atomicity | M | DatabasePostgres transaction | متوسط | تست commit/rollback پایدار در 3 سناریو |
| 4 | اصلاح `self.is_admin(...)` بدون await در admin modules | رفع خطای منطقی دسترسی | S | Base handler | پایین | تایید mypy در call-siteهای اصلاح‌شده |
| 5 | حذف duplicate state key و افزودن تست uniqueness | ثبات state machine | S | admin registry states | پایین | تست uniqueness با خروجی pass |
| 6 | حذف hardcoded credential و عدم چاپ پسورد | کاهش ریسک امنیتی | S | setup scripts | پایین | 0 secret در stdout/setup log |
| 7 | یکپارچه‌سازی قرارداد env DB name/user/password | حذف خطای provisioning | M | compose + deploy + setup | متوسط | یک env matrix واحد و سازگار |
| 8 | افزودن smoke testهای حیاتی ادمین/کانال | جلوگیری از رگرسیون سریع | M | pytest setup | متوسط | حداقل 6 تست smoke قابل‌اجرا |
| 9 | راه‌اندازی CI حداقلی (pytest + mypy subset + lint) | quality gate واقعی | M | GitHub workflow | متوسط | pipeline سبز/قرمز enforce شده |
| 10 | تعریف baseline migration و freeze schema canonical | کنترل drift | M | DB schema owners | بالا | migration version `v1` و reproducible bootstrap |

### 7.2 Backlog میان‌مدت (1-2 ماه)

| اقدام | Value | Complexity | Dependencies | Risk | Measurable Outcome |
|---|---|---|---|---|---|
| شکستن `channel_handlers.py` به submoduleهای permission/crud/reorder/export | افزایش maintainability | L | Routing refactor | متوسط | کاهش سایز فایل به < 500 خط |
| بازطراحی admin routing با router map تایپ‌شده | traceability بالاتر | M | admin registry | متوسط | کاهش regex mega-pattern و پوشش تست route |
| حذف تدریجی `db.__getattr__` و migration به repo API صریح | قرارداد واضح dependency | L | همه handlers | بالا | 90% حذف direct `db.method()` legacy |
| تعریف error taxonomy (domain/infrastructure/user) | کاهش `except Exception` عمومی | M | logging policy | متوسط | 50% کاهش catch-all در مسیرهای حساس |
| برنامه type-hardening ماژول‌به‌ماژول | کشف زودهنگام bug | L | mypy config | متوسط | کاهش خطای mypy از 3354 به < 1200 |

### 7.3 مسیر بلندمدت (3-6 ماه)

| اقدام | Value | Complexity | Dependencies | Risk | Measurable Outcome |
|---|---|---|---|---|---|
| migration کامل به معماری domain-driven (Admin/User/Support/Analytics) | سرعت توسعه فیچر | L | ماژولار‌سازی | بالا | lead time تغییرات 30% کمتر |
| observability stack (structured logs + metrics + traces) | کاهش MTTR | M | infra monitoring | متوسط | MTTR خطاهای P1 کمتر از 30 دقیقه |
| reliability hardening (idempotency, retries policy, circuit guards) | پایداری runtime | M | infrastructure contracts | متوسط | کاهش خطاهای transient > 40% |
| release governance (migration gates + backward compatibility checks) | کاهش ریسک deploy | M | CI/CD | متوسط | 0 incident ناشی از drift schema |

### 7.4 تغییرات مهم API/Interface/Type (برای فاز اجرا)
1. تعریف `PermissionService` async با قرارداد صریح:
   - `async is_admin(user_id: int) -> bool`
   - `async has_permission(user_id: int, perm: Permission) -> bool`
2. تعریف `DBTransaction` استاندارد:
   - `async with db.transaction() as conn`
3. تعریف `StateRegistryContract` با validation uniqueness برای state key
4. تعریف `SchemaSourceOfTruth`:
   - migration versioned تنها مرجع ایجاد/تغییر schema
   - runtime `_ensure_schema` فقط برای check سبک، نه creation اصلی

---

## 8) Feature Roadmap (Top 8 کاربردی با KPI)

### Feature-01: Permission Audit Trail + Policy Simulator
- `Problem`: تصمیم‌های دسترسی امروز قابل پیگیری عمیق نیست
- `User Value`: ادمین می‌فهمد چرا دسترسی reject/allow شده
- `Architecture Impact`: افزودن audit event در RoleManager و admin UI
- `MVP Slice`: ثبت هر check با `user_id`, `permission`, `result`, `reason`
- `Success KPI`: کاهش 50% تیکت‌های «چرا دسترسی ندارم»

### Feature-02: Migration Dashboard
- `Problem`: وضعیت schema و migration شفاف نیست
- `User Value`: تیم deploy با اطمینان rollback/upgrade انجام می‌دهد
- `Architecture Impact`: metadata migration + admin diagnostics
- `MVP Slice`: نمایش current version، pending migration، checksum status
- `Success KPI`: 0 deploy failure ناشی از migration mismatch

### Feature-03: Bulk Admin Actions with Dry-Run
- `Problem`: عملیات گروهی ادمین بدون پیش‌نمایش ریسک‌دار است
- `User Value`: قبل از اعمال، اثر تغییر دیده می‌شود
- `Architecture Impact`: service layer برای preview + confirm
- `MVP Slice`: dry-run برای پاکسازی کانال/گزارش/blacklist
- `Success KPI`: کاهش 70% خطاهای اپراتوری برگشت‌پذیر

### Feature-04: Attachment Moderation Queue with SLA
- `Problem`: رسیدگی گزارش‌ها و بازبینی‌ها SLA ندارد
- `User Value`: پاسخ سریع‌تر و کیفیت مدیریت محتوا بالاتر
- `Architecture Impact`: queue state + escalation rules
- `MVP Slice`: اولویت‌بندی گزارش‌ها بر اساس severity + age
- `Success KPI`: median زمان رسیدگی < 6 ساعت

### Feature-05: Admin Observability Panel
- `Problem`: دید بلادرنگ نسبت به خطا و سلامت جریان‌ها محدود است
- `User Value`: تشخیص سریع خرابی و اقدام فوری
- `Architecture Impact`: metrics aggregation + lightweight dashboard
- `MVP Slice`: خطاهای 24h، latency handlerها، failed transactions
- `Success KPI`: کاهش MTTR حداقل 40%

### Feature-06: User Attachment Quality Score
- `Problem`: کیفیت اتچمنت‌های کاربرمحور یکنواخت نیست
- `User Value`: محتوای بهتر در نتایج و رضایت بیشتر کاربران
- `Architecture Impact`: scoring pipeline در analytics/user_attachments
- `MVP Slice`: score اولیه بر اساس report rate + engagement
- `Success KPI`: افزایش 20% نرخ تعامل روی اتچمنت‌های تاییدشده

### Feature-07: Smart Recommendation per Mode/Weapon
- `Problem`: پیشنهادات فعلی context-aware کامل نیست
- `User Value`: کاربر سریع‌تر به loadout مناسب می‌رسد
- `Architecture Impact`: سرویس پیشنهاد بر پایه رفتار/محبوبیت
- `MVP Slice`: توصیه top-3 برای `(mode, weapon)` با fallback ثابت
- `Success KPI`: کاهش 25% زمان تا انتخاب اتچمنت

### Feature-08: Backup Restore Verification Workflow
- `Problem`: موفقیت restore فقط در سطح اجرای دستور سنجیده می‌شود
- `User Value`: اطمینان واقعی از قابلیت بازیابی
- `Architecture Impact`: post-restore checks + report artifact
- `MVP Slice`: runbook خودکار با health checks پس از restore
- `Success KPI`: 100% موفقیت DR drill ماهانه

---

## 9) Acceptance Criteria & Validation Plan

### AC-1: Permission Correctness
- سناریو: کاربر غیرادمین به مسیر `channel_management` دسترسی نگیرد
- معیار پذیرش: deny قطعی و قابل‌ردگیری در audit log

### AC-2: Transaction Determinism
- سناریو: خطا وسط عملیات report/review
- معیار پذیرش: rollback کامل و بدون partial write

### AC-3: State Machine Integrity
- سناریو: build state registry
- معیار پذیرش: هیچ کلید تکراری و overwrite خاموش وجود نداشته باشد

### AC-4: Schema Consistency
- سناریو: bootstrap محیط جدید
- معیار پذیرش: schema حاصل از migration با runtime contract یکسان باشد

### AC-5: Deploy Sanity
- سناریو: اجرای setup/deploy/compose
- معیار پذیرش: نام DB/user/password در تمام مسیرها هم‌راستا باشد

### AC-6: Quality Gate Enforcement
- سناریو: اجرای CI روی PR
- معیار پذیرش:
  - smoke tests الزامی
  - mypy subset الزامی
  - lint baseline الزامی

### AC-7: Regression Guard for Async
- سناریو: اجرای static checks روی handlerهای async
- معیار پذیرش: صفر مورد missing-await در مسیرهای حیاتی

### AC-8: Secret Hygiene
- سناریو: اجرای setup scripts
- معیار پذیرش: هیچ secret در log/stdout چاپ نشود

---

## 10) Appendix

### A) ماتریس ریسک
| Severity | تعداد | توضیح |
|---|---:|---|
| P0 | 3 | ریسک مستقیم روی مجوز/تراکنش/پایداری |
| P1 | 7 | ریسک عملیاتی و معماری با اثر بالا |
| P2 | 6 | بدهی فنی اثرگذار بر سرعت/کیفیت |
| P3 | 2 | بهبودهای hygiene و فرآیندی |

### B) واژه‌نامه
- `Blast Radius`: وسعت اثر یک مشکل در سیستم
- `Schema Drift`: اختلاف ساختار دیتابیس بین محیط‌ها/منابع
- `Quality Gate`: شروط اجباری قبل از merge/deploy
- `MTTR`: میانگین زمان بازیابی از خطا

### C) فهرست شواهد کلیدی (نمونه)
- `handlers/channel/channel_handlers.py:32,42,49,52,123,145,269,627,929`
- `handlers/admin/user_attachments_admin/reports_handler.py:56,213,395,499,587`
- `handlers/admin/user_attachments_admin/review_handler.py:841,906`
- `handlers/admin/user_attachments_admin/settings_handler.py:807`
- `app/registry/admin_registry_states.py:347,353,358,622,628,633`
- `core/database/database_pg.py:115,130,192,425,510,530`
- `scripts/init_postgres.sql:172,178`
- `scripts/setup_database.sql:26,390`
- `scripts/setup_database.py:25,26,27,297`
- `docker-compose.yml:18,55,79`
- `Dockerfile:15,39`
- `pyproject.toml:17,18,19`
- `.gitignore:64,77`

### D) وضعیت فعلی ابزارهای کیفی
- `compileall`: موفق
- `pytest`: warning درباره `testpaths` و `asyncio_default_fixture_loop_scope`
- `mypy`: 3354 خطا در 96 فایل

---

## نتیجه نهایی
پروژه برای ادامه توسعه فیچرهای جدید، ابتدا به یک «فاز تثبیت» نیاز دارد. اولویت قطعی با رفع خطاهای `async/await`، یکپارچه‌سازی schema/migration، و برقرار کردن quality gate اجباری است. پس از آن، مسیر ارتقا و فیوچرها می‌تواند با ریسک کنترل‌شده اجرا شود.
