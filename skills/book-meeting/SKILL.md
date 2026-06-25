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
   - If `negotiation.status` is `accepted`, create a Google Calendar event for `negotiation.accepted` with the selected contact (use their email as attendee).
   - If `negotiation.status` is `no_agreement`, tell the user you could not agree on a time and suggest trying different times.
   - If there is no `negotiation` field, confirm the chosen contact (name and email) only.
8. Confirm the outcome to the user (booked time, or why it failed).

## Rules
- Always run step 1 before anything else.
- Always pass `confirm_selection=True` when searching contacts for this skill.
- Do not call search_contacts without `confirm_selection` when booking.
