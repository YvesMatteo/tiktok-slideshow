#!/usr/bin/env python3
"""Render the MCP slideshow in the Poppins display font (the @volkan.js look):
the same layout the generator already produces -- white captions on the photo
with a soft shadow, a dark rounded number pill up top -- but set in Poppins
Bold instead of Inter, which is the heavier, rounded feel in the reference.

HOW IT WORKS (and why it doesn't modify anything protected):
The generator (make_mcp_slideshow.py) draws every piece of text with the two
module-level font paths mcp_slideshow.FONT_BOLD / .FONT_SEMI, resolved at call
time. This wrapper imports that module, repoints those two variables at the
Poppins TTFs that are ALREADY bundled in assets/fonts/, and then calls the
generator's own main(). No generator/copy-bank/plate/font file is edited on
disk; only in-memory variables are swapped for this one process. The random
server pick, captions, title, hashtags, and layout are 100% the generator's.

USAGE -- drop-in replacement for the generator in the scheduled task:
    python3 scripts/apply_caption_style.py
It prints the SAME stdout as make_mcp_slideshow.py (GENERATED AT:, FIRST
SLIDE:, run folder, order, title, hook, hashtags) so the rest of the pipeline
(apply_start_slide.py, the report step) is unchanged.

If Poppins is missing for any reason, it falls back to the generator's normal
Inter fonts and still produces a valid run (never blocks the schedule).
"""
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _SCRIPT_DIR)

_FONTS = os.path.join(_SKILL_DIR, 'assets', 'fonts')
_POPPINS_BOLD = os.path.join(_FONTS, 'Poppins-Bold.ttf')
_POPPINS_SEMI = os.path.join(_FONTS, 'Poppins-SemiBold.ttf')

import mcp_slideshow as ms
import make_mcp_slideshow as gen


def _apply_poppins():
    """Repoint the compositor's fonts to Poppins if available. Returns the
    name of the font family actually in effect."""
    if os.path.exists(_POPPINS_BOLD):
        ms.FONT_BOLD = _POPPINS_BOLD
        ms.FONT_SEMI = _POPPINS_SEMI if os.path.exists(_POPPINS_SEMI) else _POPPINS_BOLD
        for attr in ('FONT_BOLD', 'FONT_SEMI'):
            if hasattr(gen, attr):
                setattr(gen, attr, getattr(ms, attr))
        return 'Poppins'
    return 'Inter (Poppins not found -- fell back)'


def main():
    family = _apply_poppins()
    print(f"[apply_caption_style] font family in effect: {family}")
    return gen.main()


if __name__ == '__main__':
    main()
