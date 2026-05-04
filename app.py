import streamlit as st
import boto3
import hashlib
import time
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key
import pytz

# ===== 1. CONFIGURACIÓN INICIAL =====
st.set_page_config(
    page_title="NEXUS POS V5", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# ===== 2. ESTÉTICA FUTURISTA SIN LAG =====
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* FONDO ANIMADO FUTURISTA - LIGERO */
    .stApp {
        background: linear-gradient(-45deg, #0f172a, #1e293b, #334155, #0f172a);
        background-size: 400% 400%;
        animation: gradient 15s ease infinite;
    }
    
    @keyframes gradient {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* HEADER CON BRILLO */
    .main-header {
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 50%, #ec4899 100%);
        padding: 2rem;
        border-radius: 20px;
        text-align: center;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        margin-bottom: 2rem;
        animation: glow 2s ease-in-out infinite alternate;
    }
    
    @keyframes glow {
        from { box-shadow: 0 25px 50px -12px rgba(139, 92, 246, 0.5); }
        to { box-shadow: 0 25px 50px -12px rgba(236, 72, 153, 0.5); }
    }
    
    /* GLASSMORPHISM LIGERO */
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 2rem;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        animation: fadeIn 0.6s ease-out;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(
