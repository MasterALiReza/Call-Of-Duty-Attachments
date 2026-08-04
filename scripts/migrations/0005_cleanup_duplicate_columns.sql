-- Migration 0005: Cleanup duplicate columns
DO $$
BEGIN
    -- backfill: view_count از views_count
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name='user_attachments' AND column_name='views_count')
    AND EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name='user_attachments' AND column_name='view_count') THEN
        UPDATE user_attachments 
        SET view_count = GREATEST(view_count, COALESCE(views_count, 0));
        ALTER TABLE user_attachments DROP COLUMN views_count;
    END IF;
END $$;
