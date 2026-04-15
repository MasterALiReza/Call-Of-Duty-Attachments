-- Bring migration source in parity with runtime-only tables used by services.

CREATE TABLE IF NOT EXISTS analytics_events (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    event_type TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_notification_preferences (
    user_id BIGINT PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    modes JSONB NOT NULL DEFAULT '["br","mp"]'::jsonb,
    events JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scheduled_notifications (
    id SERIAL PRIMARY KEY,
    message_type TEXT NOT NULL CHECK (message_type IN ('text', 'photo')),
    message_text TEXT,
    photo_file_id TEXT,
    parse_mode TEXT DEFAULT 'Markdown',
    interval_hours INTEGER NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_sent_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ NOT NULL,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS attachment_metrics (
    id SERIAL PRIMARY KEY,
    attachment_id INTEGER NOT NULL,
    user_id BIGINT,
    action_type TEXT NOT NULL CHECK (action_type IN ('view', 'click', 'share', 'copy', 'rate')),
    session_id TEXT,
    metadata JSONB,
    action_date TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS attachment_performance (
    attachment_id INTEGER NOT NULL,
    performance_date DATE NOT NULL,
    popularity_score REAL NOT NULL DEFAULT 0,
    trending_score REAL NOT NULL DEFAULT 0,
    engagement_rate REAL NOT NULL DEFAULT 0,
    quality_score REAL NOT NULL DEFAULT 0,
    rank_in_weapon INTEGER,
    rank_overall INTEGER,
    PRIMARY KEY (attachment_id, performance_date)
);

CREATE TABLE IF NOT EXISTS cms_content (
    content_id SERIAL PRIMARY KEY,
    content_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    author_id BIGINT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS analytics_users (
    user_id BIGINT PRIMARY KEY,
    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
    registration_source TEXT,
    join_attempts INTEGER NOT NULL DEFAULT 0,
    successful_joins INTEGER NOT NULL DEFAULT 0,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    channels_joined JSONB
);

CREATE TABLE IF NOT EXISTS analytics_channels (
    channel_id TEXT PRIMARY KEY,
    title TEXT,
    url TEXT,
    added_at TIMESTAMP NOT NULL DEFAULT NOW(),
    removed_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'active',
    total_joins INTEGER NOT NULL DEFAULT 0,
    total_join_attempts INTEGER NOT NULL DEFAULT 0,
    conversion_rate NUMERIC NOT NULL DEFAULT 0,
    changes JSONB
);

CREATE TABLE IF NOT EXISTS analytics_daily_stats (
    date DATE PRIMARY KEY,
    new_users INTEGER NOT NULL DEFAULT 0,
    successful_joins INTEGER NOT NULL DEFAULT 0,
    failed_joins INTEGER NOT NULL DEFAULT 0,
    total_attempts INTEGER NOT NULL DEFAULT 0,
    conversion_rate NUMERIC NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS subscribers (
    user_id BIGINT PRIMARY KEY,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    subscribed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_sched_notif_next_run
    ON scheduled_notifications (next_run_at);
CREATE INDEX IF NOT EXISTS ix_sched_notif_enabled_next
    ON scheduled_notifications (enabled, next_run_at);
CREATE INDEX IF NOT EXISTS ix_am_attachment_date
    ON attachment_metrics (attachment_id, action_date);
CREATE INDEX IF NOT EXISTS ix_am_action_date
    ON attachment_metrics (action_type, action_date);
CREATE INDEX IF NOT EXISTS ix_am_attachment_action
    ON attachment_metrics (attachment_id, action_type);
CREATE INDEX IF NOT EXISTS ix_am_user
    ON attachment_metrics (user_id);
CREATE INDEX IF NOT EXISTS ix_cms_content_status_pub
    ON cms_content (status, published_at DESC);
CREATE INDEX IF NOT EXISTS ix_cms_content_type_status
    ON cms_content (content_type, status);
CREATE INDEX IF NOT EXISTS ix_cms_content_tags_gin
    ON cms_content USING gin (tags);
