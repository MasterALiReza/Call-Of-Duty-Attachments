# 👥 User Management Module

## Overview

The User Management module provides administrators with comprehensive tools to track, view, search, and manage bot users directly from the Telegram admin panel.

## Features

| Feature | Description |
|---------|-------------|
| **User Stats Dashboard** | Total users, new today, active today/week, banned count |
| **Paginated User List** | Browse all users with 10 per page pagination |
| **User Search** | Search by username, numeric ID, or name |
| **User Details** | Full profile: ID, name, language, join date, last seen, submissions stats |
| **Ban/Unban** | Ban users with reason, unban with one click |
| **Banned Filter** | View only banned users |
| **New User Notifications** | Auto-notify admins when new users start the bot, with inline detail button |

## Architecture

```
handlers/admin/modules/system/user_management.py  ← Handler (10 methods)
core/database/repositories/user_repository.py      ← 6 new DB methods
handlers/admin/admin_states.py                     ← 5 new states
handlers/admin/admin_handlers_modular.py           ← Routing & wiring
app/registry/admin_registry_states.py              ← ConversationHandler states
handlers/admin/modules/base_handler.py             ← Keyboard button
managers/admin_notifier.py                         ← New user notification + inline button
locales/fa.json, en.json                           ← 40+ translation keys
```

## Permissions

- **`MANAGE_USERS`** permission required (already assigned to `super_admin` and `support_admin` roles)
- Super admins always have access

## Admin States

| State | Description |
|-------|-------------|
| `USER_MGMT_MENU` | Main menu with stats and action buttons |
| `USER_MGMT_LIST` | Paginated user list with clickable items |
| `USER_MGMT_SEARCH` | Awaiting text input for search query |
| `USER_MGMT_DETAIL` | Showing full user details with ban/unban |
| `USER_MGMT_BAN` | Awaiting ban reason text input |

## Database Methods

| Method | Description |
|--------|-------------|
| `get_users_paginated(page, limit, search, is_banned, sort_by)` | Paginated user list with search/filter |
| `get_users_count(search, is_banned)` | Total count for pagination |
| `get_user_detailed(user_id)` | Full profile + submission stats |
| `ban_user(user_id, reason)` | Ban user with reason |
| `unban_user(user_id)` | Remove ban |
| `get_users_stats()` | Aggregate stats (total, new, active, banned) |

## Callback Data Patterns

| Pattern | Handler |
|---------|---------|
| `admin_users` | Opens user management menu |
| `um_list` | Show user list |
| `um_page_{n}` | Pagination |
| `um_search` | Start search flow |
| `um_filter_banned` | Filter banned only |
| `um_detail_{id}` | User details |
| `um_ban_{id}` | Start ban flow |
| `um_unban_{id}` | Unban user |
| `um_noop` | No-op (page indicator) |

## New User Notification

When a new user starts the bot, all admins receive a notification with:
- User name, username, and ID
- Total users count and new users today
- **Inline "👤 مشاهده جزئیات" button** linking directly to user details in the management panel

## Translation Keys

All UI strings use the `admin.user_mgmt.*` namespace with full FA/EN support (40+ keys).
