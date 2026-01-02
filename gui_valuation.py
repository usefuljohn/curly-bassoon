import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import os
from decimal import Decimal
import valuation
from pool_data_handler import resolve_account_name

class PortfolioGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("BitShares Portfolio Valuation")
        self.root.geometry("800x650") # Slightly taller
        
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        
        # --- Settings Frame ---
        settings_frame = ttk.LabelFrame(root, text="Account Configuration", padding="10")
        settings_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(settings_frame, text="Account Names (comma separated):").pack(side=tk.LEFT)
        
        self.account_entry = ttk.Entry(settings_frame)
        self.account_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.save_btn = ttk.Button(settings_frame, text="Save & Scan", command=self.save_accounts)
        self.save_btn.pack(side=tk.LEFT)
        
        # Load initial settings into Entry
        self.current_settings = self.load_settings()
        initial_names = ", ".join(self.current_settings.get("account_names", []))
        self.account_entry.insert(0, initial_names)
        
        # --- Header ---
        header_frame = ttk.Frame(root, padding="10")
        header_frame.pack(fill=tk.X)
        
        title_label = ttk.Label(header_frame, text="Liquidity Pool Portfolio", font=("Helvetica", 16, "bold"))
        title_label.pack(side=tk.LEFT)
        
        self.refresh_btn = ttk.Button(header_frame, text="Refresh Data", command=self.start_refresh)
        self.refresh_btn.pack(side=tk.RIGHT)
        
        # --- Tabs ---
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=5)
        
        # USD Tab
        self.usd_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.usd_frame, text="USD Portfolio")
        self.usd_tree = self.create_treeview(self.usd_frame)
        
        # GROWTH Tab
        self.growth_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.growth_frame, text="GROWTH Portfolio")
        self.growth_tree = self.create_treeview(self.growth_frame)
        
        # --- Footer ---
        footer_frame = ttk.Frame(root, padding="10")
        footer_frame.pack(fill=tk.X)
        
        self.usd_total_label = ttk.Label(footer_frame, text="USD Total: $0.00", font=("Helvetica", 10))
        self.usd_total_label.pack(anchor=tk.W)
        
        self.growth_total_label = ttk.Label(footer_frame, text="GROWTH Total: $0.00", font=("Helvetica", 10))
        self.growth_total_label.pack(anchor=tk.W)
        
        ttk.Separator(footer_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        self.grand_total_label = ttk.Label(footer_frame, text="GRAND TOTAL: $0.00", font=("Helvetica", 14, "bold"))
        self.grand_total_label.pack(anchor=tk.E)
        
        # Status Bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def load_settings(self):
        settings_file = "user_settings.json"
        defaults = {"accounts": [], "account_names": []}
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r") as f:
                    return json.load(f)
            except:
                pass
        return defaults

    def save_accounts(self):
        raw_text = self.account_entry.get()
        names = [n.strip() for n in raw_text.split(",") if n.strip()]
        
        if not names:
            messagebox.showwarning("Input Error", "Please enter at least one account name.")
            return

        self.save_btn.config(state=tk.DISABLED)
        self.status_var.set("Resolving account names...")
        
        threading.Thread(target=self._resolve_and_save, args=(names,), daemon=True).start()

    def _resolve_and_save(self, names):
        resolved_ids = []
        valid_names = []
        failed_names = []

        for name in names:
            # Simple caching check could go here, but RPC is fast enough usually
            aid = resolve_account_name(name)
            if aid:
                resolved_ids.append(aid)
                valid_names.append(name)
            else:
                failed_names.append(name)
        
        if failed_names:
            msg = f"Could not find accounts: {', '.join(failed_names)}\nProceeding with valid ones."
            self.root.after(0, lambda: messagebox.showwarning("Account Lookup", msg))
        
        if not resolved_ids:
            self.root.after(0, lambda: self.finish_save([], [], "No valid accounts found."))
            return

        # Save to file
        settings = {
            "accounts": resolved_ids,
            "account_names": valid_names
        }
        
        try:
            with open("user_settings.json", "w") as f:
                json.dump(settings, f, indent=4)
            self.current_settings = settings
            self.root.after(0, lambda: self.finish_save(valid_names, resolved_ids, "Settings saved. Scanning..."))
        except Exception as e:
            self.root.after(0, lambda: self.finish_save([], [], f"Error saving settings: {e}"))

    def finish_save(self, valid_names, ids, status_msg):
        self.save_btn.config(state=tk.NORMAL)
        self.status_var.set(status_msg)
        
        # Update entry with valid names only to keep it clean
        if valid_names:
             self.account_entry.delete(0, tk.END)
             self.account_entry.insert(0, ", ".join(valid_names))
             # Trigger refresh immediately
             self.start_refresh()

    def create_treeview(self, parent):
        cols = ("Pool", "Share %", "Pool TVL", "Your Value")
        tree = ttk.Treeview(parent, columns=cols, show='headings')
        
        for col in cols:
            tree.heading(col, text=col, command=lambda _col=col: self.treeview_sort_column(tree, _col, False))
            tree.column(col, width=150)
            
        tree.column("Pool", width=200)
        tree.column("Share %", width=100, anchor=tk.CENTER)
        tree.column("Pool TVL", width=150, anchor=tk.E)
        tree.column("Your Value", width=150, anchor=tk.E)
        
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        return tree

    def treeview_sort_column(self, tv, col, reverse):
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        
        try:
            # Clean data for sorting (remove $, %, ,)
            def clean_val(val):
                v = val.replace('$', '').replace('%', '').replace(',', '').strip()
                return float(v) if v else 0.0
            
            l.sort(key=lambda t: clean_val(t[0]), reverse=reverse)
        except ValueError:
            # Fallback to string sort
            l.sort(reverse=reverse)

        # Rearrange items in sorted positions
        for index, (val, k) in enumerate(l):
            tv.move(k, '', index)

        # Reverse sort next time
        tv.heading(col, command=lambda: self.treeview_sort_column(tv, col, not reverse))

    def start_refresh(self):
        self.refresh_btn.config(state=tk.DISABLED)
        self.status_var.set("Fetching data from BitShares blockchain...")
        
        # Clear existing data
        for row in self.usd_tree.get_children():
            self.usd_tree.delete(row)
        for row in self.growth_tree.get_children():
            self.growth_tree.delete(row)
            
        thread = threading.Thread(target=self.run_valuation)
        thread.daemon = True
        thread.start()

    def run_valuation(self):
        try:
            # Re-use logic from valuation.py
            
            # Get Accounts from settings
            accounts = self.current_settings.get("accounts", [])
            if not accounts:
                 self.root.after(0, lambda: self.finish_refresh("No accounts configured."))
                 return

            # 1. Get Price
            try:
                with open("config_core.json", "r") as f:
                    core_config = json.load(f)
                    price = valuation.get_twentix_price_usd(core_config)
            except Exception as e:
                print(f"Config error: {e}")
                price = None
                
            grand_total = Decimal(0)
            usd_total = Decimal(0)
            growth_total = Decimal(0)
            
            # 2. Process Portfolios
            for p in valuation.PORTFOLIOS:
                # p is {"name": "USD", ...}
                total_val, details = valuation.process_portfolio(p, price, accounts)
                
                if total_val:
                    grand_total += total_val
                    
                    if p["name"] == "USD":
                        usd_total = total_val
                        self.update_tree(self.usd_tree, details)
                    elif p["name"] == "GROWTH":
                        growth_total = total_val
                        self.update_tree(self.growth_tree, details)
            
            # 3. Update UI Labels
            self.root.after(0, lambda: self.update_labels(usd_total, growth_total, grand_total))
            self.root.after(0, lambda: self.finish_refresh("Data Updated Successfully"))
            
        except Exception as e:
            self.root.after(0, lambda: self.finish_refresh(f"Error: {str(e)}"))

    def update_tree(self, tree, data):
        # Schedule the UI update on the main thread
        def _update():
            for item in data:
                tree.insert("", tk.END, values=(
                    item["pool"],
                    f"{item['share_percent']:.4f}%",
                    f"${Decimal(item['value_usd']) / (Decimal(item['share_percent'])/100) if item['share_percent'] > 0 else 0:,.2f}", # Reverse calc TVL or pass it? 
                    # Actually details doesn't pass TVL directly, let's just use the value
                    f"${item['value_usd']:,.2f}"
                ))
        self.root.after(0, _update)

    def update_labels(self, usd, growth, grand):
        self.usd_total_label.config(text=f"USD Total: ${usd:,.2f}")
        self.growth_total_label.config(text=f"GROWTH Total: ${growth:,.2f}")
        self.grand_total_label.config(text=f"GRAND TOTAL: ${grand:,.2f}")

    def finish_refresh(self, message):
        self.status_var.set(message)
        self.refresh_btn.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = PortfolioGUI(root)
    root.mainloop()
