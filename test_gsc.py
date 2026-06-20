#!/usr/bin/env python3
import sqlite3
import json
import base64
import os
from datetime import datetime
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2 import service_account

load_dotenv()

# Test GSC connection and keyword insertion
service_account_b64 = os.getenv("GSC_SERVICE_ACCOUNT_JSON", "").strip()
if service_account_b64:
    try:
        service_account_info = json.loads(base64.b64decode(service_account_b64).decode("utf-8"))
    except:
        # Try loading as plain JSON string instead
        service_account_info = json.loads(service_account_b64)
    
    creds = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
    )
    service = build("webmasters", "v3", credentials=creds)
    print("✓ Service account authenticated successfully")
    
    # Try to get sites
    try:
        response = service.sites().list().execute()
        sites = [s['siteUrl'] for s in response.get('siteEntry', [])]
        print(f"✓ Found {len(sites)} verified sites")
        for site in sites:
            print(f"  - {site}")
    except Exception as e:
        print(f"✗ Error fetching sites: {e}")
else:
    print("✗ GSC_SERVICE_ACCOUNT_JSON not configured")
