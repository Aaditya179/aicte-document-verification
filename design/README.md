# Design

ProofPath's look comes from Indian government file practice. Screenshots placed in this folder
override it (build spec, section 13). The tokens are defined once in `frontend/app/globals.css`;
components use only the token names, never hex values.

| Token | Value | Meaning |
| --- | --- | --- |
| `paper` | `#F3F4EF` | The page: cool register paper |
| `sheet` | `#FCFCFA` | A sheet laid on the page (tables, forms) |
| `ink` | `#1E2A44` | Blue-black ink: text and primary actions |
| `ink-2`, `ink-3` | `#4F5B73`, `#636D85` | Secondary and quiet text |
| `rule`, `rule-strong` | `#CDD3CC`, `#A3ADA5` | Ruled lines and borders |
| `officer` | `#1F6A4A` | Green ink, used only for what a person confirmed or did |
| `conflict` | `#B42318` | Red pencil: a conflict or a failed check |
| `pending` | `#7A4E00` | Waiting for a person |
| `mark` | `#F6E36A` | Highlighter on a value cited from a document |

- **Type:** Martel for headings and file numbers, Mukta for the interface. Both are from Indian type
  foundries and carry Devanagari, for a later Hindi interface.
- **The one bold element** is the highlighter: every value read from a document is marked and links
  to its page. Everything else stays quiet: ruled lines, a double ledger rule under the header and the
  file cover, 3 to 4 px radii, no gradients, no shadows, no pills.
- Status meaning never relies on colour alone; every status is also written out.
