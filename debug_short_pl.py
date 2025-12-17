
from database import get_portfolio_summary, init_db

# データベース初期化
init_db()

# ポートフォリオ取得
summary = get_portfolio_summary()

# 5016.T (JX金属) のデータを特定
target = next((p for p in summary if "5016" in p['ticker']), None)

if target:
    print(f"=== DB Data for {target['ticker']} ===")
    print(f"Qty: {target['total_quantity']} ({type(target['total_quantity'])})")
    print(f"PositionType: {target.get('position_type')} (Raw)")
    print(f"AvgPrice: {target['avg_price']}")
    
    # app.py logic simulation
    ticker = target['ticker']
    quantity = target['total_quantity']
    avg_price = float(target['avg_price'])
    # Force Mock Price from Screenshot
    current_price = 1728.5
    
    position_type = target.get('position_type', 'long')
    
    abs_quantity = abs(quantity)
    
    if position_type == 'long':
        print(f"Logic Path: LONG")
        profit_loss = (current_price - avg_price) * abs_quantity
    else:
        print(f"Logic Path: SHORT")
        profit_loss = (avg_price - current_price) * abs_quantity
        
    print(f"Calculated PL: {profit_loss}")
    
    # Check if calculation matches +1300
    if abs(profit_loss - 1300) < 1:
        print("MATCHED ERROR (+1300). Logic is producing LONG result for SHORT data.")
    elif abs(profit_loss - (-1300)) < 1:
        print("Result is CORRECT (-1300). app.py logic on disk is correct.")
    else:
        print(f"Result is WEIRD. Expected -1300 or +1300.")
else:
    print("5016.T not found in portfolio.")
