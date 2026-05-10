import streamlit as st
import pandas as pd
import pymongo
import os
from dotenv import load_dotenv
import plotly.express as px

# Load environment variables
load_dotenv()

# MongoDB Connection
MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB_NAME", "smallbiz_bot")

@st.cache_resource
def init_connection():
    return pymongo.MongoClient(MONGO_URI)

client = init_connection()
db = client[DB_NAME]

def get_data():
    businesses = list(db.businesses.find())
    orders = list(db.orders.find())
    inventory = list(db.inventory.find())
    return businesses, orders, inventory

# Custom CSS for further styling
st.markdown("""
    <style>
    .stApp {
        background-color: #FFFFFF;
    }
    .main-header {
        color: #FFA500;
        font-weight: bold;
        text-align: center;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #FFF0C2;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
        margin-bottom: 20px;
    }
    .metric-title {
        font-size: 16px;
        color: #333333;
        margin-bottom: 10px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        color: #FFA500;
    }
    .stSelectbox label {
        color: #333333;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header">SmallBiz Telegram Bot - Admin Dashboard</h1>', unsafe_allow_html=True)

try:
    businesses, orders, inventory = get_data()
    
    # System Level Metrics
    st.markdown("### System Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    total_businesses = len(businesses)
    total_orders = len(orders)
    total_revenue = sum([o.get('total_amount', 0) for o in orders if o.get('status') != 'cancelled'])
    total_inventory = len(inventory)
    
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-title">Total Businesses</div><div class="metric-value">{total_businesses}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><div class="metric-title">Total Orders</div><div class="metric-value">{total_orders}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><div class="metric-title">Total Revenue</div><div class="metric-value">₹{total_revenue:,.2f}</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-card"><div class="metric-title">Inventory Items</div><div class="metric-value">{total_inventory}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    
    if businesses:
        b_options = {b["telegram_user_id"]: f"{b.get('business_name', 'Unknown')} (ID: {b['telegram_user_id']})" for b in businesses}
        selected_b_id = st.selectbox("Select a Business to View Details:", options=["All"] + list(b_options.keys()), format_func=lambda x: "All Businesses" if x == "All" else b_options[x])
        
        # Filter Data
        if selected_b_id != "All":
            orders = [o for o in orders if o.get('business_id') == selected_b_id]
            inventory = [i for i in inventory if i.get('business_id') == selected_b_id]
        
        # Business Specific Visualizations
        st.markdown(f"### {'System Wide Data' if selected_b_id == 'All' else b_options[selected_b_id] + ' Data'}")
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("#### Order Status Breakdown")
            if orders:
                df_orders = pd.DataFrame(orders)
                status_counts = df_orders['status'].value_counts().reset_index()
                status_counts.columns = ['status', 'count']
                fig_pie = px.pie(status_counts, names='status', values='count', 
                                 color_discrete_sequence=['#FFA500', '#FFCC00', '#FF8C00', '#FFD700', '#FFF0C2'])
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No orders found for this selection.")
                
        with col_chart2:
            st.markdown("#### Payment Status Breakdown")
            if orders and 'payment_status' in df_orders.columns:
                payment_counts = df_orders['payment_status'].value_counts().reset_index()
                payment_counts.columns = ['payment_status', 'count']
                fig_pay = px.pie(payment_counts, names='payment_status', values='count', 
                                 color_discrete_sequence=['#FFCC00', '#FFA500', '#FFF0C2'])
                st.plotly_chart(fig_pay, use_container_width=True)
            else:
                st.info("No payment data available.")
        
        st.markdown("#### Inventory Status")
        if inventory:
            df_inv = pd.DataFrame(inventory)
            if 'quantity' in df_inv.columns and 'low_stock_threshold' in df_inv.columns:
                df_inv['is_low_stock'] = df_inv['quantity'] <= df_inv['low_stock_threshold']
                low_stock_items = df_inv[df_inv['is_low_stock']]
                
                if not low_stock_items.empty:
                    st.warning(f"⚠️ {len(low_stock_items)} items are low on stock!")
                    st.dataframe(low_stock_items[['name', 'quantity', 'low_stock_threshold', 'unit']], use_container_width=True)
                else:
                    st.success("All inventory items are adequately stocked.")
                
                # Inventory Chart
                fig_bar = px.bar(df_inv.sort_values(by='quantity', ascending=False).head(15), 
                                 x='name', y='quantity', title="Top 15 Inventory Items by Quantity",
                                 color_discrete_sequence=['#FFA500'])
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.dataframe(df_inv, use_container_width=True)
        else:
            st.info("No inventory found for this selection.")
            
    else:
        st.info("No businesses found in the database. Wait for users to register via the bot.")
        
except Exception as e:
    st.error(f"Error connecting to database or fetching data: {str(e)}")
    st.info("Make sure your MongoDB container is running and accessible.")

