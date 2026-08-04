-- ============================================================================
-- Migration: Add missing 24 weapons
-- Description: Adds newly released CoDM weapons to the database safely
-- ============================================================================

WITH new_weapons (cat_name, w_name) AS (
    VALUES
        -- Assault Rifles
        ('assault_rifle', 'XM4'), ('assault_rifle', 'Vargo-S'), 
        ('assault_rifle', 'RAM-7'), ('assault_rifle', 'Lachmann-556'), 
        ('assault_rifle', 'BAL-27'), ('assault_rifle', 'Cronen Squall'),
        
        -- SMGs
        ('smg', 'VMP'), ('smg', 'Sten'), ('smg', 'LC10'), 
        ('smg', 'FSS Hurricane'), ('smg', 'MicroMG 9mm'),

        -- LMGs
        ('lmg', 'PKM'), ('lmg', 'RAAL MG'), ('lmg', 'MG 82'), ('lmg', 'DP27'),

        -- Snipers
        ('sniper', '3-Line Rifle'),

        -- Marksman
        ('marksman', 'Type 63'), ('marksman', 'M1 Garand'), ('marksman', 'SO-14'),

        -- Shotguns
        ('shotgun', 'VLK Rogue'), ('shotgun', 'Einhorn Revolving'), ('shotgun', 'MX Guardian'),

        -- Pistols
        ('pistol', 'Crossbow'), ('pistol', 'Machine Pistol')
)
INSERT INTO weapons (category_id, name)
SELECT c.id, nw.w_name
FROM new_weapons nw
JOIN weapon_categories c ON c.name = nw.cat_name
ON CONFLICT (category_id, name) DO NOTHING;
