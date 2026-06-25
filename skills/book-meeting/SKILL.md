---
name: book-meeting
description: Books a meeting with another person. Use when the user wants to schedule, book, or set up a meeting with someone by name.
---

# Book Meeting

## When to use
- User asks to book, schedule, or set up a meeting with someone
- User names a person they want to meet with

## Workflow
1. Call **check_calendar_connected** first.
2. If `connected` is false, stop immediately. Tell the user to connect Google Calendar using the **Connect Google Calendar** button in the app header, then try booking again. Do not call search_contacts or any other tools.
3. Extract the person's name from the user's message.
4. Call **search_contacts** with `confirm_selection=True`.
5. If status is `not_found`, tell the user no matching contact exists.
6. If status is `cancelled`, tell the user booking was cancelled.
7. If status is `selected`:
   - Read `negotiation.text` — the free-flow availability discussion between your agent and the contact's agent.
   - Present that text clearly to the user as the proposed meeting availability, and confirm the chosen contact (name and email).
   - Do NOT create a calendar event yet. Slot selection and sending the invite come later.
   - If `negotiation.text` is missing or empty, tell the user availability could not be retrieved and suggest trying again.

## Rules
- Always run step 1 before anything else.
- Always pass `confirm_selection=True` when searching contacts for this skill.
- Do not call search_contacts without `confirm_selection` when booking.
