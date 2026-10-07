"""
Synthetic extracts for a 20-store home-goods chain ("Harbor & Pine Home").

What gets simulated, week by week for every store x SKU:
  demand   lognormal base rate per SKU, store size multiplier, category
           seasonality (garden peaks in May, bedding in Nov-Jan), promo weeks
  supply   each store re-orders when stock drops below a rough reorder point;
           suppliers have their own lead times, lateness and fill rates
  sales    units sold = min(demand, stock available); the shortfall becomes
           days out of stock for the week

A few problems are planted: two suppliers that ship late and short, an
over-bought outdoor range in the spring, and some products that were ordered
for every store but only sell in the flagships.

The raw product master is deliberately a bit messy (inconsistent category
casing, prices stored as text with a currency sign) so the Power Query layer
has some real cleaning to do.

Usage:  python generate_data.py <output folder>
"""
import os, sys
import numpy as np
import pandas as pd

out = sys.argv[1] if len(sys.argv) > 1 else "."
rng = np.random.default_rng(11)

stores = pd.DataFrame([
    ("ST01", "Portland Pearl", "West", "Flagship", 32000), ("ST02", "Seattle Ballard", "West", "Standard", 21000),
    ("ST03", "Boise Downtown", "West", "Standard", 18000), ("ST04", "Sacramento Midtown", "West", "Standard", 19500),
    ("ST05", "Reno Meadowood", "West", "Outlet", 14000), ("ST06", "Denver Cherry Creek", "Mountain", "Flagship", 30000),
    ("ST07", "Boulder Pearl St", "Mountain", "Standard", 16500), ("ST08", "Salt Lake Sugar House", "Mountain", "Standard", 20000),
    ("ST09", "Phoenix Biltmore", "Mountain", "Standard", 22000), ("ST10", "Albuquerque Nob Hill", "Mountain", "Outlet", 13000),
    ("ST11", "Austin Domain", "South", "Flagship", 31000), ("ST12", "Dallas Uptown", "South", "Standard", 23000),
    ("ST13", "Houston Heights", "South", "Standard", 22500), ("ST14", "San Antonio Pearl", "South", "Standard", 18500),
    ("ST15", "Nashville 12South", "South", "Standard", 17500), ("ST16", "Chicago Lincoln Park", "Midwest", "Flagship", 33000),
    ("ST17", "Minneapolis North Loop", "Midwest", "Standard", 20500), ("ST18", "Madison State St", "Midwest", "Standard", 15500),
    ("ST19", "Columbus Short North", "Midwest", "Standard", 19000), ("ST20", "Kansas City Crossroads", "Midwest", "Outlet", 12500)],
    columns=["StoreID", "StoreName", "Region", "Format", "SalesFloorSqFt"])

cats = {"Kitchen": (["Skillet", "Chef Knife", "Cutting Board", "Mixing Bowl Set", "Dutch Oven", "Utensil Crock", "Spice Rack", "Colander"], 18, 140),
        "Tableware": (["Dinner Plate Set", "Stoneware Mug", "Wine Glass Pair", "Serving Platter", "Linen Napkins", "Flatware Set"], 12, 95),
        "Bedding": (["Percale Sheet Set", "Duvet Cover", "Down Alternative Pillow", "Quilt", "Weighted Blanket", "Mattress Topper"], 35, 220),
        "Bath": (["Bath Towel", "Bath Mat", "Shower Curtain", "Waffle Robe", "Soap Dispenser"], 10, 85),
        "Decor": (["Table Lamp", "Throw Pillow", "Wall Mirror", "Ceramic Vase", "Picture Frame", "Scented Candle", "Wool Throw"], 14, 180),
        "Storage": (["Woven Basket", "Shelf Unit", "Shoe Rack", "Storage Bin Set", "Coat Hooks"], 15, 150),
        "Outdoor": (["Patio Lantern", "Planter Pot", "Outdoor Cushion", "String Lights", "Bistro Chair", "Garden Tool Set"], 16, 160)}
finishes = ["Oak", "Slate", "Linen", "Sage", "Ivory", "Charcoal", "Terracotta", "Navy", "Walnut", "Sand"]
suppliers = {"Kitchen": ["Ridgeline Cookware", "Copperleaf Supply"], "Tableware": ["Copperleaf Supply", "Northbay Ceramics"],
             "Bedding": ["Loomhouse Textiles", "Cotton Ridge Mills"], "Bath": ["Loomhouse Textiles", "Cotton Ridge Mills"],
             "Decor": ["Brightwater Imports", "Northbay Ceramics"], "Storage": ["Pacific Homewares", "Brightwater Imports"],
             "Outdoor": ["Sunfield Outdoor", "Pacific Homewares"]}
sup_profile = {  # lead weeks, late prob, fill rate
    "Ridgeline Cookware": (3, 0.08, 0.98), "Copperleaf Supply": (2, 0.10, 0.97), "Northbay Ceramics": (4, 0.12, 0.96),
    "Loomhouse Textiles": (5, 0.55, 0.78), "Cotton Ridge Mills": (3, 0.09, 0.98), "Brightwater Imports": (6, 0.5, 0.8),
    "Pacific Homewares": (3, 0.07, 0.97), "Sunfield Outdoor": (4, 0.12, 0.95)}

prods = []
n = 0
for cat, (items, lo, hi) in cats.items():
    for item in items:
        for f in rng.choice(finishes, size=int(rng.integers(4, 7)), replace=False):
            n += 1
            price = round(float(np.exp(rng.uniform(np.log(lo), np.log(hi)))), 0) - 0.01
            cost = round(price * rng.uniform(0.38, 0.55), 2)
            sup = rng.choice(suppliers[cat])
            raw_cat = cat if rng.random() > 0.15 else rng.choice([cat.lower(), cat.upper(), cat + " "])
            prods.append(dict(SKU=f"HP-{10000 + n}", ProductName=f"{f} {item}", Category=raw_cat, Supplier=sup,
                              UnitCost=f"${cost:,.2f}", RetailPrice=f"${price:,.2f}", CasePack=int(rng.choice([1, 2, 4, 6, 12])),
                              LeadTimeDays=sup_profile[sup][0] * 7, Status="Active" if rng.random() > 0.03 else "Discontinued"))
products = pd.DataFrame(prods)
P, S = len(products), len(stores)
price = products.RetailPrice.str.replace("[$,]", "", regex=True).astype(float).values
cost = products.UnitCost.str.replace("[$,]", "", regex=True).astype(float).values
cat_clean = products.Category.str.strip().str.title().values

weeks = pd.date_range("2025-10-04", periods=52, freq="W-SAT")
season = {"Outdoor": lambda m: 0.35 + 1.4 * np.exp(-((m - 5.5) ** 2) / 3.0),
          "Bedding": lambda m: 1 + 0.45 * np.cos((m - 12) / 12 * 2 * np.pi),
          "Decor": lambda m: 1 + 0.35 * np.exp(-((m - 11.8) ** 2) / 1.2)}
base = np.exp(rng.normal(0.6, 0.9, P)) * (60 / price) ** 0.45
store_mult = (stores.SalesFloorSqFt.values / 20000) ** 1.1 * np.where(stores.Format.values == "Outlet", 0.8, 1.0)
flag_only = rng.random(P) < 0.08  # sells well only in flagships
dem_rate = base[None, :] * store_mult[:, None]
dem_rate[:, flag_only] *= np.where(stores.Format.values == "Flagship", 1.6, 0.18)[:, None]

lead = np.array([sup_profile[s][0] for s in products.Supplier])
late_p = np.array([sup_profile[s][1] for s in products.Supplier])
fill = np.array([sup_profile[s][2] for s in products.Supplier])
pack = products.CasePack.values

stock = np.ceil(dem_rate * rng.uniform(5, 8, (S, P)))
overbuy = (cat_clean == "Outdoor") & (rng.random(P) < 0.5)
pipeline = []  # (arrival_week, s, p, qty, po_index)
pos = []
rows = []
for w, wk in enumerate(weeks):
    m = wk.month + wk.day / 31
    seas = np.array([season.get(c, lambda m: 1.0)(m) for c in cat_clean])
    promo = (rng.random(P) < 0.04) * rng.uniform(0.4, 1.2, P)
    lam = dem_rate * seas[None, :] * (1 + promo)[None, :] * (1 + 0.05 * np.sin(w / 3))
    demand = rng.poisson(lam * rng.gamma(3.0, 1 / 3.0, lam.shape))
    receipts = np.zeros((S, P))
    keep = []
    for a in pipeline:
        if a[0] == w:
            receipts[a[1], a[2]] += a[3]
            pos[a[4]]["ReceivedDate"] = (wk - pd.Timedelta(days=int(rng.integers(0, 6)))).date()
        else:
            keep.append(a)
    pipeline = keep
    avail = stock + receipts
    sold = np.minimum(demand, avail)
    short = demand - sold
    oos_days = np.where(short > 0, np.clip(np.round(7 * short / np.maximum(demand, 1)), 1, 7), 0)
    stock = avail - sold
    # replenishment decision for next weeks
    on_order = np.zeros((S, P))
    for a in pipeline:
        on_order[a[1], a[2]] += a[3]
    exp_d = lam * 1.05
    rop = exp_d * (lead + 1) + 0.35 * np.sqrt(exp_d * (lead + 1)) + np.ceil(exp_d * 2.5)  # presentation stock
    need = (stock + on_order < rop) & (products.Status.values == "Active")[None, :]
    if w in (20, 21, 22):  # spring buy of outdoor goes in heavy
        need[:, overbuy] = True
    si, pi = np.nonzero(need)
    for s_, p_ in zip(si, pi):
        target = rop[s_, p_] + exp_d[s_, p_] * 1.5
        if w in (20, 21, 22) and overbuy[p_]:
            target = exp_d[s_, p_] * 40
        qty = int(np.ceil(max(target - stock[s_, p_] - on_order[s_, p_], pack[p_]) / pack[p_]) * pack[p_])
        late = int(rng.random() < late_p[p_]) * int(rng.integers(1, 5))
        recv = qty if rng.random() < fill[p_] else int(qty * rng.uniform(0.5, 0.95))
        arrive = w + 1 + lead[p_] + late
        pos.append(dict(PONumber=f"PO{260000 + len(pos)}", StoreID=stores.StoreID[s_], SKU=products.SKU[p_],
                        Supplier=products.Supplier[p_], OrderDate=(wk + pd.Timedelta(days=2)).date(),
                        ExpectedDate=(wk + pd.Timedelta(days=int(lead[p_]) * 7 + 7)).date(), ReceivedDate=None,
                        OrderedQty=qty, ReceivedQty=recv))
        if arrive < len(weeks):
            pipeline.append((arrive, s_, p_, recv, len(pos) - 1))
        else:
            pos[-1]["ReceivedQty"] = None
    for s_ in range(S):
        active = (products.Status.values == "Active")
        sel = (sold[s_] > 0) | (stock[s_] > 0) | (receipts[s_] > 0) | ((oos_days[s_] > 0) & active)
        for p_ in np.nonzero(sel)[0]:
            disc = 0.7 if (overbuy[p_] and w > 40) else 1.0
            rows.append((wk.date(), stores.StoreID[s_], products.SKU[p_], int(sold[s_, p_]),
                         round(sold[s_, p_] * price[p_] * disc * rng.uniform(0.93, 1.0), 2),
                         int(receipts[s_, p_]), int(stock[s_, p_]), int(oos_days[s_, p_])))

weekly = pd.DataFrame(rows, columns=["WeekEnding", "StoreID", "SKU", "UnitsSold", "NetSales", "ReceiptsUnits",
                                     "ClosingStockUnits", "DaysOutOfStock"])
po = pd.DataFrame(pos)
os.makedirs(out, exist_ok=True)
stores.to_csv(os.path.join(out, "stores.csv"), index=False)
products.to_csv(os.path.join(out, "products.csv"), index=False)
weekly.to_csv(os.path.join(out, "weekly_store_sku.csv"), index=False)
po.to_csv(os.path.join(out, "purchase_orders.csv"), index=False)
print(P, len(weekly), len(po))
