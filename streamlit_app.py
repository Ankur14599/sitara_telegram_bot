import os

from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
import pymongo
import streamlit as st

from app.core.security import verify_password
from app.services.trend_service import TrendService


load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB_NAME", "smallbiz_bot")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")

st.set_page_config(page_title="Sitara Admin", page_icon="*", layout="wide")


def inject_css():
    st.markdown(
        """
        <style>
        .stApp { background: #f8fafc; color: #111827; }
        [data-testid="stSidebar"] { background: #111827; }
        [data-testid="stSidebar"] * { color: #f9fafb; }
        .auth-wrap {
            max-width: 440px;
            margin: 9vh auto 2rem auto;
            padding: 2rem;
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
        }
        .auth-title { font-size: 2rem; font-weight: 800; margin-bottom: .25rem; }
        .auth-copy { color: #64748b; margin-bottom: 1.5rem; }
        .metric-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 1rem;
        }
        .metric-label { color: #64748b; font-size: .85rem; }
        .metric-value { font-size: 1.65rem; font-weight: 800; color: #111827; }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_css()


def require_login():
    if st.session_state.get("authenticated"):
        return

    st.markdown(
        """
        <div class="auth-wrap">
            <div class="auth-title">Sitara Admin</div>
            <div class="auth-copy">Secure business analytics for orders, customers, inventory, and trends.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not ADMIN_USERNAME or not ADMIN_PASSWORD_HASH:
        st.error("Admin credentials are not configured.")
        st.stop()

    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        with st.form("admin_login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)

        if submitted:
            if username == ADMIN_USERNAME and verify_password(password, ADMIN_PASSWORD_HASH):
                st.session_state["authenticated"] = True
                st.rerun()
            st.error("Invalid username or password.")

    st.stop()


require_login()


@st.cache_resource
def init_connection():
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    return client


client = init_connection()
db = client[DB_NAME]


@st.cache_data(ttl=60)
def load_data():
    businesses = list(db.businesses.find())
    orders = list(db.orders.find())
    inventory = list(db.inventory.find())
    customers = list(db.customers.find())
    return businesses, orders, inventory, customers


@st.cache_data(ttl=60)
def load_trends(business_id, days):
    since = TrendService.since(days)
    query_business_id = business_id if business_id != "All" else None

    if query_business_id is None:
        base_match = {"created_at": {"$gte": since}}
        item_pipeline = TrendService.top_items_pipeline(0, since, 12)
        customer_pipeline = TrendService.top_customers_pipeline(0, since, 12)
        status_pipeline = TrendService.status_pipeline(0, since)
        daily_pipeline = TrendService.daily_orders_pipeline(0, since)
        for pipeline in (item_pipeline, customer_pipeline, status_pipeline, daily_pipeline):
            pipeline[0]["$match"] = base_match
    else:
        item_pipeline = TrendService.top_items_pipeline(query_business_id, since, 12)
        customer_pipeline = TrendService.top_customers_pipeline(query_business_id, since, 12)
        status_pipeline = TrendService.status_pipeline(query_business_id, since)
        daily_pipeline = TrendService.daily_orders_pipeline(query_business_id, since)

    return {
        "top_items": list(db.orders.aggregate(item_pipeline)),
        "top_customers": list(db.orders.aggregate(customer_pipeline)),
        "statuses": list(db.orders.aggregate(status_pipeline)),
        "daily_orders": list(db.orders.aggregate(daily_pipeline)),
    }


def filter_records(records, business_id):
    if business_id == "All":
        return records
    return [record for record in records if record.get("business_id") == business_id]


def metric_card(label, value):
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def money(value):
    return f"Rs. {float(value or 0):,.2f}"


businesses, orders, inventory, customers = load_data()

st.sidebar.title("Sitara")
st.sidebar.caption("Admin dashboard")
if st.sidebar.button("Sign out", use_container_width=True):
    st.session_state.clear()
    st.rerun()

business_options = {"All": "All Businesses"}
business_options.update(
    {
        b.get("telegram_user_id"): f"{b.get('business_name', 'Unknown')} ({b.get('telegram_user_id')})"
        for b in businesses
    }
)

selected_business = st.sidebar.selectbox(
    "Business",
    options=list(business_options.keys()),
    format_func=lambda key: business_options[key],
)
days = st.sidebar.selectbox("Trend window", options=[7, 30, 90], index=1)

orders_view = filter_records(orders, selected_business)
inventory_view = filter_records(inventory, selected_business)
customers_view = filter_records(customers, selected_business)
trends = load_trends(selected_business, days)

st.title("Sitara Admin Dashboard")
st.caption(f"Live overview for {business_options[selected_business]}")

total_revenue = sum(float(order.get("total_amount", 0) or 0) for order in orders_view if order.get("status") != "cancelled")
active_orders = len([order for order in orders_view if order.get("status") not in ("completed", "cancelled")])
low_stock = [
    item for item in inventory_view
    if float(item.get("quantity", 0) or 0) <= float(item.get("low_stock_threshold", 0) or 0)
]

col1, col2, col3, col4 = st.columns(4)
with col1:
    metric_card("Orders", len(orders_view))
with col2:
    metric_card("Active Orders", active_orders)
with col3:
    metric_card("Revenue", money(total_revenue))
with col4:
    metric_card("Low Stock", len(low_stock))

tab_overview, tab_orders, tab_customers, tab_inventory, tab_trends, tab_businesses = st.tabs(
    ["Overview", "Orders", "Customers", "Inventory", "Trends", "Businesses"]
)

with tab_overview:
    left, right = st.columns(2)
    with left:
        st.subheader("Order Status")
        if trends["statuses"]:
            df_status = pd.DataFrame(trends["statuses"]).rename(columns={"_id": "status"})
            st.plotly_chart(
                px.pie(df_status, names="status", values="count", hole=0.45),
                use_container_width=True,
            )
        else:
            st.info("No order status data yet.")

    with right:
        st.subheader("Orders Over Time")
        if trends["daily_orders"]:
            df_daily = pd.DataFrame(trends["daily_orders"]).rename(columns={"_id": "date"})
            st.plotly_chart(
                px.line(df_daily, x="date", y="orders", markers=True),
                use_container_width=True,
            )
        else:
            st.info("No daily order trend yet.")

with tab_orders:
    st.subheader("Manage Orders")
    
    # ── Create Order ──────────────────────────────────────────────────
    with st.expander("➕ Add New Manual Order"):
        with st.form("create_order_form"):
            new_biz_id = st.number_input("Business ID", value=selected_business if selected_business != "All" else 0, min_value=0)
            new_customer = st.text_input("Customer Name")
            new_total = st.number_input("Total Amount", min_value=0.0, step=0.01)
            create_submitted = st.form_submit_button("Create Order", use_container_width=True)
            
            if create_submitted:
                if not new_customer:
                    st.error("Customer name is required.")
                elif new_biz_id == 0:
                    st.error("Valid Business ID is required.")
                else:
                    from app.services.order_service import OrderService
                    import asyncio
                    
                    # Since Streamlit is sync, we need a small helper to run async
                    def run_async(coro):
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        return loop.run_until_complete(coro)

                    svc = OrderService(new_biz_id)
                    run_async(svc.create_order(customer_name=new_customer, items=[]))
                    
                    if new_total > 0:
                        db.orders.update_one(
                            {"business_id": new_biz_id, "customer_name": new_customer},
                            {"$set": {"total_amount": new_total}},
                            sort=[("created_at", -1)]
                        )
                    
                    st.success(f"Order created for {new_customer}!")
                    st.cache_data.clear()
                    st.rerun()

    # ── List / Update / Delete ────────────────────────────────────────
    if orders_view:
        df_orders = pd.DataFrame(orders_view)
        # Sort by creation date descending
        df_orders = df_orders.sort_values(by="created_at", ascending=False)
        
        for _, row in df_orders.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                order_num = row.get('order_number')
                biz_id = row.get('business_id')
                
                with c1:
                    st.markdown(f"**{order_num}**")
                    st.caption(f"Business: {biz_id}")
                with c2:
                    st.text(row.get('customer_name'))
                    st.text(money(row.get('total_amount')))
                with c3:
                    current_status = row.get('status', 'pending')
                    status_options = ["pending", "in_progress", "ready", "completed", "cancelled"]
                    new_status = st.selectbox(
                        "Status", 
                        options=status_options, 
                        index=status_options.index(current_status),
                        key=f"status_{order_num}",
                        label_visibility="collapsed"
                    )
                    if new_status != current_status:
                        db.orders.update_one(
                            {"order_number": order_num, "business_id": biz_id},
                            {"$set": {"status": new_status}}
                        )
                        st.cache_data.clear()
                        st.rerun()
                with c4:
                    if st.button("🗑️", key=f"del_{order_num}", type="secondary", help="Delete Order"):
                        db.orders.delete_one({"order_number": order_num, "business_id": biz_id})
                        st.success(f"Deleted {order_num}")
                        st.cache_data.clear()
                        st.rerun()
    else:
        st.info("No orders found.")

with tab_trends:
    left, right = st.columns(2)
    with left:
        st.subheader(f"Most Ordered Items ({days} days)")
        if trends["top_items"]:
            df_items = pd.DataFrame(trends["top_items"])
            st.plotly_chart(
                px.bar(df_items, x="item", y="quantity", hover_data=["orders", "revenue"]),
                use_container_width=True,
            )
            st.dataframe(df_items[["item", "quantity", "orders", "revenue"]], use_container_width=True)
        else:
            st.info("No item trend data yet.")

    with right:
        st.subheader(f"Top Customers ({days} days)")
        if trends["top_customers"]:
            df_top_customers = pd.DataFrame(trends["top_customers"])
            st.plotly_chart(
                px.bar(df_top_customers, x="customer", y="orders", hover_data=["revenue"]),
                use_container_width=True,
            )
            st.dataframe(df_top_customers[["customer", "orders", "revenue", "last_order"]], use_container_width=True)
        else:
            st.info("No customer trend data yet.")

with tab_customers:
    st.subheader("Customer Management")
    
    # ── Create Customer ───────────────────────────────────────────────
    with st.expander("👤 Add New Customer"):
        with st.form("create_customer_form"):
            c_biz_id = st.number_input("Business ID", value=selected_business if selected_business != "All" else 0, min_value=0, key="cust_biz_id")
            c_name = st.text_input("Customer Name")
            c_phone = st.text_input("Phone (Optional)")
            c_submitted = st.form_submit_button("Add Customer", use_container_width=True)
            
            if c_submitted:
                if not c_name or c_biz_id == 0:
                    st.error("Name and Business ID are required.")
                else:
                    from app.services.customer_service import CustomerService
                    import asyncio
                    
                    def run_async(coro):
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        return loop.run_until_complete(coro)

                    svc = CustomerService(c_biz_id)
                    run_async(svc.find_or_create(c_name))
                    if c_phone:
                        db.customers.update_one(
                            {"business_id": c_biz_id, "name": c_name},
                            {"$set": {"phone": c_phone}}
                        )
                    st.success(f"Customer {c_name} added!")
                    st.cache_data.clear()
                    st.rerun()

    # ── List / Delete ─────────────────────────────────────────────────
    if customers_view:
        df_customers = pd.DataFrame(customers_view)
        # Handle cases where some columns might be missing
        display_cols = ["name", "total_orders", "total_spent", "last_order_date"]
        df_customers = df_customers[[c for c in display_cols if c in df_customers.columns]]
        
        for _, row in df_customers.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                name = row.get('name')
                
                with c1:
                    st.markdown(f"**{name}**")
                    st.caption(f"Orders: {row.get('total_orders', 0)} | Spent: {money(row.get('total_spent', 0))}")
                with c2:
                    st.caption(f"Last Order: {row.get('last_order_date', 'Never')}")
                with c3:
                    if st.button("🗑️", key=f"del_cust_{name}_{selected_business}", help="Delete Customer"):
                        db.customers.delete_one({"name": name, "business_id": selected_business if selected_business != "All" else row.get('business_id')})
                        st.success(f"Deleted {name}")
                        st.cache_data.clear()
                        st.rerun()
    else:
        st.info("No customers found.")

with tab_inventory:
    st.subheader("Inventory Health")
    if low_stock:
        st.warning(f"{len(low_stock)} items are at or below threshold.")
        st.dataframe(pd.DataFrame(low_stock), use_container_width=True)
    elif inventory_view:
        st.success("All inventory items are above threshold.")

    if inventory_view:
        df_inventory = pd.DataFrame(inventory_view)
        if {"name", "quantity"}.issubset(df_inventory.columns):
            st.plotly_chart(
                px.bar(
                    df_inventory.sort_values(by="quantity", ascending=False).head(15),
                    x="name",
                    y="quantity",
                    color="unit" if "unit" in df_inventory.columns else None,
                ),
                use_container_width=True,
            )
        st.dataframe(df_inventory, use_container_width=True)
    else:
        st.info("No inventory items yet.")

with tab_businesses:
    st.subheader("Business Management")
    st.caption("Admin only: Manage and block business accounts.")
    
    for biz in businesses:
        with st.container(border=True):
            b1, b2, b3 = st.columns([3, 2, 2])
            biz_id = biz.get("telegram_user_id")
            name = biz.get("business_name", "Unknown")
            is_active = biz.get("is_active", True)
            
            with b1:
                st.markdown(f"**{name}**")
                st.caption(f"ID: {biz_id} | Owner: {biz.get('owner_name')}")
            with b2:
                status_color = "green" if is_active else "red"
                st.markdown(f"Status: <span style='color:{status_color}'>{'ACTIVE' if is_active else 'BLOCKED'}</span>", unsafe_allow_html=True)
            with b3:
                if is_active:
                    if st.button("🚫 Block", key=f"block_{biz_id}", use_container_width=True):
                        db.businesses.update_one({"telegram_user_id": biz_id}, {"$set": {"is_active": False}})
                        st.cache_data.clear()
                        st.rerun()
                else:
                    if st.button("✅ Unblock", key=f"unblock_{biz_id}", use_container_width=True):
                        db.businesses.update_one({"telegram_user_id": biz_id}, {"$set": {"is_active": True}})
                        st.cache_data.clear()
                        st.rerun()
