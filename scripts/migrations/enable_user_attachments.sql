-- Enable User Attachment System
-- This script explicitly sets the 'system_enabled' setting to '1' (true) in user_attachment_settings table.
-- This ensures the "User Attachments" button is visible in the main menu.

INSERT INTO settings (key, value, description, category, data_type, updated_at)
VALUES ('system_enabled', '1', 'Enable User Attachments System', 'user_attachments', 'boolean', NOW())
ON CONFLICT (key) 
DO UPDATE SET value = '1', updated_at = NOW();
