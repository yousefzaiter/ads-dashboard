#!/usr/bin/env python3
"""
Test script to simulate creative analysis page rendering
Tests data processing, filtering, sorting, and pagination
"""

import os
import sys
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from meta_ads_server import fetch_meta_all_ads
from snap_ads_server import fetch_snap_all_ads

def test_creative_analysis_pipeline():
    """Simulate the complete creative analysis page pipeline"""

    print("\n" + "="*70)
    print("TESTING CREATIVE ANALYSIS PAGE PIPELINE")
    print("="*70)

    # Setup
    meta_token = os.getenv("META_ACCESS_TOKEN")
    snap_token = os.getenv("SNAP_ACCESS_TOKEN")

    meta_account = "act_579554746963968"  # Grass project
    snap_account = "3b43a935-f7d1-49f9-b6f6-a088433e2a09"  # Grass project

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    print(f"\n📊 Fetching ads for date range: {start_str} to {end_str}")

    # Fetch both platforms
    meta_df = fetch_meta_all_ads(meta_token, meta_account, start_str, end_str)
    snap_df = fetch_snap_all_ads(snap_token, snap_account, start_str, end_str)

    if meta_df is None:
        meta_df = pd.DataFrame()
    if snap_df is None:
        snap_df = pd.DataFrame()

    print(f"\n✅ Fetched:")
    print(f"   Meta: {len(meta_df)} ads")
    print(f"   Snap: {len(snap_df)} ads")

    # Combine
    combined = pd.concat([meta_df, snap_df], ignore_index=True)
    print(f"   Total: {len(combined)} ads\n")

    if combined.empty:
        print("❌ No data to process")
        return

    # Test 1: Platform filtering
    print("\n" + "-"*70)
    print("TEST 1: Platform Filtering")
    print("-"*70)

    platforms = combined['Type'].unique()
    for plat in platforms:
        count = len(combined[combined['Type'] == plat])
        print(f"   {plat}: {count} ads")

    # Test 2: Status filtering
    print("\n" + "-"*70)
    print("TEST 2: Status Filtering (Status filter)")
    print("-"*70)

    enabled_only = combined[combined['Status'].isin(['ENABLED', 'ACTIVE'])]
    print(f"   Enabled: {len(enabled_only)} ads")
    print(f"   All: {len(combined)} ads")

    print(f"   Status values: {combined['Status'].unique()}")

    # Test 3: Sorting
    print("\n" + "-"*70)
    print("TEST 3: Sorting")
    print("-"*70)

    # ROAS sorting (descending)
    sorted_roas = combined.sort_values('ROAS', ascending=False).head(5)
    print(f"\n   Top 5 by ROAS:")
    print(f"   {'Ad Name':<40} {'ROAS':>8} {'Spend':>10}")
    print(f"   {'-'*40} {'-'*8} {'-'*10}")
    for idx, row in sorted_roas.iterrows():
        name = str(row['Campaign'])[:35]
        print(f"   {name:<40} {row['ROAS']:>8.2f} {row['Cost']:>10.2f}")

    # CPA sorting (ascending)
    sorted_cpa = combined[combined['CPA'] > 0].sort_values('CPA', ascending=True).head(5)
    print(f"\n   Top 5 by CPA (lowest):")
    print(f"   {'Ad Name':<40} {'CPA':>8} {'Spend':>10}")
    print(f"   {'-'*40} {'-'*8} {'-'*10}")
    for idx, row in sorted_cpa.iterrows():
        name = str(row['Campaign'])[:35]
        print(f"   {name:<40} {row['CPA']:>8.2f} {row['Cost']:>10.2f}")

    # Test 4: Pagination
    print("\n" + "-"*70)
    print("TEST 4: Pagination (24 cards per page)")
    print("-"*70)

    PAGE_SIZE = 24
    total_pages = (len(combined) + PAGE_SIZE - 1) // PAGE_SIZE
    print(f"   Total ads: {len(combined)}")
    print(f"   Page size: {PAGE_SIZE}")
    print(f"   Total pages: {total_pages}")

    for page in range(min(3, total_pages)):
        start_idx = page * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        page_df = combined.iloc[start_idx:end_idx]
        print(f"\n   Page {page+1}: {len(page_df)} ads")
        print(f"   Showing ads {start_idx+1} to {min(end_idx, len(combined))}")

    # Test 5: Combined filtering & sorting
    print("\n" + "-"*70)
    print("TEST 5: Combined Filtering + Sorting")
    print("-"*70)

    # Filter: Snap platform, Enabled only, sorted by ROAS
    filtered = combined[
        (combined['Type'] == 'SNAP_AD') &
        (combined['Status'].isin(['ENABLED', 'ACTIVE']))
    ].sort_values('ROAS', ascending=False).head(5)

    print(f"\n   Snap ads (Enabled only, top 5 by ROAS):")
    print(f"   {'Ad Name':<40} {'ROAS':>8} {'Cost':>10}")
    print(f"   {'-'*40} {'-'*8} {'-'*10}")
    for idx, row in filtered.iterrows():
        name = str(row['Campaign'])[:35]
        print(f"   {name:<40} {row['ROAS']:>8.2f} {row['Cost']:>10.2f}")

    # Test 6: Check all required columns
    print("\n" + "-"*70)
    print("TEST 6: Data Completeness")
    print("-"*70)

    required_cols = ['Campaign', 'Status', 'ROAS', 'CPA', 'CTR', 'Cost', 'Type', 'ID']
    missing = [col for col in required_cols if col not in combined.columns]

    if not missing:
        print(f"   ✅ All required columns present")
    else:
        print(f"   ❌ Missing columns: {missing}")

    # Check for null values
    null_counts = combined[required_cols].isnull().sum()
    if null_counts.sum() == 0:
        print(f"   ✅ No null values in required columns")
    else:
        print(f"   ⚠️ Null values found:")
        for col, count in null_counts[null_counts > 0].items():
            print(f"      {col}: {count}")

    print("\n" + "="*70)
    print("✅ CREATIVE ANALYSIS PIPELINE TEST COMPLETED SUCCESSFULLY")
    print("="*70)


if __name__ == "__main__":
    test_creative_analysis_pipeline()
