---
name: meeting-negotiation
description: Find mutually available meeting times with another agent by checking your owner's calendar and describing availability using a consistent response format.
---

# Meeting Negotiation

## Goal
Help find times that work for both owners. You can only see your owner's
calendar, so describe when your owner is free and let the other agent compare
against theirs. You do not pick a final time or send invites.

## Each turn
1. Read the other agent's message.
2. Use Google Calendar tools to check your owner's availability.
3. Reply using the response format below.

## Response format

Use this structure every turn. Keep section headers exactly as shown.

**Summary**
One sentence: what you understood and what you are doing this turn.

**My owner's availability**
- [Day, Mon DD] [start]–[end] [timezone]
- [Day, Mon DD] [start]–[end] [timezone]

Use 2–5 slots when proposing. When responding to their slots, list only overlaps
or write "None of these work" and offer alternatives.

**Question**
One clear ask for the peer, e.g. "Which of these works for your owner?" or
"Can you propose times next week?"

## Turn-specific rules

### When proposing times
- Put all proposed slots under **My owner's availability**.
- End with **Question**: ask them to pick one or counter.

### When they proposed times
- Under **My owner's availability**, list only slots that work for your owner.
- If none work, write "None of these work" and offer 2–3 alternatives.
- End with **Question**.

### When overlaps are found
- **Summary**: state how many mutually workable times you found.
- **My owner's availability**: list every overlap (one bullet per slot).
- **Question**: "Our owners will choose from these options."

## Rules
- Infer the meeting length from the message; if none is given, assume 60 minutes.
- Always use the same time style (12-hour or 24-hour) and include timezone (e.g. PDT).
- One slot per bullet; never run slots together in a paragraph.
- Never pick a final meeting time or say a slot is "agreed" — only list options.
- Do not search for contacts. Do not book meetings or send invites.
- No special prefixes like `ACCEPT:` or `COUNTER:`.
