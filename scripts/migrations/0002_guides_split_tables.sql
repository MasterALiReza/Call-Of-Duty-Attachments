-- Migration 0002: align guides media schema with async repositories
-- - Adds canonical split tables: guide_photos / guide_videos
-- - Backfills from legacy guide_media when available

CREATE TABLE IF NOT EXISTS guide_photos (
    id SERIAL PRIMARY KEY,
    guide_id INTEGER NOT NULL REFERENCES guides(id) ON DELETE CASCADE,
    file_id TEXT NOT NULL,
    caption TEXT,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS guide_videos (
    id SERIAL PRIMARY KEY,
    guide_id INTEGER NOT NULL REFERENCES guides(id) ON DELETE CASCADE,
    file_id TEXT NOT NULL,
    caption TEXT,
    sort_order INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_guide_photos_guide_sort
    ON guide_photos (guide_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_guide_videos_guide_sort
    ON guide_videos (guide_id, sort_order);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = 'guide_media'
    ) THEN
        INSERT INTO guide_photos (guide_id, file_id, caption, sort_order)
        SELECT gm.guide_id, gm.file_id, gm.caption, COALESCE(gm.order_index, 0)
        FROM guide_media gm
        WHERE gm.media_type = 'photo'
          AND NOT EXISTS (
              SELECT 1
              FROM guide_photos gp
              WHERE gp.guide_id = gm.guide_id
                AND gp.file_id = gm.file_id
          );

        INSERT INTO guide_videos (guide_id, file_id, caption, sort_order)
        SELECT gm.guide_id, gm.file_id, gm.caption, COALESCE(gm.order_index, 0)
        FROM guide_media gm
        WHERE gm.media_type = 'video'
          AND NOT EXISTS (
              SELECT 1
              FROM guide_videos gv
              WHERE gv.guide_id = gm.guide_id
                AND gv.file_id = gm.file_id
          );
    END IF;
END $$;
