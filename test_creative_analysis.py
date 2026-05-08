#!/usr/bin/env python3
"""
Test script for creative analysis page functionality
Tests the fetch functions and data processing without UI
"""

import os
import sys
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import the server modules
from meta_ads_server import fetch_meta_all_ads
from snap_ads_server import fetch_snap_all_ads

def test_meta_fetch():
    """Test Meta ads fetching"""
    print("\n" + "="*60)
    print("TESTING META ADS FETCH")
    print("="*60)

    token = os.getenv("META_ACCESS_TOKEN")
    if not token:
        print("❌ META_ACCESS_TOKEN not found in .env")
        return None

    # Use test account from clients.json
    # Format: "act_XXXXXXXXXX"
    account_id = "act_579554746963968"  # Grass project

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    print(f"\n📊 Fetching Meta ads for account: {account_id}")
    print(f"   Date range: {start_date.date()} to {end_date.date()}")

    try:
        df = fetch_meta_all_ads(token, account_id, start_date, end_date)

        if df is None or df.empty:
            print("❌ No data returned from Meta")
            return None

        print(f"\n✅ SUCCESS - Fetched {len(df)} Meta ads")
        print(f"\n📋 Columns: {list(df.columns)}")
        print(f"\n📊 Data Sample:")
        print(df[['Campaign', 'Status', 'ROAS', 'CPA', 'CTR']].head())
        print(f"\n📈 Statuses: {df['Status'].unique()}")
        print(f"   ENABLED: {len(df[df['Status'] == 'ENABLED'])}")
        print(f"   PAUSED: {len(df[df['Status'] == 'PAUSED'])}")

        return df

    except Exception as e:
        print(f"❌ Error fetching Meta ads: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_snap_fetch():
    """Test Snap ads fetching"""
    print("\n" + "="*60)
    print("TESTING SNAP ADS FETCH")
    print("="*60)

    token = os.getenv("SNAP_ACCESS_TOKEN")
    if not token:
        print("❌ SNAP_ACCESS_TOKEN not found in .env")
        return None

    # Use test account from clients.json
    account_id = "3b43a935-f7d1-49f9-b6f6-a088433e2a09"  # Grass project

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    print(f"\n📊 Fetching Snap ads for account: {account_id}")
    print(f"   Date range: {start_date.date()} to {end_date.date()}")

    try:
        df = fetch_snap_all_ads(token, account_id, start_date, end_date, active_only=True)

        if df is None or df.empty:
            print("❌ No data returned from Snap")
            return None

        print(f"\n✅ SUCCESS - Fetched {len(df)} Snap ads")
        print(f"\n📋 Columns: {list(df.columns)}")
        print(f"\n📊 Data Sample:")
        print(df[['Campaign', 'Status', 'ROAS', 'CPA', 'CTR']].head())
        print(f"\n📈 Statuses: {df['Status'].unique()}")
        print(f"   ENABLED: {len(df[df['Status'] == 'ENABLED'])}")
        print(f"   PAUSED: {len(df[df['Status'] == 'PAUSED'])}")

        return df

    except Exception as e:
        print(f"❌ Error fetching Snap ads: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_filtering_and_sorting(df):
    """Test filtering and sorting functionality"""
    if df is None or df.empty:
        return

    print("\n" + "="*60)
    print("TESTING FILTERING & SORTING")
    print("="*60)

    # Test ROAS sorting
    print("\n🔽 Sorting by ROAS (descending):")
    sorted_roas = df.sort_values('ROAS', ascending=False).head(3)
    print(sorted_roas[['Campaign', 'ROAS']].to_string())

    # Test CPA sorting
    print("\n🔼 Sorting by CPA (ascending):")
    sorted_cpa = df.sort_values('CPA', ascending=True).head(3)
    print(sorted_cpa[['Campaign', 'CPA']].to_string())

    # Test active only filter
    print("\n📌 Active/Enabled ads only:")
    active = df[df['Status'].isin(['ENABLED', 'ACTIVE'])]
    print(f"   Total: {len(active)} active ads")

    # Test pagination
    print("\n📄 Pagination (first 6 cards):")
    paginated = df.head(6)
    print(paginated[['Campaign', 'ROAS', 'CPA', 'CTR']].to_string())


if __name__ == "__main__":
    print("\n🚀 Starting Creative Analysis Fetch Tests")

    meta_df = test_meta_fetch()
    snap_df = test_snap_fetch()

    # Combine dataframes for additional tests
    if meta_df is not None and snap_df is not None:
        combined_df = pd.concat([meta_df, snap_df], ignore_index=True)
        print("\n" + "="*60)
        print(f"COMBINED RESULTS: {len(combined_df)} total ads")
        print("="*60)
        test_filtering_and_sorting(combined_df)
    elif meta_df is not None:
        test_filtering_and_sorting(meta_df)
    elif snap_df is not None:
        test_filtering_and_sorting(snap_df)
    else:
        print("\n❌ No data to test")

    print("\n✅ Tests completed\n")
