# Slot Manager (Discord bot + Dashboard) — with per-slot padding

This project provides a dashboard + discord bot to create "slots" 2–25 with editable backgrounds (PNG/GIF via Cloudinary), team name, tag, emoji, font adjustments, and per-slot padding (top & bottom in pixels). Images are generated as PNG or GIF (text overlay on each frame).

## Key additions
- `padding_top` and `padding_bottom` (pixels) stored per slot.
- Dashboard allows editing top/bottom padding.
- Rendering logic positions text centered within the band between top and bottom padding.

## Deployment & usage
(see previous instructions in the scaffold — same steps: deploy backend on Render, set env, add bot, set Cloudinary, run frontend)

