import json
import requests
import datetime
import csv
import os
from decimal import Decimal, getcontext
from pool_data_handler import get_pool_data, get_account_balance, rpc_call

# Set precision
getcontext().prec = 28

# Configuration
PORTFOLIOS = [
    {"name": "USD", "config": "config_core.json", "output": "capital_history_usd.csv"},
    {"name": "GROWTH", "config": "config_growth.json", "output": "capital_history_growth.csv"}
]

def load_user_settings():
    """Load user settings including accounts."""
    settings_file = "user_settings.json"
    defaults = {"accounts": ["1.2.1795137"]} # Default fallback
    
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
            
    return defaults

def get_object(object_id):
    """Fetch a single object from the blockchain"""
    res = rpc_call("get_objects", [[object_id]])
    if res and len(res) > 0:
        return res[0]
    return None

def get_asset_supply(asset_id):
    """Get the current supply of an asset"""
    # 1. Get Asset Object
    asset_obj = get_object(asset_id)
    if not asset_obj:
        return Decimal(0), 0
        
    precision = asset_obj.get("precision", 0)
    dynamic_id = asset_obj.get("dynamic_asset_data_id")
    
    # 2. Get Dynamic Data
    dynamic_obj = get_object(dynamic_id)
    if not dynamic_obj:
        return Decimal(0), precision
        
    current_supply_raw = Decimal(dynamic_obj.get("current_supply", 0))
    return current_supply_raw / (Decimal(10) ** precision), precision

def get_twentix_price_usd(config):
    """Determine TWENTIX price in USD using reference pools"""
    # Look for pools marked as price reference
    # Prefer USDC or USD
    
    candidates = []
    
    for pool in config.get("pools", []):
        if pool.get("is_price_reference"):
            # Check which side is TWENTIX (Asset A or B)
            # We want Price = USD_Amount / TWENTIX_Amount
            
            p_data = get_pool_data(pool["id"])
            if not p_data:
                continue
                
            is_twentix_a = pool["asset_a"]["symbol"] == "TWENTIX"
            
            # Get precisions
            prec_a = pool["asset_a"]["precision"]
            prec_b = pool["asset_b"]["precision"]
            
            bal_a = Decimal(p_data["balance_a"]) / (Decimal(10) ** prec_a)
            bal_b = Decimal(p_data["balance_b"]) / (Decimal(10) ** prec_b)
            
            if bal_a == 0 or bal_b == 0:
                continue
                
            if is_twentix_a:
                # Pair is TWENTIX / USD
                # Price of 1 TWENTIX = USD_Bal / TWENTIX_Bal = bal_b / bal_a
                price = bal_b / bal_a
                label = pool["asset_b"]["symbol"]
            else:
                # Pair is USD / TWENTIX
                # Price of 1 TWENTIX = USD_Bal / TWENTIX_Bal = bal_a / bal_b
                price = bal_a / bal_b
                label = pool["asset_a"]["symbol"]
            
            print(f"  Reference Price from {pool['label']}: ${price:.6f}")
            candidates.append(price)
            
    if candidates:
        avg_price = sum(candidates) / len(candidates)
        print(f"  > Average TWENTIX Price: ${avg_price:.6f}")
        return avg_price
        
    print("  ! No price reference found in this config. Trying fallback...")
    return None

# Known Stablecoin Symbols/Substrings to check
STABLECOINS = ["USDT", "USDC", "HONEST.USD", "XBTSX.USDC", "USD"]

def is_stable_asset(symbol):
    """Check if asset symbol indicates a stablecoin"""
    # Exact match or endswith for things like "XBTSX.USDC"
    # Actually, let's just check if the known strings are in the symbol
    for s in STABLECOINS:
        if s == symbol or symbol.endswith(f".{s}") or symbol == s:
            return True
    return False

def ensure_csv_headers(filename, current_pool_labels):
    """
    Ensures the CSV file has the correct headers including Timestamp, Accounts, Total Value USD,
    and all current pool labels. Preserves existing data and columns.
    """
    base_headers = ["Timestamp", "Accounts", "Total Value USD"]
    
    # If file doesn't exist, just return the full new header list
    if not os.path.exists(filename):
        return base_headers + current_pool_labels

    existing_headers = []
    # Read existing headers
    try:
        with open(filename, 'r', newline='') as f:
            reader = csv.reader(f)
            try:
                existing_headers = next(reader)
            except StopIteration:
                pass
    except Exception as e:
        print(f"Warning: Could not read existing headers from {filename}: {e}")

    # Calculate new headers (preserving order of existing, adding new ones at end)
    new_headers = list(existing_headers)
    
    # 1. Ensure Base Headers are present
    for h in base_headers:
        if h not in new_headers:
            # If "Accounts" is missing, insert it after Timestamp if possible
            if h == "Accounts" and "Timestamp" in new_headers:
                 idx = new_headers.index("Timestamp") + 1
                 new_headers.insert(idx, h)
            else:
                 new_headers.append(h)

    # 2. Add any new pool labels that aren't in headers yet
    for label in current_pool_labels:
        if label not in new_headers:
            new_headers.append(label)

    # If headers changed, rewrite the file
    if new_headers != existing_headers:
        print(f"Updating CSV headers for {filename}...")
        rows = []
        if existing_headers:
            with open(filename, 'r', newline='') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=new_headers)
            writer.writeheader()
            for row in rows:
                # Remove extra fields (None key from DictReader) and keys not in new_headers
                clean_row = {k: v for k, v in row.items() if k in new_headers and k is not None}
                writer.writerow(clean_row)
                
    return new_headers

def find_twentix_price_for_asset(target_asset_symbol, all_pools_config):
    """
    Attempts to find the price of 'target_asset_symbol' in terms of TWENTIX
    by looking for a direct pair in the provided pools configuration.
    Returns: Price of 1 unit of Target Asset in TWENTIX (Decimal) or None
    """
    for pool in all_pools_config:
        p_a = pool["asset_a"]["symbol"]
        p_b = pool["asset_b"]["symbol"]
        
        # We are looking for a pair (Target, TWENTIX) or (TWENTIX, Target)
        if target_asset_symbol not in (p_a, p_b):
            continue
            
        other_asset = p_b if p_a == target_asset_symbol else p_a
        if other_asset != "TWENTIX":
            continue
            
        # Found a pairing pool!
        # Calculate price
        p_data = get_pool_data(pool["id"])
        if not p_data:
            continue
            
        prec_a = pool["asset_a"]["precision"]
        prec_b = pool["asset_b"]["precision"]
        
        bal_a = Decimal(p_data["balance_a"]) / (Decimal(10) ** prec_a)
        bal_b = Decimal(p_data["balance_b"]) / (Decimal(10) ** prec_b)
        
        if bal_a == 0 or bal_b == 0:
            continue

        # Price = TWENTIX Amount / Target Asset Amount
        if p_a == "TWENTIX":
            # Asset A is TWENTIX, Asset B is Target
            # Price = bal_a / bal_b
            return bal_a / bal_b
        else:
            # Asset B is TWENTIX, Asset A is Target
            # Price = bal_b / bal_a
            return bal_b / bal_a
            
    return None

def process_portfolio(portfolio, global_price, accounts):
    """Process a single portfolio configuration"""
    name = portfolio["name"]
    config_file = portfolio["config"]
    output_file = portfolio["output"]
    
    print(f"\n=== Processing Portfolio: {name} ===")
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error loading {config_file}: {e}")
        return

    pools = config.get("pools", [])
    if not pools:
        print(f"  No pools configured for {name}.")
        return Decimal(0)

    # If global price isn't set, try to find it in this config (only if needed fallback)
    twentix_price = global_price
    if not twentix_price:
         twentix_price = get_twentix_price_usd(config)
    
    if not twentix_price:
        # Final fallback
        twentix_price = Decimal("0.003")
        # Only warn if we actually might need it
        # print(f"  Using Hardcoded Safety Price: ${twentix_price}")

    total_portfolio_usd = Decimal(0)
    pool_valuations = []

    print(f"--- Processing Pools for {name} ---")
    
    for pool_conf in pools:
        if pool_conf.get("skip_valuation"):
            continue

        pool_id = pool_conf["id"]
        label = pool_conf["label"]
        
        # Fetch Pool Data
        pool_obj = get_pool_data(pool_id)
        if not pool_obj:
            print(f"Skipping {label} ({pool_id}): No data")
            continue
            
        share_asset_id = pool_obj.get("share_asset")
        
        # Get Total Supply of LP Token
        total_supply, share_prec = get_asset_supply(share_asset_id)
        
        if total_supply == 0:
            print(f"Skipping {label}: Zero supply")
            continue
            
        # Get User Balances
        user_balance_total = Decimal(0)
        for account in accounts:
            bal_raw = get_account_balance(account, share_asset_id)
            if bal_raw:
                user_balance_total += Decimal(bal_raw) / (Decimal(10) ** share_prec)
        
        # We now allow zero balance to show up in the report (as 0% share)
        # if user_balance_total == 0:
        #    continue
            
        # --- VALUATION LOGIC ---
        pool_tvl_usd = Decimal(0)
        
        asset_a_sym = pool_conf["asset_a"]["symbol"]
        asset_b_sym = pool_conf["asset_b"]["symbol"]
        prec_a = pool_conf["asset_a"]["precision"]
        prec_b = pool_conf["asset_b"]["precision"]
        
        balance_a = Decimal(pool_obj["balance_a"]) / (Decimal(10) ** prec_a)
        balance_b = Decimal(pool_obj["balance_b"]) / (Decimal(10) ** prec_b)

        # Method 1: Stablecoin x 2
        if is_stable_asset(asset_a_sym):
            pool_tvl_usd = balance_a * 2
            # print(f"  > {label}: Valued via {asset_a_sym} x 2")
        elif is_stable_asset(asset_b_sym):
            pool_tvl_usd = balance_b * 2
            # print(f"  > {label}: Valued via {asset_b_sym} x 2")
        else:
            # Method 2: TWENTIX Reference (Direct)
            is_twentix_a = asset_a_sym == "TWENTIX"
            is_twentix_b = asset_b_sym == "TWENTIX"
            
            if is_twentix_a:
                pool_tvl_usd = (balance_a * 2) * twentix_price
            elif is_twentix_b:
                pool_tvl_usd = (balance_b * 2) * twentix_price
            else:
                # Method 3: Indirect Reference via TWENTIX
                # Try to find a path: Asset A -> TWENTIX -> USD
                price_a_in_twentix = find_twentix_price_for_asset(asset_a_sym, pools)
                
                if price_a_in_twentix:
                     # Value of Asset A side in TWENTIX = Balance A * Price(A->TWENTIX)
                     val_a_in_twentix = balance_a * price_a_in_twentix
                     pool_tvl_usd = (val_a_in_twentix * 2) * twentix_price
                     # print(f"  > {label}: Indirect val via {asset_a_sym}->TWENTIX")
                else:
                    # Try Asset B
                    price_b_in_twentix = find_twentix_price_for_asset(asset_b_sym, pools)
                    if price_b_in_twentix:
                        val_b_in_twentix = balance_b * price_b_in_twentix
                        pool_tvl_usd = (val_b_in_twentix * 2) * twentix_price
                        # print(f"  > {label}: Indirect val via {asset_b_sym}->TWENTIX")
                    else:
                        print(f"  Warning: {label} has no Stablecoin, TWENTIX, or resolvable path. Skipping valuation.")
                        continue

        # User Share
        share_ratio = user_balance_total / total_supply
        user_value_usd = pool_tvl_usd * share_ratio
        
        print(f"{label:15} | Share: {share_ratio*100:6.4f}% | Pool TVL: ${pool_tvl_usd:12.2f} | Your Value: ${user_value_usd:10.2f}")
        
        pool_valuations.append({
            "pool": label,
            "share_percent": float(share_ratio * 100),
            "value_usd": float(user_value_usd)
        })
        
        total_portfolio_usd += user_value_usd

    print("-" * 60)
    print(f"{name.upper()} PORTFOLIO VALUE: ${total_portfolio_usd:,.2f}")
    print("-" * 60)
    
    # Save to CSV
    # Collect all possible pool labels from config to ensure full coverage
    all_pool_labels = [p["label"] for p in pools]
    
    final_headers = ensure_csv_headers(output_file, all_pool_labels)
    
    # Prepare row data
    row_data = {
        "Timestamp": datetime.datetime.now().isoformat(),
        "Accounts": ";".join(accounts),
        "Total Value USD": f"{total_portfolio_usd:.2f}"
    }
    
    for p_val in pool_valuations:
        p_label = p_val["pool"]
        p_val_usd = p_val['value_usd']
        
        if p_label in row_data:
            try:
                current_val = float(row_data[p_label])
                row_data[p_label] = f"{current_val + p_val_usd:.2f}"
            except ValueError:
                row_data[p_label] = f"{p_val_usd:.2f}"
        else:
            row_data[p_label] = f"{p_val_usd:.2f}"
    
    with open(output_file, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=final_headers)
        
        # Header if new file (or if we just created it but it's empty)
        if os.stat(output_file).st_size == 0:
            writer.writeheader()
            
        writer.writerow(row_data)
        print(f"Data saved to {output_file}")
        
    return total_portfolio_usd, pool_valuations

def main():
    settings = load_user_settings()
    accounts = settings.get("accounts", [])
    
    print(f"Starting Valuation Model at {datetime.datetime.now()}")
    print(f"Tracking Accounts: {', '.join(accounts)}")
    
    if not accounts:
        print("No accounts configured. Please check user_settings.json")
        return

    # Pre-fetch price if possible to ensure consistency across portfolios
    # We'll peek at the Core config for this
    print("\n--- Establishing Reference Price ---")
    try:
        with open("config_core.json", "r") as f:
            core_config = json.load(f)
            price = get_twentix_price_usd(core_config)
    except:
        price = None
        
    grand_total = Decimal(0)
    
    for p in PORTFOLIOS:
        val, _ = process_portfolio(p, price, accounts)
        if val:
            grand_total += val
            
    print("\n" + "=" * 60)
    print(f"GRAND TOTAL (ALL PORTFOLIOS): ${grand_total:,.2f}")
    print("=" * 60)

if __name__ == "__main__":
    main()
