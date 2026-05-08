#!/usr/bin/env python3
"""
Debug Meta fetch to understand why no data is returned
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from meta_ads_server import _get, fetch_meta_all_ads

def test_meta_api_directly():
    """Test Meta API calls directly to debug"""
    token = os.getenv("META_ACCESS_TOKEN")
    account_id = "act_579554746963968"

    print("\n" + "="*60)
    print("TESTING META API DIRECTLY")
    print("="*60)

    # Test 1: List ads
    print("\n1️⃣ Fetching ads list...")
    try:
        ads_resp = _get(
            f"/{account_id}/ads",
            token,
            {
                "fields": ("id,name,effective_status,adset_id,adset_name,"
                           "campaign_id,campaign_name,"
                           "creative{thumbnail_url,image_url,object_story_spec}"),
                "limit":  500,
                "filtering": '[{"field":"effective_status","operator":"IN",'
                             '"value":["ACTIVE","PAUSED","CAMPAIGN_PAUSED",'
                             '"ADSET_PAUSED","DISAPPROVED","PENDING_REVIEW"]}]',
            },
        )
        ad_count = len(ads_resp.get("data", []))
        print(f"   ✅ Fetched {ad_count} ads")
        if ad_count > 0:
            print(f"   Sample ad: {ads_resp['data'][0]}")
        else:
            print("   ⚠️ No ads returned")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()

    # Test 2: Fetch insights
    print("\n2️⃣ Fetching insights...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    try:
        ins_resp = _get(
            f"/{account_id}/insights",
            token,
            {
                "fields": ("ad_id,spend,impressions,clicks,ctr,cpc,"
                           "reach,frequency,actions,action_values"),
                "level":  "ad",
                "time_range": f'{{"since":"{start_date.strftime("%Y-%m-%d")}","until":"{end_date.strftime("%Y-%m-%d")}"}}',
                "limit":  500,
            },
        )
        ins_count = len(ins_resp.get("data", []))
        print(f"   ✅ Fetched {ins_count} insight records")
        if ins_count > 0:
            print(f"   Sample insight: {ins_resp['data'][0]}")
        else:
            print("   ⚠️ No insights returned")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()

    # Test 3: Full fetch
    print("\n3️⃣ Running full fetch_meta_all_ads()...")
    try:
        df = fetch_meta_all_ads(token, account_id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        if df is not None and not df.empty:
            print(f"   ✅ Fetched {len(df)} rows")
            print(f"   Columns: {list(df.columns)}")
            print(f"   Sample:\n{df[['Campaign', 'Status', 'Cost']].head()}")
        else:
            print("   ❌ No data returned")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_meta_api_directly()
