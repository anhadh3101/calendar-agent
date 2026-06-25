---
name: meeting-negotiation
description: Proposes, counters, and accepts meeting times using calendar availability. Use when scheduling meetings, negotiating slots with another agent, or responding to A2A negotiation messages.
---

# Meeting Negotiation

## When to use
- User asks to schedule a meeting with someone
- A peer proposes a time slot
- You need to counter-propose or accept

## Workflow
1. Check calendar availability for the proposed window (Composio Google Calendar tools)
2. If free: respond with `ACCEPT: [ISO datetime]`
3. If busy: propose 2–3 alternatives in the same week
4. Keep responses concise — one slot per line

## Output format
- Accept: `ACCEPT: 2026-06-25T14:00:00-07:00`
- Counter: `COUNTER: [slot1], [slot2], [slot3]`
