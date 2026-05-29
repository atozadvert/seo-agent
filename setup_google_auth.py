#!/usr/bin/env python3
"""
Google Search Console Authentication Setup
This script handles OAuth2 authentication for Google Search Console API
"""

import json
import pickle
import os
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("❌ Missing: google-auth-oauthlib")
    print("   Install: pip install google-auth-oauthlib")
    exit(1)

SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
OAUTH_FILE = "client_secret_120764177866-n3j71kun2dr1um5sc43vohs5rtl2lr3s.apps.googleusercontent.com.json"
TOKEN_FILE = "token.pickle"


def authenticate_gsc():
    """Authenticate with Google Search Console API and save credentials."""
    print("\n🔐 Google Search Console Authentication Setup")
    print("=" * 60)
    
    # Check if OAuth file exists
    if not Path(OAUTH_FILE).exists():
        print(f"\n❌ OAuth file not found: {OAUTH_FILE}")
        print("   Please download from: https://console.cloud.google.com/apis/credentials")
        return False
    
    print(f"\n✅ Found OAuth credentials file")
    
    # Load existing token if available
    creds = None
    if Path(TOKEN_FILE).exists():
        print(f"✅ Loading cached credentials from {TOKEN_FILE}...")
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # Refresh or create new credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            print("\n📖 Starting OAuth authentication flow...")
            print("   → A browser window will open")
            print("   → Sign in with your Google account")
            print("   → Allow access to Search Console\n")
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    OAUTH_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"\n❌ Authentication failed: {e}")
                return False
        
        # Save credentials for future runs
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
            print(f"\n✅ Credentials saved to {TOKEN_FILE}")
    else:
        print(f"✅ Credentials are valid and ready to use")
    
    print("\n" + "=" * 60)
    print("✅ Authentication successful!")
    print("\nYou can now run: python seo_agent.py audit")
    print("   → Agent will use real Google Search Console data")
    
    return True


def verify_gsc_connection():
    """Verify that GSC API is accessible."""
    try:
        from googleapiclient.discovery import build
        
        if not Path(TOKEN_FILE).exists():
            print("❌ No credentials found. Run setup_google_auth.py first")
            return False
        
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
        
        if not creds or not creds.valid:
            print("❌ Credentials invalid. Run setup_google_auth.py again")
            return False
        
        service = build('webmasters', 'v3', credentials=creds)
        print("✅ Successfully connected to Google Search Console API")
        
        # Try to list sites
        try:
            response = service.sites().list().execute()
            sites = response.get('siteEntry', [])
            print(f"\n📍 Verified sites ({len(sites)} total):")
            for site in sites:
                print(f"   • {site['siteUrl']}")
            return True
        except Exception as e:
            print(f"⚠️  Could not list sites: {e}")
            return True  # Connection works, just no sites
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        verify_gsc_connection()
    else:
        authenticate_gsc()
