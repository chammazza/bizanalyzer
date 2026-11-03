"""BizAnalyzer - sales, profit & product analytics for small businesses (Streamlit)."""
import io
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="BizAnalyzer", page_icon="📊", layout="wide")

GREEN, BLUE = "#12B886", "#1C7ED6"
PALETTE = ["#12B886", "#1C7ED6", "#63E6BE", "#74C0FC", "#0CA678", "#4263EB", "#38D9A9", "#339AF0"]
PAGES = ["📊 Dashboard", "📤 Upload Data", "📈 Sales Analysis", "💰 Profit & Financial",
         "🛍️ Product Analysis", "📦 Inventory", "🧠 Smart Insights", "📑 Reports", "⚙️ Settings"]

# ----------------------------------------------------------------------------- styling
st.markdown(f"""
<style>
.block-container {{padding-top: 1.4rem; max-width: 1300px;}}
[data-testid="stSidebar"] {{background: linear-gradient(180deg,#0B3D2E 0%,#0B2F4F 100%);}}
[data-testid="stSidebar"] * {{color: #EAF6F1;}}
[data-testid="stSidebar"] [data-baseweb="select"] * {{color:#12263F;}}
.hero {{background: linear-gradient(120deg,{GREEN} 0%,{BLUE} 100%); color:#fff; padding:22px 28px;
        border-radius:20px; margin-bottom:18px; box-shadow:0 8px 24px rgba(28,126,214,.25);}}
.hero h1 {{margin:0; font-size:1.9rem; color:#fff;}}
.hero p {{margin:4px 0 0 0; opacity:.92;}}
.kpi {{background:#fff; border:1px solid #E3EAF2; border-left:5px solid var(--c); border-radius:16px;
       padding:14px 16px; box-shadow:0 2px 10px rgba(16,40,80,.06); margin-bottom:10px;}}
.kpi .l {{font-size:.72rem; color:#6B7A90; text-transform:uppercase; letter-spacing:.05em;}}
.kpi .v {{font-size:1.55rem; font-weight:700; color:#12263F; line-height:1.3;}}
.kpi .s {{font-size:.8rem; color:#6B7A90;}}
.up {{color:#0CA678 !important; font-weight:600;}} .down {{color:#E03131 !important; font-weight:600;}}
.insight {{background:#fff; border:1px solid #E3EAF2; border-radius:14px; padding:12px 16px; margin-bottom:8px;}}
.pill {{display:inline-block; padding:2px 10px; border-radius:99px; font-size:.75rem; font-weight:600;}}
</style>
""", unsafe_allow_html=True)


def hero(title, subtitle=""):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def show(fig, h=360):
    fig.update_layout(template="plotly_white", height=h, margin=dict(l=10, r=10, t=40, b=10),
                      colorway=PALETTE, legend=dict(orientation="h", y=-0.2),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    try:
        st.plotly_chart(fig, width="stretch")
    except TypeError:
        st.plotly_chart(fig, use_container_width=True)


def table(df, **kw):
    try:
        st.dataframe(df, width="stretch", hide_index=True, **kw)
    except TypeError:
        st.dataframe(df, use_container_width=True, hide_index=True, **kw)


def money(x):
    cur = st.session_state.currency
    return "—" if x is None or pd.isna(x) else f"{x:,.0f} {cur}"


def kpi(label, value, sub="", color=GREEN, delta=None):
    d = ""
    if delta is not None and not pd.isna(delta):
        cls = "up" if delta >= 0 else "down"
        d = f' <span class="{cls}">{"▲" if delta >= 0 else "▼"} {abs(delta):.1f}%</span>'
    st.markdown(f'<div class="kpi" style="--c:{color}"><div class="l">{label}</div>'
                f'<div class="v">{value}</div><div class="s">{sub}{d}</div></div>', unsafe_allow_html=True)


# ----------------------------------------------------------------------------- state
DEFAULTS = dict(raw=None, raw_name="", clean=None, report=None, expenses=None, inventory=None,
                currency="DH", low_stock=10, history=[], nav=PAGES[1], mapping={})
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

# ----------------------------------------------------------------------------- column detection
SYN = {
    "date": ["date", "order date", "date sold", "sale date", "sold at", "day", "jour"],
    "status": ["order status", "status", "statut"],
    "order_id": ["order id", "orderid", "order no", "order number", "invoice", "order", "commande"],
    "product": ["product", "product name", "item", "item name", "produit", "article", "sku"],
    "category": ["category", "categorie", "product category", "type", "famille"],
    "quantity": ["quantity", "qty", "units", "units sold", "quantite", "qte"],
    "price": ["selling price", "unit price", "sale price", "price", "prix", "prix de vente"],
    "cost": ["unit cost", "cost price", "cost", "cogs", "purchase price", "prix dachat", "prix achat", "cout"],
    "discount": ["discount", "remise", "reduction"],
}
REQUIRED = ["date", "product", "quantity", "price"]
LABELS = {"date": "Date", "order_id": "Order ID", "product": "Product", "category": "Category",
          "quantity": "Quantity", "price": "Selling Price", "cost": "Unit Cost",
          "discount": "Discount", "status": "Order Status"}


def _n(s):
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower().replace("_", " ").replace("é", "e").replace("è", "e")).strip()


def detect(cols, syn):
    normed = {c: _n(c) for c in cols}
    found, used = {}, set()
    for f, names in syn.items():
        hit = next((c for c, n in normed.items() if n in names and c not in used), None)
        if hit is None:
            hit = next((c for c, n in normed.items() if c not in used and any(s in n for s in names if len(s) > 5)), None)
        if hit is not None:
            found[f] = hit
            used.add(hit)
    return found


EXP_SYN = {"date": SYN["date"], "category": ["expense category", "category", "categorie", "type", "expense"],
           "amount": ["amount", "montant", "value", "cost", "total"]}
INV_SYN = {"product": SYN["product"], "stock": ["stock", "current stock", "quantity", "qty", "on hand", "inventory"],
           "reorder": ["reorder level", "min stock", "minimum", "reorder point", "min"],
           "unit_cost": ["unit cost", "cost", "cost price", "purchase price"]}


# ----------------------------------------------------------------------------- cleaning
def build_clean(raw, m, discount_type, excl_status, drop_dups):
    d = pd.DataFrame(index=raw.index)
    d["date"] = pd.to_datetime(raw[m["date"]], errors="coerce")
    d["product"] = raw[m["product"]].astype(str).str.strip().replace({"nan": np.nan, "": np.nan})
    d["quantity"] = pd.to_numeric(raw[m["quantity"]], errors="coerce")
    d["price"] = pd.to_numeric(raw[m["price"]], errors="coerce")
    d["cost"] = pd.to_numeric(raw[m["cost"]], errors="coerce") if m.get("cost") else np.nan
    d["discount"] = pd.to_numeric(raw[m["discount"]], errors="coerce").fillna(0) if m.get("discount") else 0.0
    d["category"] = (raw[m["category"]].astype(str).str.strip().replace({"nan": "Uncategorized", "": "Uncategorized"})
                     if m.get("category") else "Uncategorized")
    d["status"] = raw[m["status"]].astype(str).str.strip() if m.get("status") else "—"
    d["order_id"] = raw[m["order_id"]].astype(str) if m.get("order_id") else "ROW" + pd.Series(raw.index + 1, index=raw.index).astype(str)

    rep = {"total_rows": len(raw), "has_cost": bool(m.get("cost")), "has_orderid": bool(m.get("order_id"))}
    rep["missing"] = {LABELS[f]: int(d[{"date": "date", "product": "product", "quantity": "quantity", "price": "price"}[f]].isna().sum()) for f in REQUIRED}
    bad = d.date.isna() | d["product"].isna() | d.quantity.isna() | d.price.isna() | (d.quantity <= 0) | (d.price < 0)
    dups = raw.duplicated(keep="first")
    rep["invalid"] = int(bad.sum())
    rep["invalid_idx"] = list(raw.index[bad][:200])
    rep["duplicates"] = int(dups.sum())
    keep = ~bad
    if drop_dups:
        keep &= ~dups
    st_ex = d.status.isin(excl_status)
    rep["excluded_status"] = int((st_ex & keep).sum())
    keep &= ~st_ex
    d = d[keep].copy()
    gross = d.quantity * d.price
    disc = gross * d.discount.clip(0, 100) / 100 if discount_type.startswith("Percent") else d.discount.clip(lower=0)
    d["discount_amt"] = np.minimum(disc, gross)
    d["revenue"] = gross - d.discount_amt
    d["cogs"] = d.quantity * d.cost
    d["profit"] = d.revenue - d.cogs
    d["month"] = d.date.dt.to_period("M").dt.to_timestamp()
    d["day"] = d.date.dt.normalize()
    d["weekday"] = d.date.dt.day_name()
    rep["rows_clean"] = len(d)
    rep["no_cost"] = int(d.cogs.isna().sum())
    return d.reset_index(drop=True), rep


def clean_expenses(raw, m):
    e = pd.DataFrame({"date": pd.to_datetime(raw[m["date"]], errors="coerce"),
                      "category": raw[m["category"]].astype(str).str.strip() if m.get("category") else "Other",
                      "amount": pd.to_numeric(raw[m["amount"]], errors="coerce")})
    e = e.dropna(subset=["date", "amount"])
    e["month"] = e.date.dt.to_period("M").dt.to_timestamp()
    return e.reset_index(drop=True)


def read_any(f, sheet=None):
    if f.name.lower().endswith(".csv"):
        try:
            return pd.read_csv(f, sep=None, engine="python")
        except Exception:
            f.seek(0)
            return pd.read_csv(f, encoding="latin-1", sep=None, engine="python")
    return pd.read_excel(f, sheet_name=sheet or 0)


# ----------------------------------------------------------------------------- demo & template
def demo_data():
    rng = np.random.default_rng(42)
    prods = [("Serum", "Skincare", 120, 60, 1.2), ("Perfume", "Fragrance", 250, 130, 0.8),
             ("Cream", "Skincare", 80, 35, 0.6), ("Lipstick", "Makeup", 95, 40, 0.9),
             ("Shampoo", "Haircare", 70, 32, 1.0), ("Body Lotion", "Skincare", 65, 48, 1.9),
             ("Mascara", "Makeup", 110, 45, 0.5), ("Hair Oil", "Haircare", 90, 28, 0.7)]
    days = pd.date_range("2026-01-01", "2026-10-31")
    rows, oid = [], 1
    w = np.array([p[4] for p in prods]); w = w / w.sum()
    for i, day in enumerate(days):
        n = rng.poisson(4 + 5 * i / len(days) + (1.5 if day.weekday() >= 4 else 0))
        for _ in range(n):
            p = prods[rng.choice(len(prods), p=w)]
            status = rng.choice(["Delivered", "Cancelled", "Returned"], p=[.89, .07, .04])
            rows.append([day.strftime("%Y-%m-%d"), f"ORD{oid:05d}", p[0], p[1], int(rng.integers(1, 5)),
                         p[2], p[3], int(rng.choice([0, 0, 0, 5, 10, 15])), status])
            oid += 1
    sales = pd.DataFrame(rows, columns=["Date", "Order ID", "Product", "Category", "Quantity",
                                        "Selling Price", "Unit Cost", "Discount", "Order Status"])
    exp = []
    for mth in pd.period_range("2026-01", "2026-10", freq="M"):
        s = mth.to_timestamp()
        exp += [[s.strftime("%Y-%m-%d"), "Rent", 3000],
                [(s + pd.Timedelta(days=4)).strftime("%Y-%m-%d"), "Advertising", int(rng.integers(1500, 2800))],
                [(s + pd.Timedelta(days=9)).strftime("%Y-%m-%d"), "Delivery", int(rng.integers(800, 1500))],
                [(s + pd.Timedelta(days=14)).strftime("%Y-%m-%d"), "Packaging", int(rng.integers(300, 700))]]
    exp = pd.DataFrame(exp, columns=["Date", "Expense Category", "Amount"])
    inv = pd.DataFrame({"Product": [p[0] for p in prods], "Current Stock": [18, 40, 0, 7, 120, 12, 55, 26],
                        "Reorder Level": [25, 20, 15, 15, 40, 30, 15, 20], "Unit Cost": [p[3] for p in prods]})
    return sales, exp, inv


def template_xlsx():
    s, e, i = demo_data()
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        s.head(10).to_excel(w, sheet_name="Sales", index=False)
        e.head(6).to_excel(w, sheet_name="Expenses", index=False)
        i.to_excel(w, sheet_name="Inventory", index=False)
    return buf.getvalue()


def load_demo():
    s, e, i = demo_data()
    m = detect(s.columns, SYN)
    clean, rep = build_clean(s, m, "Percent (%)", ["Cancelled", "Returned"], False)
    st.session_state.update(raw=s, raw_name="demo", clean=clean, report=rep, mapping=m, nav=PAGES[0],
                            expenses=clean_expenses(e, detect(e.columns, EXP_SYN)),
                            inventory=i.rename(columns={"Product": "product", "Current Stock": "stock",
                                                        "Reorder Level": "reorder", "Unit Cost": "unit_cost"}))
    log_history("Demo data")


def log_history(name):
    c = st.session_state.clean
    st.session_state.history.append({"File": name, "Rows analysed": len(c),
                                     "Period": f"{c.date.min():%Y-%m-%d} → {c.date.max():%Y-%m-%d}",
                                     "Revenue": round(c.revenue.sum(), 2)})


def confirm_cb():
    ss = st.session_state
    clean, rep = build_clean(ss.raw, ss.mapping, ss.get("opt_disc", "Percent (%)"), ss.get("opt_excl", []), ss.get("opt_dups", False))
    ss.clean, ss.report, ss.nav = clean, rep, PAGES[0]
    log_history(ss.raw_name)


def delete_cb():
    for k in ["raw", "clean", "report", "expenses", "inventory"]:
        st.session_state[k] = None
    st.session_state.update(raw_name="", history=[], mapping={}, nav=PAGES[1])


# ----------------------------------------------------------------------------- analytics
def kpis(df, exp):
    rev = df.revenue.sum()
    costed = df[df.cogs.notna()]
    has_cost = len(costed) > 0
    gross = costed.profit.sum() if has_cost else None
    cogs = costed.cogs.sum() if has_cost else None
    rev_c = costed.revenue.sum() if has_cost else None
    opex = exp.amount.sum() if exp is not None and len(exp) else None
    net = gross - opex if (gross is not None and opex is not None) else None
    orders = df.order_id.nunique()
    return dict(revenue=rev, cogs=cogs, gross=gross, opex=opex, net=net, orders=orders,
                units=df.quantity.sum(), aov=rev / orders if orders else np.nan,
                gross_margin=gross / rev_c * 100 if has_cost and rev_c else None,
                net_margin=net / rev * 100 if net is not None and rev else None,
                discounts=df.discount_amt.sum())


def product_table(df):
    g = df.groupby("product").agg(category=("category", "first"), units=("quantity", "sum"),
                                  revenue=("revenue", "sum"),
                                  cogs=("cogs", lambda s: s.sum(min_count=1)),
                                  profit=("profit", lambda s: s.sum(min_count=1))).reset_index()
    g["margin_%"] = np.where(g.profit.notna() & (g.revenue > 0), g.profit / g.revenue * 100, np.nan)
    return g.sort_values("revenue", ascending=False)


def pct(a, b):
    return (a - b) / b * 100 if b else np.nan


def insights(df, exp):
    out = []
    k = kpis(df, exp)
    mon = df.groupby("month").revenue.sum()
    if len(mon) >= 2:
        last, prev = mon.index[-1], mon.index[-2]
        ch = pct(mon.iloc[-1], mon.iloc[-2])
        partial = df.date.max() < last + pd.offsets.MonthEnd(0)
        out.append(("📈" if ch >= 0 else "📉",
                    f"Revenue {'increased' if ch >= 0 else 'decreased'} by {abs(ch):.1f}% in {last:%B %Y} compared to {prev:%B %Y}"
                    + (" (the last month is incomplete in your data, so compare with care)." if partial else ".")))
    if len(mon):
        out.append(("🏆", f"Best month: {mon.idxmax():%B %Y} with {money(mon.max())}."))
    pt = product_table(df)
    if len(pt):
        out.append(("💎", f"{pt.iloc[0]['product']} generated the highest revenue ({money(pt.iloc[0]['revenue'])})."))
        out.append(("📦", f"{pt.sort_values('units').iloc[-1]['product']} has the highest sales volume ({int(pt.units.max()):,} units)."))
        wp = pt.dropna(subset=["profit"])
        if len(wp):
            top = wp.sort_values("profit").iloc[-1]
            out.append(("💰", f"{top['product']} is the most profitable product ({money(top['profit'])} gross profit)."))
            avg = k["gross_margin"] or 0
            hv = wp[(wp.units >= wp.units.median()) & (wp["margin_%"] < avg - 5)].sort_values("units", ascending=False)
            for _, r in hv.head(2).iterrows():
                out.append(("⚠️", f"{r['product']} sells a lot ({int(r.units)} units) but its margin is only {r['margin_%']:.0f}% vs {avg:.0f}% overall - review its price or cost."))
            hm = wp[(wp.units < wp.units.median()) & (wp["margin_%"] > avg + 5)].sort_values("margin_%", ascending=False)
            for _, r in hm.head(2).iterrows():
                out.append(("🌱", f"{r['product']} has a strong margin ({r['margin_%']:.0f}%) but low volume - promoting it could grow profit."))
    wd = df.groupby("weekday").revenue.sum()
    if len(wd):
        out.append(("📅", f"{wd.idxmax()} is your strongest day of the week; {wd.idxmin()} is the weakest."))
    if k["discounts"] > 0 and (k["revenue"] + k["discounts"]) > 0:
        out.append(("🏷️", f"Discounts cost you {money(k['discounts'])} ({k['discounts'] / (k['revenue'] + k['discounts']) * 100:.1f}% of gross sales)."))
    if k["net"] is None and k["gross"] is not None:
        out.append(("ℹ️", "No operating expenses uploaded: net profit is not shown, only gross profit."))
    if k["gross"] is None:
        out.append(("ℹ️", "No unit cost column mapped: profit analysis is unavailable."))
    return out


def why_decrease(df):
    mon = df.groupby("month").agg(rev=("revenue", "sum"), orders=("order_id", "nunique"))
    if len(mon) < 2:
        return "I need at least two months of data to compare."
    (m1, a), (m2, b) = list(mon.iloc[-2:].iterrows())
    ch = pct(b.rev, a.rev)
    lines = [f"Revenue went from {money(a.rev)} in {m1:%B %Y} to {money(b.rev)} in {m2:%B %Y} ({ch:+.1f}%)."]
    lines.append(f"- Orders: {int(a.orders)} → {int(b.orders)} ({pct(b.orders, a.orders):+.1f}%).")
    lines.append(f"- Average order value: {money(a.rev / a.orders)} → {money(b.rev / b.orders)} ({pct(b.rev / b.orders, a.rev / a.orders):+.1f}%).")
    pm = df.pivot_table(index="product", columns="month", values="revenue", aggfunc="sum").fillna(0)
    delta = (pm[m2] - pm[m1]).sort_values()
    lines.append(f"- Biggest drop: {delta.index[0]} ({money(delta.iloc[0])}). Biggest gain: {delta.index[-1]} ({money(delta.iloc[-1])}).")
    if df.date.max() < m2 + pd.offsets.MonthEnd(0):
        lines.append(f"- Note: your data ends on {df.date.max():%Y-%m-%d}, so {m2:%B} may simply be incomplete.")
    return "\n".join(lines)


def answer(q, df, exp):
    ql = q.lower()
    pt = product_table(df)
    mon = df.groupby("month").revenue.sum()
    if "decreas" in ql or "drop" in ql or "why" in ql or "fall" in ql:
        return why_decrease(df)
    if "profit" in ql and pt.profit.notna().any():
        r = pt.dropna(subset=["profit"]).sort_values("profit").iloc[-1]
        return f"**{r['product']}** generated the highest gross profit: {money(r['profit'])} (margin {r['margin_%']:.1f}%)."
    if "month" in ql:
        return f"**{mon.idxmax():%B %Y}** had the highest revenue: {money(mon.max())}."
    if "revenue" in ql or "best" in ql or "top" in ql:
        r = pt.iloc[0]
        return f"**{r['product']}** has the highest revenue: {money(r['revenue'])} ({int(r.units)} units)."
    if "investigate" in ql or "next" in ql or "what should" in ql:
        tips = [t for ic, t in insights(df, exp) if ic in ("⚠️", "🌱", "📉", "🏷️", "ℹ️")]
        return "\n".join(f"- {t}" for t in tips) or "- Nothing alarming stands out. Compare months and products regularly."
    return "I can answer: highest profit, highest revenue, best month, why sales decreased, what to investigate next. Try one of those."


# ----------------------------------------------------------------------------- reports
def make_pdf(df, exp, period, sections):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.shapes import Drawing
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    cur = st.session_state.currency
    mny = lambda x: "-" if x is None or pd.isna(x) else f"{x:,.0f} {cur}"
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=colors.HexColor(GREEN), fontSize=24)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=colors.HexColor(BLUE))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm)
    el = [Paragraph("BizAnalyzer Report", h1), Paragraph(f"Period analysed: {period}", ss["Normal"]), Spacer(1, 14)]

    def tbl(rows, widths=None, header=True):
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        st_ = [("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#CBD5E1")), ("FONTSIZE", (0, 0), (-1, -1), 9),
               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F8F5")])]
        if header:
            st_ += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(GREEN)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
        t.setStyle(TableStyle(st_))
        return t

    k = kpis(df, exp)
    if "Sales summary" in sections:
        el += [Paragraph("Sales summary", h2), tbl([["Metric", "Value"], ["Total revenue", mny(k["revenue"])],
               ["Orders", f"{k['orders']:,}"], ["Units sold", f"{k['units']:,.0f}"], ["Average order value", mny(k["aov"])],
               ["Discounts given", mny(k["discounts"])]], [8 * cm, 6 * cm]), Spacer(1, 10)]
        mon = df.groupby("month").revenue.sum()
        if len(mon) > 1:
            d = Drawing(440, 180)
            bc = VerticalBarChart()
            bc.x, bc.y, bc.width, bc.height = 40, 30, 380, 130
            bc.data = [list(mon.round(0).values)]
            bc.categoryAxis.categoryNames = [f"{m:%b}" for m in mon.index]
            bc.bars[0].fillColor = colors.HexColor(BLUE)
            bc.valueAxis.labels.fontSize = 7
            bc.categoryAxis.labels.fontSize = 8
            d.add(bc)
            el += [Paragraph("Monthly revenue", ss["Heading4"]), d]
    if "Profit summary" in sections:
        el += [Paragraph("Profit summary", h2), tbl([["Metric", "Value"], ["Revenue", mny(k["revenue"])],
               ["Cost of goods sold", mny(k["cogs"])], ["Gross profit", mny(k["gross"])],
               ["Operating expenses", mny(k["opex"])], ["Net profit", mny(k["net"]) if k["net"] is not None else "n/a (no expenses provided)"],
               ["Net margin", f"{k['net_margin']:.1f}%" if k["net_margin"] is not None else "n/a"]], [8 * cm, 6 * cm]), Spacer(1, 10)]
    if "Top products" in sections:
        pt = product_table(df).head(10)
        rows = [["Product", "Units", "Revenue", "Gross profit", "Margin"]] + [
            [r["product"], f"{r.units:,.0f}", mny(r.revenue), mny(r.profit), "-" if pd.isna(r["margin_%"]) else f"{r['margin_%']:.1f}%"] for _, r in pt.iterrows()]
        el += [Paragraph("Top products", h2), tbl(rows), Spacer(1, 10)]
    if "Notes & recommendations" in sections:
        el.append(Paragraph("Notes & recommendations", h2))
        for _, t in insights(df, exp):
            el.append(Paragraph("• " + t.replace("&", "&amp;").replace("<", "&lt;"), ss["Normal"]))
    doc.build(el)
    return buf.getvalue()


def make_excel(df, exp):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        k = kpis(df, exp)
        pd.DataFrame({"Metric": list(k.keys()), "Value": list(k.values())}).to_excel(w, sheet_name="Summary", index=False)
        df.groupby("month").agg(revenue=("revenue", "sum"), profit=("profit", "sum"), orders=("order_id", "nunique"),
                                units=("quantity", "sum")).reset_index().to_excel(w, sheet_name="Monthly", index=False)
        product_table(df).to_excel(w, sheet_name="Products", index=False)
        df.drop(columns=["month", "day"]).to_excel(w, sheet_name="Clean data", index=False)
        if exp is not None and len(exp):
            exp.drop(columns=["month"]).to_excel(w, sheet_name="Expenses", index=False)
    return buf.getvalue()


# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("## 📊 BizAnalyzer")
    st.caption("Understand your business, not just your numbers.")
    st.radio("Navigation", PAGES, key="nav", label_visibility="collapsed")
    st.divider()
    st.caption("🔒 Your files are processed in memory only and erased when you close the tab.")
    if st.session_state.clean is not None:
        st.button("🗑️ Delete my data now", on_click=delete_cb, key="del_side")
page = st.session_state.nav
has_data = st.session_state.clean is not None

view = exp_v = nodate = None
period_txt = ""
rng = None
if has_data and page not in (PAGES[1], PAGES[8]):
    full = st.session_state.clean
    with st.sidebar:
        st.divider()
        st.markdown("**Filters**")
        dmin, dmax = full.date.min().date(), full.date.max().date()
        dr = st.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
        if isinstance(dr, tuple) and len(dr) == 2:
            rng = (pd.Timestamp(dr[0]), pd.Timestamp(dr[1]))
        else:
            rng = (pd.Timestamp(dmin), pd.Timestamp(dmax))
        prods = st.multiselect("Product", sorted(full["product"].unique()))
        cats = st.multiselect("Category", sorted(full["category"].unique()))
    nodate = full
    if prods:
        nodate = nodate[nodate["product"].isin(prods)]
    if cats:
        nodate = nodate[nodate["category"].isin(cats)]
    view = nodate[(nodate.date >= rng[0]) & (nodate.date < rng[1] + pd.Timedelta(days=1))]
    ex = st.session_state.expenses
    exp_v = ex[(ex.date >= rng[0]) & (ex.date < rng[1] + pd.Timedelta(days=1))] if ex is not None else None
    period_txt = f"{rng[0]:%Y-%m-%d} to {rng[1]:%Y-%m-%d}"

if page not in (PAGES[1], PAGES[8]) and not has_data:
    hero("Welcome to BizAnalyzer", "Upload your sales file to get instant insights - or try it with demo data.")
    st.info("No data loaded yet.")
    st.button("✨ Load demo data", on_click=load_demo, key="demo_welcome")
    st.button("📤 Go to Upload", on_click=lambda: st.session_state.update(nav=PAGES[1]), key="go_up")
    st.stop()

if view is not None and view.empty:
    st.warning("No rows match the current filters.")
    st.stop()

# ----------------------------------------------------------------------------- pages
if page == PAGES[0]:
    hero("Dashboard", f"Period: {period_txt}")
    k = kpis(view, exp_v)
    mon = view.groupby("month").revenue.sum()
    rev_delta = pct(mon.iloc[-1], mon.iloc[-2]) if len(mon) >= 2 else None
    c = st.columns(4)
    with c[0]: kpi("Total Revenue", money(k["revenue"]), "vs previous month" if rev_delta is not None else "", GREEN, rev_delta)
    with c[1]: kpi("Total Costs (COGS)", money(k["cogs"]), "Cost of goods sold", BLUE)
    with c[2]: kpi("Gross Profit", money(k["gross"]), f"Margin {k['gross_margin']:.1f}%" if k["gross_margin"] is not None else "needs unit cost", GREEN)
    with c[3]: kpi("Net Profit", money(k["net"]) if k["net"] is not None else "n/a",
                   f"Net margin {k['net_margin']:.1f}%" if k["net_margin"] is not None else "upload expenses to unlock", BLUE)
    c = st.columns(4)
    with c[0]: kpi("Profit Margin", f"{k['net_margin']:.1f}%" if k["net_margin"] is not None else (f"{k['gross_margin']:.1f}%" if k["gross_margin"] is not None else "n/a"),
                   "net" if k["net_margin"] is not None else "gross", GREEN)
    with c[1]: kpi("Total Orders", f"{k['orders']:,}", "", BLUE)
    with c[2]: kpi("Units Sold", f"{k['units']:,.0f}", "", GREEN)
    with c[3]: kpi("Avg Order Value", money(k["aov"]), "", BLUE)

    st.markdown("#### 🧠 Smart summary")
    for ic, t in insights(view, exp_v)[:5]:
        st.markdown(f'<div class="insight">{ic} {t}</div>', unsafe_allow_html=True)

    a, b = st.columns([3, 2])
    with a:
        m = view.groupby("month").agg(Revenue=("revenue", "sum"), Profit=("profit", "sum")).reset_index()
        f = go.Figure()
        f.add_bar(x=m.month, y=m.Revenue, name="Revenue", marker_color=BLUE)
        if view.profit.notna().any():
            f.add_scatter(x=m.month, y=m.Profit, name="Gross profit", mode="lines+markers", line=dict(color=GREEN, width=3))
        f.update_layout(title="Revenue & profit by month")
        show(f)
    with b:
        cat = view.groupby("category").revenue.sum().reset_index()
        show(px.pie(cat, names="category", values="revenue", hole=.55, title="Sales by category"))
    a, b = st.columns(2)
    with a:
        day = view.groupby("day").revenue.sum().reset_index()
        day["7-day avg"] = day.revenue.rolling(7, min_periods=1).mean()
        f = px.area(day, x="day", y="revenue", title="Daily sales", color_discrete_sequence=[BLUE])
        f.add_scatter(x=day.day, y=day["7-day avg"], name="7-day avg", line=dict(color=GREEN, width=2))
        show(f)
    with b:
        top = product_table(view).head(8).sort_values("revenue")
        show(px.bar(top, x="revenue", y="product", orientation="h", title="Top products by revenue", color_discrete_sequence=[GREEN]))

elif page == PAGES[1]:
    hero("Upload Data", "Excel or CSV. We detect your columns, check quality, and never change data silently.")
    st.info("🔒 **Privacy:** your files are never saved on disk or in a database. They live in memory for your session only "
            "and are erased automatically when you close the tab, or instantly with the “Delete my data now” button.")
    c = st.columns([2, 1, 1])
    with c[0]:
        up = st.file_uploader("Drag & drop your sales file (Excel or CSV)", type=["csv", "xlsx", "xls"])
    with c[1]:
        st.write("")
        st.button("✨ Try demo data", on_click=load_demo, key="demo_up")
    with c[2]:
        st.write("")
        st.download_button("⬇️ Download template", template_xlsx(), "bizanalyzer_template.xlsx")
    if up is not None and up.name != st.session_state.raw_name:
        sheet = None
        if up.name.lower().endswith(("xlsx", "xls")):
            sheets = pd.ExcelFile(up).sheet_names
            sheet = sheets[0]
            up.seek(0)
        try:
            raw = read_any(up, sheet)
            st.session_state.update(raw=raw, raw_name=up.name, mapping=detect(raw.columns, SYN))
        except Exception as e:
            st.error(f"Could not read this file: {e}")
    raw = st.session_state.raw
    if raw is not None and st.session_state.raw_name != "demo":
        st.markdown(f"**{st.session_state.raw_name}**")
        m1, m2 = st.columns(2)
        m1.metric("Rows", f"{len(raw):,}")
        m2.metric("Columns", len(raw.columns))
        table(raw.head(20))
        st.markdown("#### 🔗 Column mapping")
        st.caption("Auto-detected. Change anything that looks wrong.")
        det = detect(raw.columns, SYN)
        opts = ["— none —"] + list(raw.columns)
        mp = {}
        cols = st.columns(3)
        for i, f in enumerate(SYN):
            with cols[i % 3]:
                dflt = opts.index(det[f]) if f in det else 0
                sel = st.selectbox(LABELS[f] + (" *" if f in REQUIRED else ""), opts, index=dflt, key=f"map_{f}_{st.session_state.raw_name}")
                if sel != opts[0]:
                    mp[f] = sel
        st.session_state.mapping = mp
        missing_req = [LABELS[f] for f in REQUIRED if f not in mp]
        o1, o2, o3 = st.columns(3)
        with o1:
            st.selectbox("Discount column is a…", ["Percent (%)", "Amount"], key="opt_disc")
        with o2:
            statuses = sorted(raw[mp["status"]].astype(str).unique()) if "status" in mp else []
            dflt_ex = [s for s in statuses if re.search(r"cancel|return|refund|fail", s.lower())]
            st.multiselect("Exclude order statuses", statuses, default=dflt_ex, key="opt_excl")
        with o3:
            st.checkbox("Remove exact duplicate rows", key="opt_dups")
        if missing_req:
            st.error("Please map the required columns: " + ", ".join(missing_req))
        else:
            _, rep = build_clean(raw, mp, st.session_state.get("opt_disc", "Percent (%)"), st.session_state.get("opt_excl", dflt_ex), st.session_state.get("opt_dups", False))
            st.markdown("#### ✅ Data quality check")
            q = st.columns(4)
            q[0].metric("Valid rows", f"{rep['rows_clean']:,}")
            q[1].metric("Invalid / missing", rep["invalid"])
            q[2].metric("Duplicate rows", rep["duplicates"])
            q[3].metric("Excluded by status", rep["excluded_status"])
            if rep["invalid"]:
                st.warning(f"{rep['invalid']} rows have a bad date, missing product, or invalid quantity/price. They will be left out of the analysis - review them below.")
                with st.expander("Show problem rows"):
                    table(raw.loc[rep["invalid_idx"]])
            if rep["duplicates"] and not st.session_state.get("opt_dups"):
                st.info("Duplicate rows were found but are kept. Tick the box above to remove them.")
            if not rep["has_cost"]:
                st.info("No Unit Cost column mapped: sales analysis will work, profit analysis won't.")
            if not rep["has_orderid"]:
                st.info("No Order ID column: each row will be counted as one order.")
            st.button("🚀 Confirm & Analyze", type="primary", on_click=confirm_cb, disabled=rep["rows_clean"] == 0)

    st.markdown("#### 🧾 Optional files")
    e1, e2 = st.columns(2)
    with e1:
        ef = st.file_uploader("Operating expenses (Date, Expense Category, Amount)", type=["csv", "xlsx", "xls"], key="exp_up")
        if ef is not None:
            er = read_any(ef)
            dm = detect(er.columns, EXP_SYN)
            if all(x in dm for x in ["date", "amount"]):
                st.session_state.expenses = clean_expenses(er, dm)
                st.success(f"{len(st.session_state.expenses)} expense rows loaded - net profit is now available.")
            else:
                st.error("Couldn't find Date and Amount columns.")
    with e2:
        inf = st.file_uploader("Inventory (Product, Current Stock, Reorder Level, Unit Cost)", type=["csv", "xlsx", "xls"], key="inv_up")
        if inf is not None:
            ir = read_any(inf)
            dm = detect(ir.columns, INV_SYN)
            if all(x in dm for x in ["product", "stock"]):
                inv = ir.rename(columns={v: k for k, v in dm.items()})[list(dm.keys())]
                st.session_state.inventory = inv
                st.success(f"{len(inv)} products loaded.")
            else:
                st.error("Couldn't find Product and Stock columns.")

elif page == PAGES[2]:
    hero("Sales Analysis", f"Period: {period_txt}")
    k = kpis(view, exp_v)
    c = st.columns(3)
    with c[0]: kpi("Total Sales", money(k["revenue"]))
    with c[1]: kpi("Orders", f"{k['orders']:,}", color=BLUE)
    with c[2]: kpi("Avg Order Value", money(k["aov"]))
    t1, t2, t3 = st.tabs(["Daily", "Weekly", "Monthly"])
    s = view.set_index("date").revenue
    for tab, rule, name in [(t1, "D", "Daily"), (t2, "W", "Weekly"), (t3, "MS", "Monthly")]:
        with tab:
            r = s.resample(rule).sum().reset_index()
            r.columns = ["Period", "Revenue"]
            f = px.line(r, x="Period", y="Revenue", markers=name != "Daily", title=f"{name} sales", color_discrete_sequence=[BLUE])
            f.update_traces(fill="tozeroy", fillcolor="rgba(28,126,214,.12)")
            show(f)
            if name == "Monthly":
                r["Change %"] = r.Revenue.pct_change() * 100
                table(r.assign(Period=r.Period.dt.strftime("%B %Y")).round(1))
    st.markdown("#### 🔁 Period comparison")
    n = (rng[1] - rng[0]).days + 1
    ps, pe = rng[0] - pd.Timedelta(days=n), rng[0] - pd.Timedelta(days=1)
    prev = nodate[(nodate.date >= ps) & (nodate.date < pe + pd.Timedelta(days=1))]
    if prev.empty:
        st.info("No data before the selected range to compare with.")
    else:
        kp = kpis(prev, None)
        c = st.columns(3)
        with c[0]: kpi("Revenue", money(k["revenue"]), f"previous: {money(kp['revenue'])}", GREEN, pct(k["revenue"], kp["revenue"]))
        with c[1]: kpi("Orders", f"{k['orders']:,}", f"previous: {kp['orders']:,}", BLUE, pct(k["orders"], kp["orders"]))
        with c[2]: kpi("Avg Order Value", money(k["aov"]), f"previous: {money(kp['aov'])}", GREEN, pct(k["aov"], kp["aov"]))
        st.caption(f"Compared with {ps:%Y-%m-%d} to {pe:%Y-%m-%d}.")
    a, b = st.columns(2)
    with a:
        p = view.groupby("product").revenue.sum().sort_values().reset_index()
        show(px.bar(p, x="revenue", y="product", orientation="h", title="Sales by product", color_discrete_sequence=[GREEN]))
    with b:
        p = view.groupby("category").revenue.sum().sort_values().reset_index()
        show(px.bar(p, x="revenue", y="category", orientation="h", title="Sales by category", color_discrete_sequence=[BLUE]))
    wd = view.groupby("weekday").revenue.sum().reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]).reset_index()
    show(px.bar(wd, x="weekday", y="revenue", title="Sales by day of week", color_discrete_sequence=[GREEN]), 300)

elif page == PAGES[3]:
    hero("Profit & Financial Analysis", f"Period: {period_txt}")
    k = kpis(view, exp_v)
    if k["gross"] is None:
        st.warning("Profit analysis needs a Unit Cost column. Go to Upload Data and map it.")
        st.stop()
    c = st.columns(3)
    with c[0]: kpi("Revenue", money(k["revenue"]))
    with c[1]: kpi("Cost of Goods Sold", money(k["cogs"]), color=BLUE)
    with c[2]: kpi("Gross Profit", money(k["gross"]), f"Margin {k['gross_margin']:.1f}%")
    c = st.columns(3)
    with c[0]: kpi("Operating Expenses", money(k["opex"]) if k["opex"] is not None else "not provided", color=BLUE)
    with c[1]: kpi("Net Profit", money(k["net"]) if k["net"] is not None else "n/a", "confirmed" if k["net"] is not None else "needs expenses file")
    with c[2]: kpi("Net Margin", f"{k['net_margin']:.1f}%" if k["net_margin"] is not None else "n/a", color=BLUE)
    if k["net"] is None:
        st.info("No operating expenses provided, so Net Profit is not shown (we won't present gross profit as net profit). Upload an expenses file in Upload Data.")
    if k["net"] is not None and view.cogs.isna().any():
        st.warning("Some rows have no unit cost, so profit is calculated on the rows that do.")
    steps = [("Revenue", k["revenue"], "absolute"), ("COGS", -k["cogs"], "relative"), ("Gross profit", k["gross"], "total")]
    if k["net"] is not None:
        steps += [("Operating expenses", -k["opex"], "relative"), ("Net profit", k["net"], "total")]
    f = go.Figure(go.Waterfall(x=[s[0] for s in steps], y=[s[1] for s in steps], measure=[s[2] for s in steps],
                               increasing_marker_color=GREEN, decreasing_marker_color="#E03131", totals_marker_color=BLUE))
    f.update_layout(title="From revenue to profit")
    show(f)
    a, b = st.columns([3, 2])
    with a:
        m = view.groupby("month").agg(revenue=("revenue", "sum"), gross=("profit", "sum")).reset_index()
        if exp_v is not None and len(exp_v):
            m = m.merge(exp_v.groupby("month").amount.sum().rename("expenses").reset_index(), on="month", how="left").fillna({"expenses": 0})
            m["net"] = m.gross - m.expenses
        f = go.Figure()
        f.add_bar(x=m.month, y=m.gross, name="Gross profit", marker_color=GREEN)
        if "net" in m:
            f.add_scatter(x=m.month, y=m.net, name="Net profit", mode="lines+markers", line=dict(color=BLUE, width=3))
        f.update_layout(title="Profit by month")
        show(f)
    with b:
        if exp_v is not None and len(exp_v):
            show(px.pie(exp_v.groupby("category").amount.sum().reset_index(), names="category", values="amount", hole=.55, title="Operating expenses"))
        else:
            st.info("Expense breakdown appears here once you upload expenses.")
    st.caption("Revenue = Σ(quantity × price) − discounts · Gross profit = Revenue − COGS · Net profit = Gross profit − operating expenses")

elif page == PAGES[4]:
    hero("Product Analysis", "Which products make you money?")
    pt = product_table(view)
    has_p = pt.profit.notna().any()
    a, b = st.columns(2)
    with a:
        st.markdown("##### 🏆 Best-selling (units)")
        table(pt.sort_values("units", ascending=False).head(5)[["product", "units", "revenue"]].round(0))
        if has_p:
            st.markdown("##### 💎 Most profitable")
            table(pt.sort_values("profit", ascending=False).head(5)[["product", "profit", "margin_%"]].round(1))
    with b:
        st.markdown("##### 🐢 Worst-selling (units)")
        table(pt.sort_values("units").head(5)[["product", "units", "revenue"]].round(0))
        if has_p:
            st.markdown("##### 📉 Least profitable")
            table(pt.sort_values("profit").head(5)[["product", "profit", "margin_%"]].round(1))
    if has_p:
        pp = pt.dropna(subset=["profit"])
        f = px.scatter(pp, x="units", y="margin_%", size="revenue", color="category", text="product",
                       title="Volume vs margin (bubble = revenue)")
        f.update_traces(textposition="top center")
        f.add_hline(y=pp.profit.sum() / pp.revenue.sum() * 100, line_dash="dot", annotation_text="average margin")
        show(f, 460)
    st.markdown("##### Full product table")
    table(pt.round(1), column_config={"margin_%": st.column_config.ProgressColumn("Margin %", min_value=0, max_value=100, format="%.0f%%")} if has_p else None)
    st.markdown("##### Notes")
    for ic, t in insights(view, exp_v):
        if ic in ("💎", "📦", "💰", "⚠️", "🌱"):
            st.markdown(f'<div class="insight">{ic} {t}</div>', unsafe_allow_html=True)

elif page == PAGES[5]:
    hero("Inventory Analysis", "Optional - needs an inventory file (Product, Current Stock, Reorder Level, Unit Cost).")
    inv = st.session_state.inventory
    if inv is None:
        st.info("No inventory data yet. Upload it in Upload Data, or load the demo data.")
        st.stop()
    inv = inv.copy()
    thr = st.session_state.low_stock
    if "reorder" not in inv:
        inv["reorder"] = thr
    inv["reorder"] = inv["reorder"].fillna(thr)
    recent = nodate[nodate.date >= nodate.date.max() - pd.Timedelta(days=30)]
    vel = recent.groupby("product").quantity.sum() / 30
    inv["daily_sales"] = inv["product"].map(vel).fillna(0)
    inv["days_left"] = np.where(inv.daily_sales > 0, inv.stock / inv.daily_sales, np.nan)
    inv["status"] = np.select([inv.stock <= 0, inv.stock <= inv.reorder], ["Out of Stock", "Low Stock"], "Healthy")
    if "unit_cost" not in inv:
        inv["unit_cost"] = inv["product"].map(nodate.groupby("product").cost.mean())
    inv["stock_value"] = inv.stock * inv.unit_cost
    c = st.columns(4)
    with c[0]: kpi("Products tracked", f"{len(inv)}")
    with c[1]: kpi("Low stock", f"{(inv.status == 'Low Stock').sum()}", color="#F59F00")
    with c[2]: kpi("Out of stock", f"{(inv.status == 'Out of Stock').sum()}", color="#E03131")
    with c[3]: kpi("Stock value", money(inv.stock_value.sum()), color=BLUE)
    need = inv[(inv.status != "Healthy") | (inv.days_left < 14)]
    if len(need):
        st.markdown("#### 🔔 Needs restocking")
        for _, r in need.iterrows():
            dl = f", about {r.days_left:.0f} days of stock left at the last-30-day pace" if pd.notna(r.days_left) else ""
            st.markdown(f'<div class="insight">⚠️ <b>{r["product"]}</b>: {r.stock:.0f} units ({r.status}){dl}.</div>', unsafe_allow_html=True)
    f = go.Figure()
    f.add_bar(x=inv["product"], y=inv.stock, name="Stock", marker_color=GREEN)
    f.add_scatter(x=inv["product"], y=inv.reorder, name="Reorder level", mode="markers", marker=dict(color="#E03131", size=11, symbol="line-ew-open", line=dict(width=3)))
    f.update_layout(title="Stock vs reorder level")
    show(f)
    table(inv.round(1), column_config={"stock": st.column_config.ProgressColumn("Stock", min_value=0, max_value=float(max(inv.stock.max(), 1)), format="%.0f")})

elif page == PAGES[6]:
    hero("Smart Insights", "Every sentence below is computed from your real numbers - nothing is guessed.")
    for ic, t in insights(view, exp_v):
        st.markdown(f'<div class="insight">{ic} {t}</div>', unsafe_allow_html=True)
    st.markdown("#### 💬 Ask your data")
    sugg = ["Which product generated the highest profit?", "Why did my sales decrease?",
            "Which month had the highest revenue?", "What should I investigate next?"]
    q = st.selectbox("Pick a question", sugg)
    free = st.text_input("…or type your own (profit, revenue, month, why, investigate)")
    st.markdown(answer(free or q, view, exp_v))

elif page == PAGES[7]:
    hero("Reports", "Export a professional report for the selected period.")
    st.caption(f"Period: {period_txt} (change it with the date filter in the sidebar)")
    secs = st.multiselect("Include in PDF", ["Sales summary", "Profit summary", "Top products", "Notes & recommendations"],
                          default=["Sales summary", "Profit summary", "Top products", "Notes & recommendations"])
    c = st.columns(3)
    with c[0]:
        st.download_button("📄 Download PDF", make_pdf(view, exp_v, period_txt, secs), "bizanalyzer_report.pdf", mime="application/pdf")
    with c[1]:
        st.download_button("📊 Download Excel", make_excel(view, exp_v), "bizanalyzer_report.xlsx")
    with c[2]:
        st.download_button("🧾 Download CSV", view.drop(columns=["month", "day"]).to_csv(index=False).encode("utf-8"), "bizanalyzer_clean_data.csv", mime="text/csv")

elif page == PAGES[8]:
    hero("Settings", "Currency, thresholds, history and your data.")
    c = st.columns(2)
    with c[0]:
        st.selectbox("Currency", ["DH", "EUR", "USD"], key="currency")
        st.caption("Label only - amounts are not converted.")
    with c[1]:
        st.number_input("Default low-stock threshold", 0, 10000, key="low_stock")
    st.markdown("#### 🕘 Analysis history")
    if st.session_state.history:
        table(pd.DataFrame(st.session_state.history[::-1]))
    else:
        st.caption("Nothing yet.")
    st.markdown("#### 🗑️ Your data")
    st.button("Delete uploaded files & analysis", on_click=delete_cb)
    st.caption("Data lives only in your session memory and disappears when you close the tab.")
