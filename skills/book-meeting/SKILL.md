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
   - Read `negotiation.outcome` and `negotiation.transcript`.
   - If outcome is not `done`, tell the user negotiation did not succeed and suggest trying again.
   - If outcome is `done`:
     - From the last `me` turn with status `done`, take every bullet under **My owner's availability** and pass them all to **select_meeting_slot**.
     - Each slot needs `id`, `label`, `start` (ISO 8601 UTC), and `end` (ISO 8601 UTC).
     - Do not list slots in chat; use the tool.
   - If `negotiation` is missing or transcript is empty, tell the user availability could not be retrieved.
8. If slot selection returns `selected`:
   - Create a Google Calendar event using `slot.start` and `slot.end`.
   - Add the contact's email from the search result as an attendee.
   - Confirm the booking to the user with the chosen time and contact name.
9. If slot selection returns `cancelled` or `no_slots`:
   - Tell the user booking was cancelled or no times could be parsed; suggest trying again.

## Rules
- Always run step 1 before anything else.
- Always pass `confirm_selection=True` when searching contacts for this skill.
- Do not call search_contacts without `confirm_selection` when booking.
