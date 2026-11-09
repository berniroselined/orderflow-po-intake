import json
import difflib
from datetime import date

import pandas as pd
import streamlit as st

st.set_page_config(page_title="OrderFlow", layout="wide")

# ---------- Reference data (fictional) ----------
REGISTRY = {
    "Nusantara Niaga PT": ("Indonesia", "procurement@nusantaraniaga.example"),
    "Jakarta Prima Distribution PT": ("Indonesia", "gudang@jakartaprima.example"),
    "Klang Valley Distribution": ("Malaysia", "orders@klangvalleydist.example"),
    "Penang Consumer Supplies": ("Malaysia", "orders@penangconsumer.example"),
    "Siam Retail Partners Co Ltd": ("Thailand", "purchasing@siamretailpartners.example"),
    "Manila Bay Trading Corp": ("Philippines", "carlo@manilabaytrading.example"),
    "Saigon Fresh Distribution JSC": ("Vietnam", "purchasing@saigonfresh.example"),
    "Lion City Trading Pte Ltd": ("Singapore", "ops@lioncitytrading.example"),
}

STANDARD_PRICES = {
    "Instant Kopi Mix 20s": 6.06,
    "Sambal Chilli Sauce 250ml": 3.34,
    "Jasmine Green Tea 25 bags": 3.70,
    "Coconut Biscuits 200g": 2.10,
    "Electrolyte Sachets 12s": 6.83,
    "Vitamin C Gummies 60s": 11.35,
    "Collagen Drink Box 10s": 18.56,
    "Herbal Throat Lozenges 24s": 3.28,
    "Ultra Laundry Detergent 2kg": 9.30,
    "Fabric Softener 1.5L": 5.53,
    "Citrus Dishwash Liquid 750ml": 2.98,
    "Lavender Floor Cleaner 1L": 4.20,
    "Aloe Fresh Body Wash 500ml": 4.04,
    "Gentle Sunscreen SPF50 100ml": 8.58,
    "Herbal Shampoo 400ml": 4.77,
    "Whitening Toothpaste 150g": 2.49,
}

PRICE_TOLERANCE = 0.05  # a price more than 5% away from standard is flagged


# ---------- Checking logic ----------
def find_distributor(written):
    w = (written or "").lower().strip()
    if not w:
        return None, None
    names = list(REGISTRY.keys())
    for n in names:
        if w == n.lower() or w in n.lower() or n.lower() in w:
            return n, "ok"
    close = difflib.get_close_matches(written, names, n=1, cutoff=0.85)
    if close:
        return close[0], "close"
    return None, None


def clean_product_names(data):
    canonical = {name.lower(): name for name in STANDARD_PRICES}
    for item in data.get("items", []):
        key = " ".join(str(item.get("product", "")).lower().split())
        if key in canonical:
            item["product"] = canonical[key]
    return data


def validate(data, seen):
    errors = []

    subj = data.get("po_number_subject")
    body = data.get("po_number_body")
    if not subj and not body:
        errors.append("Missing PO number")
    if subj and body and subj.strip() != body.strip():
        errors.append(f"Subject vs body PO number mismatch ({subj} vs {body})")
    po_no = body or subj
    if po_no:
        if po_no in seen:
            errors.append(f"Duplicate PO number: {po_no}")
        seen.add(po_no)

    written = data.get("distributor_as_written")
    official, how = find_distributor(written)
    if official is None:
        errors.append(f"Unknown distributor: {written}")
    else:
        if how == "close":
            errors.append(f"Distributor name spelling variation: '{written}' vs '{official}'")
        official_email = REGISTRY[official][1]
        if (data.get("sender_email") or "").strip().lower() != official_email.lower():
            errors.append(f"Sender email mismatch: {data.get('sender_email')} vs {official_email}")

    po_date = data.get("po_date")
    delivery = data.get("delivery_date")
    if po_date and delivery:
        if date.fromisoformat(delivery) < date.fromisoformat(po_date):
            errors.append("Delivery date before order date")

    for item in data.get("items", []):
        name = item.get("product")
        if item.get("quantity_number") is None:
            errors.append(f"Quantity not a number: {name} ('{item.get('quantity_raw')}')")
        if name not in STANDARD_PRICES:
            errors.append(f"Unknown product: {name}")
        else:
            std = STANDARD_PRICES[name]
            price = item.get("unit_price")
            if price is not None and abs(price - std) / std > PRICE_TOLERANCE:
                errors.append(f"Price differs from standard: {name} ({price} vs {std})")
    return errors


def items_table(data):
    rows = []
    for item in data.get("items", []):
        qty = item.get("quantity_number")
        price = item.get("unit_price")
        total = round(qty * price, 2) if qty is not None and price is not None else None
        rows.append({
            "Product": item.get("product"),
            "Quantity as written": item.get("quantity_raw"),
            "Quantity": qty,
            "Unit price": price,
            "Line total": total,
        })
    return pd.DataFrame(rows, columns=["Product", "Quantity as written", "Quantity", "Unit price", "Line total"])


# ---------- Example data (from the fictional test set) ----------
def make(sender, name, subj, body, po_date, delivery, items):
    return {
        "sender_email": sender, "distributor_as_written": name,
        "po_number_subject": subj, "po_number_body": body,
        "po_date": po_date, "delivery_date": delivery, "currency": "SGD",
        "items": [{"product": p, "quantity_raw": r, "quantity_number": q, "unit_price": u}
                  for p, r, q, u in items],
    }


EXAMPLES = {
    "PO 2: clean order": make(
        "orders@klangvalleydist.example", "Klang Valley Distribution",
        "KVD/2026/0315", "KVD/2026/0315", "2026-07-09", "2026-08-05",
        [("Electrolyte Sachets 12s", "400", 400, 6.83),
         ("Vitamin C Gummies 60s", "250", 250, 11.35)]),
    "PO 4: missing PO number, quantity in words": make(
        "carlo@manilabaytrading.example", "Manila Bay Trading", None, None,
        "2026-08-03", "2026-08-31",
        [("Ultra Laundry Detergent 2kg", "240 pcs", 240, 9.30),
         ("Fabric Softener 1.5L", "two hundred pcs", None, 5.53)]),
    "PO 6: delivery before order date": make(
        "ops@lioncitytrading.example", "Lion City Trading Pte Ltd",
        "LCT-2026-0087", "LCT-2026-0087", "2026-08-18", "2026-08-15",
        [("Instant Kopi Mix 20s", "1000 units", 1000, 6.06)]),
    "PO 8: duplicate number and wrong sender (check PO 2 first)": make(
        "purchasing@klangvalleydist.example", "Klang Valley Distribution",
        "KVD/2026/0315", "KVD/2026/0315", "2026-09-15", "2026-10-14",
        [("Herbal Shampoo 400ml", "300 units", 300, 4.77)]),
}


# ---------- Session memory ----------
if "seen" not in st.session_state:
    st.session_state.seen = set()
if "queue" not in st.session_state:
    st.session_state.queue = []


# ---------- Page ----------
st.title("OrderFlow: AI-Assisted PO Intake & Reporting")
st.caption("Portfolio project using fictional data. Paste the JSON that Claude "
           "extracted from a purchase order email, and the app checks it.")

with st.expander("How to use this app"):
    st.write(
        "1. Paste a purchase order email into Claude and ask it to extract the data as JSON.\n"
        "2. Paste the JSON below, or pick an example.\n"
        "3. Click **Check order**. Orders with errors go to the review queue.\n\n"
        "Checking the same PO twice flags it as a duplicate. Use **Reset session** to start again."
    )

choice = st.selectbox("Load an example (optional)", ["(none)"] + list(EXAMPLES.keys()))
default_text = json.dumps(EXAMPLES[choice], indent=2) if choice != "(none)" else ""
text = st.text_area("Extracted JSON", value=default_text, height=320, key="box_" + choice)

col1, col2 = st.columns(2)
check = col1.button("Check order")
reset = col2.button("Reset session")

if reset:
    st.session_state.seen = set()
    st.session_state.queue = []
    st.info("Session reset. The duplicate memory and the review queue are empty.")

if check:
    cleaned = text.replace("\u201c", '"').replace("\u201d", '"')
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            data = data[0] if len(data) == 1 else None
        if not isinstance(data, dict):
            st.error("Please paste the JSON for one purchase order at a time.")
        else:
            data = clean_product_names(data)
            errors = validate(data, st.session_state.seen)
            table = items_table(data)
            value = round(table["Line total"].sum(), 2) if len(table) else 0.0
            po_no = data.get("po_number_body") or data.get("po_number_subject") or "(missing)"

            if errors:
                st.error(f"Needs review: {len(errors)} issue(s) found")
                for e in errors:
                    st.write("- " + e)
            else:
                st.success("Clean: no issues found")

            st.subheader("Order summary")
            st.write(f"**PO number:** {po_no}  |  **Distributor as written:** "
                     f"{data.get('distributor_as_written')}  |  **Sender:** {data.get('sender_email')}")
            st.write(f"**Order date:** {data.get('po_date')}  |  **Delivery date:** {data.get('delivery_date')}")
            st.dataframe(table)
            st.write(f"**Order value (SGD):** {value:,.2f}")
            if table["Line total"].isna().any():
                st.warning("Some lines have no numeric quantity, so the order value is understated.")

            st.session_state.queue.append({
                "PO number": po_no,
                "Distributor": data.get("distributor_as_written"),
                "Status": "needs_review" if errors else "clean",
                "Issues": len(errors),
                "Order value (SGD)": value,
            })
    except (json.JSONDecodeError, ValueError, KeyError, TypeError) as err:
        st.error(f"Could not read that input: {err}")

st.divider()
st.subheader("Checked orders this session")
if st.session_state.queue:
    queue_df = pd.DataFrame(st.session_state.queue)
    st.dataframe(queue_df)
    flagged = int((queue_df["Status"] == "needs_review").sum())
    st.write(f"{len(queue_df)} order(s) checked, {flagged} in the review queue.")
else:
    st.write("No orders checked yet.")

st.caption("Fictional data only. AI extraction is a manual step; validation rules run in code.")
