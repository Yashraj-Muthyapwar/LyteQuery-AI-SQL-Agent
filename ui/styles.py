# sql-agent-pro/ui/styles.py
import streamlit as st

def load_css():
    """Load custom CSS styles"""
    st.markdown("""
    <style>

    /* --- Main container --- */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* --- Headers --- */
    h1 {
        color: #1f2937;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    h3 {
        color: #374151;
        font-weight: 600;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    
    h4 {
        color: #4b5563;
        font-weight: 600;
        margin-bottom: 0.75rem;
    }



    /* --- Follow-up chips --- */
    .chips-wrap { 
        margin-top: 0.5rem; 
        margin-bottom: 0.5rem; 
    }
    
    .chip-row { 
        display: flex; 
        gap: 0.5rem; 
        flex-wrap: wrap; 
    }
    
    button[kind="secondary"] { 
        border-radius: 999px !important; 
    }
    
    .chip-btn [data-baseweb="button"] { 
        border-radius: 999px !important; 
    }

    .chip-btn {
        padding: 0 !important;
    }

    .chip-btn button {
      border-radius:999px !important;
      border:1px solid #e5e7eb !important;
      background:#fff !important;
      color:#111827 !important;
      font-weight:600 !important;
    }
    .chip-btn button:hover {
      background:#f3f4f6 !important;
      border-color:#d1d5db !important;
    }
    .sugg-why-inline {
      color:#6b7280; font-size:.85rem; margin-top:.25rem;
    }
    
    .success-badge {
        background: #10b981;
        color: white;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
    }

    /* --- Code blocks --- */
    code {
        background: 
        #f3f4f6;
        padding: 0.2rem 0.4rem;
        border-radius: 0.25rem;
        font-size: 0.9em;
    }


    /* --- Smooth transitions --- */
    * {
        transition: all 0.2s ease-in-out;
    }
    </style>
    """, unsafe_allow_html=True)
