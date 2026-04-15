-- Migration 0004: backfill canonical schema artifacts for legacy runtime-created DBs
-- This migration is additive and idempotent by design.

ALTER TABLE user_attachments
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP;

ALTER TABLE user_attachments
    ADD COLUMN IF NOT EXISTS deleted_by BIGINT REFERENCES admins(user_id);

ALTER TABLE user_attachments
    ADD COLUMN IF NOT EXISTS view_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_user_attachments_status
    ON user_attachments (status, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_attachments_user
    ON user_attachments (user_id);
CREATE INDEX IF NOT EXISTS idx_user_attachments_approved
    ON user_attachments (approved_at DESC) WHERE status = 'approved';

DO $$
DECLARE
    status_constraint RECORD;
BEGIN
    FOR status_constraint IN
        SELECT c.conname, pg_get_constraintdef(c.oid) AS definition
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = current_schema()
          AND t.relname = 'user_attachments'
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) ILIKE '%status%'
    LOOP
        IF status_constraint.conname <> 'user_attachments_status_check'
           OR status_constraint.definition NOT ILIKE '%deleted%'
        THEN
            EXECUTE format(
                'ALTER TABLE user_attachments DROP CONSTRAINT IF EXISTS %I',
                status_constraint.conname
            );
        END IF;
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = current_schema()
          AND t.relname = 'user_attachments'
          AND c.conname = 'user_attachments_status_check'
          AND pg_get_constraintdef(c.oid) ILIKE '%deleted%'
    ) THEN
        ALTER TABLE user_attachments
            ADD CONSTRAINT user_attachments_status_check
            CHECK (status IN ('pending', 'approved', 'rejected', 'deleted'));
    END IF;
END $$;

ALTER TABLE user_submission_stats
    ADD COLUMN IF NOT EXISTS deleted_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE ua_stats_cache
    ADD COLUMN IF NOT EXISTS deleted_count INTEGER DEFAULT 0;

ALTER TABLE analytics_users
    ADD COLUMN IF NOT EXISTS registration_source TEXT;

CREATE TABLE IF NOT EXISTS user_faq_votes (
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    faq_id INTEGER NOT NULL REFERENCES faqs(id) ON DELETE CASCADE,
    rating SMALLINT CHECK (rating IN (-1, 1)),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, faq_id)
);

CREATE TABLE IF NOT EXISTS guide_media (
    id SERIAL PRIMARY KEY,
    guide_id INTEGER NOT NULL REFERENCES guides(id) ON DELETE CASCADE,
    media_type TEXT NOT NULL CHECK (media_type IN ('photo', 'video')),
    file_id TEXT NOT NULL,
    caption TEXT,
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
