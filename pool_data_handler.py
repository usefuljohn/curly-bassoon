#!/usr/bin/env python3
"""
BitShares Data Handler
Shared utility for fetching data from BitShares RPC nodes.
"""

import requests
import json
from decimal import Decimal

# Shared API Endpoints
API_URLS = [
    "https://api.bts.mobi/rpc",
    "https://api.dex.trading/rpc", 
    "https://dexnode.net/rpc"
]

def rpc_call(method, params):
    """
    Generic RPC call helper that tries multiple endpoints.
    """
    payload = {
        "id": 1,
        "method": "call",
        "params": [0, method, params]
    }
    
    for url in API_URLS:
        try:
            # Handle URLs that might not have /rpc appended if defined differently elsewhere, 
            # but here we standardize on full RPC URLs in the constant.
            response = requests.post(
                url, 
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    return data["result"]
        except Exception as e:
            # print(f"Error calling {url}: {e}") # Debug only
            continue
            
    return None

def get_pool_data(pool_id):
    """Get liquidity pool object by ID."""
    result = rpc_call("get_objects", [[pool_id]])
    if result and len(result) > 0:
        return result[0]
    return None

def get_account_balance(account_id, asset_id):
    """Get specific asset balance for an account."""
    result = rpc_call("get_account_balances", [account_id, [asset_id]])
    
    if result:
        for bal in result:
            if bal["asset_id"] == asset_id:
                return bal["amount"]
                
    return "0"

def resolve_account_name(account_name):
    """Resolve an account name to its ID."""
    result = rpc_call("lookup_account_names", [[account_name]])
    # Result is a list of account objects or nulls.
    if result and len(result) > 0 and result[0]:
        return result[0].get("id")
    return None
