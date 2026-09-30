"""Shared locations for the offline sprite workflow; never deployed to Pages."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFRESH_MANIFEST = ROOT / 'assets/sprite_refresh_manifest.json'
STAGING = ROOT / 'assets/_generated_sprite_refresh'
BACKUPS = ROOT / 'assets/_backup_pre_sprite_refresh'
