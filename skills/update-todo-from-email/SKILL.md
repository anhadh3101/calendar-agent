---
name: update-todo-from-email
description: Reviews today's email for important items and adds them to the user's Notion to-do list after confirmation. Use when the user asks to update their to-do list, turn email into tasks, or sync their inbox into their to-dos.
---

# Update To-Do From Email

## When to use
- User asks to update, refresh, or build their to-do list
- User asks to turn today's email into tasks or check their inbox for things to do

## Workflow
1. Call **check_gmail_connected** first.
2. If `connected` is false, stop immediately. Tell the user in a friendly way that Gmail isn't connected yet and ask them to click the **Connect Gmail** button in the app header, then try again. Do not call any Gmail tools.
3. Fetch today's email with a Gmail tool. Use a search query of `newer_than:1d` (optionally combine with `in:inbox`) so you only look at recent mail.
4. Triage each email for importance using the criteria below. Skip anything that doesn't clearly require action.
5. For each important email, draft exactly one concrete to-do:
   - `title`: a short, actionable task (e.g. "Reply to Dana about the Q3 budget").
   - `note`: optional one-line context (e.g. a deadline).
   - `source`: the email subject or sender it came from.
6. Call **confirm_todos** with the full drafted list. Do NOT write to Notion yet.
7. Handle the result:
   - If status is `no_todos`, tell the user no important action items were found today.
   - If status is `cancelled`, tell the user nothing was added to their to-do list.
   - If status is `confirmed`, call **ask_notion_agent** with a clear, self-contained task to add exactly the approved to-dos (titles, and notes if present) to the user's to-do list in Notion.
8. Summarize for the user which to-dos were added.

## Importance criteria
- **Include**: explicit asks or action items, deadlines, meeting/scheduling requests, messages that need a reply, and tasks from real people.
- **Exclude**: newsletters, marketing/promotions, automated notifications, receipts, and social-media updates.

## Rules
- Always run step 1 before reading any email.
- Only look at today's email (`newer_than:1d`); do not pull in older mail.
- Never write to Notion before **confirm_todos** returns `confirmed`.
- Only add the approved subset returned by **confirm_todos** — never the full drafted list if the user deselected items.
- If the Notion subagent reports Notion isn't connected, tell the user to click the **Connect Notion** button in the app header.
