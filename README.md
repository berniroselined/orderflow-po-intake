# OrderFlow: AI-Assisted PO Intake & Reporting

A portfolio project that turns distributor purchase order (PO) emails into checked, structured data. **All data is fictional.**

**Live demo:** https://orderflow-po-intake.streamlit.app/

## The problem
Distributors send purchase orders by email in different layouts. Typing them into a system by hand is slow, and errors (missing PO numbers, wrong prices, duplicates, wrong senders) are easy to miss.

## How it works
1. **AI-assisted extraction (manual step):** a PO email is pasted into Claude, which returns the fields as JSON.
2. **Validation (Python):** nine rules check each order: missing PO number, subject vs body PO number mismatch, duplicate PO number, distributor name spelling variation, sender email mismatch, delivery date before order date, quantity not a number, unknown product, and price more than 5% away from the standard price.
3. **Storage (SQL):** orders are saved to a SQLite database. Each order is marked clean or needs_review, and each error goes to an exceptions table that acts as a review queue.
4. **Review app (Streamlit):** a web page where a user pastes one order's JSON and sees the result.

## Results on my development set
- 8 fictional POs with 8 planted errors: the checks caught 8 of 8, with 0 false alarms.
- 2 orders clean, 6 flagged for review, 28 line items, 8 exceptions stored.
- This is a development set that I built the rules on, so it is not a test on unseen data.
- The subject vs body PO number check was tested on a hand-made example only. The AI-written answer key listed a mismatch on PO 3 that was not in the PO text, so I corrected the key.

## Limits
- The AI extraction step is manual (copy and paste) so the project stays free. It is not a fully automated pipeline.
- The web app keeps its list of checked orders for one visit only. The SQL database lives in the notebook.
- Rules and thresholds are fixed in the code, and the test data is small and fictional.

## Files
- `OrderFlow_Phase1.ipynb`: the Python and SQL notebook (Google Colab)
- `app.py`: the Streamlit app
- `requirements.txt`: the app's dependencies
- `sample_POs.txt`: 8 fictional PO emails
- `answer_key.xlsx`: the expected results for the 8 POs

## Tools
Python, pandas, SQL (SQLite), Streamlit, Claude (for extraction), Google Colab, GitHub.

## Next phases
Reconciliation of POs against invoices and deliveries, a data quality monitor, Power BI reporting, workflow automation, and process documentation.
