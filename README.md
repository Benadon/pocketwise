# AI Finance Coach

A five page personal finance decision support project based on the supplied synopsis. The runnable prototype uses Python's standard library and a local SQLite database, so it has no package installation step.

## Pages

- **Overview**: monthly cash flow, category spend, health score, and next steps.
- **Transactions**: add income or expense records and review history.
- **Budgets**: set category limits and see actual usage.
- **Goals**: create savings goals and add contributions.
- **Insights**: rule based recommendations, monthly summary, and CSV export.

## Run

Requires Python 3.9 or later.

1. Open a terminal in this folder.
2. Run `python app.py`.
3. Open `http://127.0.0.1:8000`.

On first run the app creates `finance_coach.db` and seeds an example user, 90 days of sample transactions, budgets, and savings goals. Records added in the UI are stored in the same local database. Delete the database file to reset the demo.

## Project structure

- `app.py` — local web server, API, SQLite schema, and demo seed data.
- `static/index.html` — page shell.
- `static/styles.css` — responsive visual design.
- `static/app.js` — navigation, charts, forms, calculations, and API client.
- `schema.sql` — readable database design.
- `sample_data.json` — sample user and seed-data overview.

## Financial health rules

The prototype uses transparent project rules: savings rate contributes up to 40 points, expense ratio up to 30, and budget adherence up to 30. The labels are **Strong** (80–100), **Building** (60–79), and **Needs attention** (below 60). Budget use above 100% generates an overrun insight; savings below 20% prompts a savings review. These are illustrative educational thresholds, not official ratings or financial advice.

## Scope and privacy

This prototype is for a college project and uses fictional sample data. It has no authentication, bank or UPI integration, payment processing, cloud storage, or regulated investment, tax, or credit advice. The local demo database is not designed for production deployment or multi-user use.
