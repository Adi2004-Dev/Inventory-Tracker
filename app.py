import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from datetime import datetime

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('supply_chain.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS Inventory 
                 (id INTEGER PRIMARY KEY, product TEXT, category TEXT, warehouse TEXT, stock INTEGER, reorder_level INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS Restock_Alerts 
                 (id INTEGER PRIMARY KEY, product TEXT, alert_date TEXT, status TEXT)''')
                 
    c.execute('''CREATE TABLE IF NOT EXISTS Suppliers 
                 (id INTEGER PRIMARY KEY, name TEXT, contact TEXT, email TEXT, lead_time INTEGER)''')
    
    c.execute("SELECT COUNT(*) FROM Inventory")
    if c.fetchone()[0] == 0:
        sample_data = [
            ('Processors', 'Electronics', 'North Hub', 45, 50),
            ('Motherboards', 'Electronics', 'South Hub', 120, 40),
            ('Power Supplies', 'Hardware', 'North Hub', 15, 30),
            ('RAM Modules', 'Memory', 'East Hub', 200, 100)
        ]
        c.executemany("INSERT INTO Inventory (product, category, warehouse, stock, reorder_level) VALUES (?, ?, ?, ?, ?)", sample_data)
        
    c.execute("SELECT COUNT(*) FROM Suppliers")
    if c.fetchone()[0] == 0:
        sample_suppliers = [
            ('TechCorp Logistics', 'John Doe', 'john@techcorp.com', 5),
            ('Global Hardware Inc.', 'Jane Smith', 'jane@ghi.com', 10),
            ('Memory Makers Ltd.', 'Alice Johnson', 'alice@mml.com', 7)
        ]
        c.executemany("INSERT INTO Suppliers (name, contact, email, lead_time) VALUES (?, ?, ?, ?)", sample_suppliers)
        
    conn.commit()
    conn.close()

# --- APP CONFIGURATION ---
st.set_page_config(page_title="Supply Chain & Inventory DBMS", layout="wide")
init_db()

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Dashboard", "Receive Shipment", "Live Checkout Simulator", "Supplier Management"])

# --- PAGE: DASHBOARD ---
if page == "Dashboard":
    st.title("📦 Global Inventory Dashboard")
    
    conn = sqlite3.connect('supply_chain.db')
    df_inventory = pd.read_sql_query("SELECT * FROM Inventory", conn)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Items in Stock", df_inventory['stock'].sum())
    col2.metric("Active Warehouses", df_inventory['warehouse'].nunique())
    
    low_stock_count = len(df_inventory[df_inventory['stock'] <= df_inventory['reorder_level']])
    col3.metric("Critical Restock Alerts", low_stock_count, delta_color="inverse")
    
    st.divider()

    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        st.subheader("Stock Distribution by Warehouse")
        fig1 = px.pie(df_inventory, values='stock', names='warehouse', hole=0.4)
        st.plotly_chart(fig1, use_container_width=True)
        
    with row1_col2:
        st.subheader("Current Stock vs. Reorder Levels")
        fig2 = px.bar(df_inventory, x='product', y=['stock', 'reorder_level'], 
                      barmode='group', labels={'value':'Quantity', 'variable':'Metric'}, color='category')
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("⚠️ Action Required: Low Stock Alerts")
    alerts_df = df_inventory[df_inventory['stock'] <= df_inventory['reorder_level']]
    if not alerts_df.empty:
        st.error(f"Attention: {len(alerts_df)} items have dropped below their reorder threshold.")
        st.dataframe(alerts_df[['product', 'category', 'warehouse', 'stock', 'reorder_level']], use_container_width=True)
    else:
        st.success("All inventory levels are healthy.")
        
    conn.close()

# --- PAGE: LIVE CHECKOUT SIMULATOR ---
elif page == "Live Checkout Simulator":
    st.title("🛒 Live Checkout Simulator")
    
    conn = sqlite3.connect('supply_chain.db')
    df_products = pd.read_sql_query("SELECT * FROM Inventory", conn)
    
    # Create a grid layout
    cols = st.columns(3)
    
    for index, row in df_products.iterrows():
        # Distribute items across the 3 columns
        col = cols[index % 3]
        
        with col:
            with st.container(border=True):
                st.subheader(row['product'])
                st.caption(f"Warehouse: {row['warehouse']}")
                
                # Dynamic visual progress bar
                max_visual = max(row['reorder_level'] * 3, row['stock']) # Scale relative to reorder level
                progress = min(row['stock'] / max_visual, 1.0) if max_visual > 0 else 0
                
                if row['stock'] <= row['reorder_level']:
                    st.error(f"Stock: {row['stock']} / Reorder at: {row['reorder_level']}")
                else:
                    st.success(f"Stock: {row['stock']} / Reorder at: {row['reorder_level']}")
                
                st.progress(progress)
                
                sell_qty = st.number_input("Qty to Ship", min_value=1, max_value=row['stock'] if row['stock'] > 0 else 1, key=f"qty_{row['id']}")
                
                if st.button("Ship Order", key=f"btn_{row['id']}", disabled=(row['stock'] == 0)):
                    new_stock = row['stock'] - sell_qty
                    c = conn.cursor()
                    c.execute("UPDATE Inventory SET stock = ? WHERE id = ?", (new_stock, row['id']))
                    conn.commit()
                    
                    # Interactivity: Pop-up Toast Notifications
                    st.toast(f"🚚 Order processed: {sell_qty} units of {row['product']} shipped!")
                    
                    # Simulate the backend Trigger alerting the frontend
                    if new_stock <= row['reorder_level'] and row['stock'] > row['reorder_level']:
                        st.toast(f"🚨 ALERT: {row['product']} dropped below reorder level!", icon="⚠️")
                    
                    # Instantly refresh the UI to show new data
                    st.rerun()

    conn.close()

# --- PAGE: RECEIVE SHIPMENT ---
elif page == "Receive Shipment":
    st.title("📥 Receive Incoming Stock")
    
    tab1, tab2 = st.tabs(["Add to Existing Stock", "Register New Product/Category"])
    conn = sqlite3.connect('supply_chain.db')
    
    with tab1:
        st.subheader("Update Current Inventory")
        products = pd.read_sql_query("SELECT product FROM Inventory", conn)['product'].tolist()
        
        if products:
            with st.form("update_stock_form", clear_on_submit=True):
                selected_product = st.selectbox("Select Product", products)
                received_qty = st.number_input("Quantity Received", min_value=1, step=1)
                
                if st.form_submit_button("Update Inventory"):
                    c = conn.cursor()
                    c.execute("UPDATE Inventory SET stock = stock + ? WHERE product = ?", (received_qty, selected_product))
                    conn.commit()
                    
                    # Interactivity: Pop-up Toast
                    st.toast(f"✅ Successfully received {received_qty} units of {selected_product}.")
                    st.rerun()
                    
    with tab2:
        st.subheader("Manual Entry: New Product Profile")
        
        with st.form("new_product_form", clear_on_submit=True):
            new_product = st.text_input("Product Name")
            new_category = st.text_input("Category")
            new_warehouse = st.selectbox("Assign to Warehouse", ["North Hub", "South Hub", "East Hub", "West Hub"])
            
            c1, c2 = st.columns(2)
            with c1: initial_stock = st.number_input("Initial Quantity", min_value=0, step=1)
            with c2: reorder_lvl = st.number_input("Reorder Level", min_value=1, step=1, value=20)
            
            if st.form_submit_button("Register and Save"):
                if new_product.strip() and new_category.strip():
                    c = conn.cursor()
                    c.execute("SELECT * FROM Inventory WHERE product = ?", (new_product,))
                    if c.fetchone():
                        st.error("Product already exists!")
                    else:
                        c.execute("INSERT INTO Inventory (product, category, warehouse, stock, reorder_level) VALUES (?, ?, ?, ?, ?)", 
                                  (new_product, new_category, new_warehouse, initial_stock, reorder_lvl))
                        conn.commit()
                        st.toast(f"🎉 New product profile created for {new_product}!")
                        st.rerun()
                else:
                    st.error("Name and Category cannot be empty.")
    conn.close()

# --- PAGE: SUPPLIER MANAGEMENT ---
elif page == "Supplier Management":
    st.title("🤝 Supplier Directory")
    
    tab1, tab2 = st.tabs(["View Directory", "Onboard New Supplier"])
    conn = sqlite3.connect('supply_chain.db')
    
    with tab1:
        st.subheader("Active Supply Partners")
        df_suppliers = pd.read_sql_query("SELECT id, name, contact, email, lead_time as 'Lead Time (Days)' FROM Suppliers", conn)
        if not df_suppliers.empty:
            st.dataframe(df_suppliers, hide_index=True, use_container_width=True)
            
    with tab2:
        st.subheader("Register New Supplier")
        with st.form("new_supplier_form", clear_on_submit=True):
            s_name = st.text_input("Company Name")
            c1, c2 = st.columns(2)
            with c1: s_contact = st.text_input("Primary Contact")
            with c2: s_email = st.text_input("Contact Email")
            s_lead_time = st.number_input("Average Lead Time (Days)", min_value=1, step=1, value=5)
            
            if st.form_submit_button("Add to Directory"):
                if s_name.strip():
                    c = conn.cursor()
                    c.execute("INSERT INTO Suppliers (name, contact, email, lead_time) VALUES (?, ?, ?, ?)", 
                              (s_name, s_contact, s_email, s_lead_time))
                    conn.commit()
                    st.toast(f"🤝 Added {s_name} to supplier directory!")
                    st.rerun()
                else:
                    st.error("Company Name is required!")
    conn.close()