# Design

ProofPath uses the same look as its sister project Nirikshan. Screenshots placed in this folder override
these values (build spec, section 13). Until then, these are the design tokens. They are defined once
in `frontend/app/globals.css`. Phase 1 moves the hex values still written in components into these
tokens, and phase 6 adds a test that keeps them out.

| Token | Value | Use |
| --- | --- | --- |
| Accent | `#C25E26` (hover `#A84A19`) | Primary buttons, links, focus |
| Accent light | `#FBF0E4` | Selected and highlighted backgrounds |
| Border | `#E8E2D8` | Card and table borders |
| Page background | `#FAF7F2` with the grid texture | Body |
| Headings | Serif | Page and section headings |

Status meaning never relies on colour alone; every status also shows its text.
