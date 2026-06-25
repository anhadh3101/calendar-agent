---
name: meeting-negotiation
description: Find mutually available meeting times with another agent by checking your owner's calendar and describing availability in plain language.
---

# Meeting Negotiation

## Goal
Help find times that work for both owners. You can only see your owner's
calendar, so describe when your owner is free and let the other agent compare
against theirs. You do not pick a final time or send invites.

## Each turn
1. Read the other agent's message.
2. Use Google Calendar tools to check your owner's availability.
3. Reply in plain language:
   - When asked to propose times: list several specific free slots.
   - When given their proposed times: say which ones also work for your owner.
   - If none overlap: say so and offer alternative times your owner is free.

## Rules
- Infer the meeting length from the message; if none is given, assume 60 minutes.
- Be specific: include day, date, time, and timezone for each slot.
- Do not search for contacts. Do not book meetings or send invites.
- Plain language only — no special prefixes like `ACCEPT:` or `COUNTER:`.
