# Proposal: config-theme-unread

- Kind: gloss (a detail that doesn't align with the rounded plan)
- Surfaces: config, client
- Filed: 2026-11-14 01:48 by the self-maintenance census
- Status: WAITING for the owner's red pen — never auto-applied.

## Evidence

config.json offers 'theme'; no app/core source ever reads it — the value is decoration until wired

## Note

the wiring is a pure read, but it changes runtime behavior — red pen
