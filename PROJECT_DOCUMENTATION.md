# AI Finance Coach — Project Documentation

## Project overview

AI Finance Coach is a browser based personal finance management and decision support prototype. It helps a user record money movement, compare expenses with a plan, track savings goals, and review plain language prompts generated from their own entered records. Recommendations use transparent if/then rules and arithmetic formulas; the prototype does not use fuzzy logic or a machine learning model.

## Requirements mapped to the prototype

| Synopsis requirement | Project implementation |
| --- | --- |
| Finance dashboard | Monthly income, spending, savings, health score, trend chart, category chart, recent activity, and budget pulse |
| Income and expense management | Add records, search and filter history, and export records as CSV |
| Budget management | Category limits, actual use, remaining amount, and over-limit indicators |
| Savings goals | Create goals, set a target date, track progress, and record contributions |
| Spending analysis | Category totals, six-month cash-flow trend, and budget threshold prompts |
| Financial health calculator | A visible 0–100 score, component indicators, and a plain language band |
| Recommendation engine | Rule-generated nudges based on budget use and savings rate |
| Monthly report | Current month totals plus a CSV export of transaction history |
| Database | SQLite tables for users, categories, transactions, budgets, and goals |

## Architecture

The browser UI is built with HTML, CSS, and JavaScript. A small Python HTTP server serves the pages and JSON endpoints. The server validates submitted values, performs the financial calculations, and reads and writes a local SQLite file. SQLite is used for a self-contained demonstration that runs without service setup; the synopsis names MySQL as its target database, so a MySQL adapter would be a suitable next deployment step.

```text
Browser pages (HTML / CSS / JavaScript)
             │ JSON requests
             ▼
Python local HTTP server and calculation rules
             │ SQL
             ▼
Local SQLite database (finance_coach.db)
```

## Database design

- `users`: demo profile and currency.
- `categories`: income and expense category labels and display colors.
- `transactions`: dated income and expense entries linked to a category and user.
- `budgets`: monthly category limits, unique per user and category.
- `financial_goals`: target amount, amount saved, and target date.

The schema is in `schema.sql`. Fictional seed data is initialized by `app.py` the first time it is run. The seed profile is a demonstration only. It contains 90 days of records, category budgets, and three savings goals.

## Calculation and recommendation rules

- **Net saved** = monthly income − monthly expenses.
- **Savings rate** = net saved ÷ monthly income × 100.
- **Expense ratio** = monthly expenses ÷ monthly income × 100.
- **Budget use** = category expenses this month ÷ category monthly limit × 100.
- **Goal progress** = amount saved ÷ target amount × 100, capped at 100 for display.
- **Health score** (capped to 0–100) combines up to 40 savings points, up to 30 expense-ratio points, and up to 30 budget-adherence points.
- **Score bands**: Strong (80–100), Building (60–79), Needs attention (below 60).
- Budget use above 100% generates an over-limit note. Use from 80% through 100% generates a near-limit note. A savings rate below 20% produces a savings review prompt.

These figures are illustrative project rules rather than official financial ratings. The app displays the inputs and rationale so the user can understand why a prompt appeared.

## User workflow

1. Start the app and review the overview dashboard.
2. Add income or expense entries on Transactions.
3. Set or update category limits on Budgets.
4. Create a savings target and add contributions on Savings goals.
5. Review the derived prompts and monthly summary on Insights & reports; export transaction history when needed.

## Validation and limitations

Form inputs are checked for required fields, positive amounts, valid dates, and category type. The server binds to `127.0.0.1` and keeps its database in the project folder. This is a single-user academic prototype: it has no registration, password authentication, CSRF defense, cloud hosting, bank/UPI connection, payment processing, investment advice, tax advice, or production deployment controls. The database can be reset by stopping the app and removing `finance_coach.db`; it will be recreated from seed data on next start.

## Suggested academic review checklist

- Start the server and open the local address in a browser.
- Review each of the five navigation pages at desktop and mobile widths.
- Add an income entry and an expense entry, then confirm the dashboard and history update.
- Change a category budget and confirm the usage display responds.
- Create a savings goal, add a contribution, and confirm progress changes.
- Check that a CSV download contains the recorded transaction rows.
- Compare score and recommendation output against the documented formulas using a small hand-calculated sample.
