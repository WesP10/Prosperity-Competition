from typing import Dict, List
from datamodel import OrderDepth, TradingState, Order
# from data.datamodel import OrderDepth, TradingState, Order

class Trader:

    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        """
        Only method required. It takes all buy and sell orders for all symbols as an input,
        and outputs a list of orders to be sent
        """
        result = {}
        print("Saved Data", state.traderData)

        for product in state.order_depths.keys():
                if product != 'RAINFOREST_RESIN':
                    continue
                order_depth: OrderDepth = state.order_depths[product]
                orders: list[Order] = []
                acceptable_buy_price = calculate_acceptable_buy_price(product, order_depth)
                acceptable_sell_price = calculate_acceptable_sell_price(product, order_depth)

                if len(order_depth.sell_orders) > 0:
                    best_ask = min(order_depth.sell_orders.keys())
                    best_ask_volume = order_depth.sell_orders[best_ask]
                    if best_ask < acceptable_sell_price:
                        print("BUY", str(-best_ask_volume) + "x", best_ask)
                        orders.append(Order(product, best_ask, -best_ask_volume))

                if len(order_depth.buy_orders) != 0:
                    best_bid = max(order_depth.buy_orders.keys())
                    best_bid_volume = order_depth.buy_orders[best_bid]
                    if best_bid > acceptable_buy_price:
                        print("SELL", str(best_bid_volume) + "x", best_bid)
                        orders.append(Order(product, best_bid, -best_bid_volume))

                result[product] = orders
                
        traderData = state.traderData + "1"
        traderData = 'WACK'
        
        conversions = 1 

        return result, conversions, traderData

def calculate_acceptable_buy_price(product, order_depth, lastPosition):
    """
    Calculate the acceptable buy price for a given product and order depth.
    """
    # If market is stable, we can use current order book to determine acceptable price    
    # Get weighted average of current bids and asks
    bid_total = 0
    bid_volume = 0
    for price, volume in order_depth.buy_orders.items():
        bid_total += price * abs(volume)
        bid_volume += abs(volume)
    
    ask_total = 0 
    ask_volume = 0
    for price, volume in order_depth.sell_orders.items():
        ask_total += price * abs(volume)
        ask_volume += abs(volume)

    # Calculate volume weighted average prices
    vwap_bid = bid_total / bid_volume if bid_volume > 0 else 0
    vwap_ask = ask_total / ask_volume if ask_volume > 0 else 0
    
    # Set acceptable buy price slightly below midpoint
    if vwap_bid > 0 and vwap_ask > 0:
        midpoint = (vwap_bid + vwap_ask) / 2
        return midpoint * 0.99  # Buy slightly below midpoint
    elif vwap_ask > 0:
        return vwap_ask * 0.98  # If no bids, use ask price with bigger discount
    elif vwap_bid > 0:
        return vwap_bid * 0.99  # If no asks, use bid price with small discount
    else:
        return 0  # No orders in book
    
def calculate_acceptable_sell_price(product, order_depth, lastPosition):
    """
    Calculate the acceptable sell price for a given product and order depth.
    """
    # If market is stable, we can use current order book to determine acceptable price    
    # Get weighted average of current bids and asks
    bid_total = 0
    bid_volume = 0
    for price, volume in order_depth.buy_orders.items():
        bid_total += price * abs(volume)
        bid_volume += abs(volume)
    ask_total = 0
    ask_volume = 0
    for price, volume in order_depth.sell_orders.items():
        ask_total += price * abs(volume)
        ask_volume += abs(volume)
    # Calculate volume weighted average prices
    vwap_bid = bid_total / bid_volume if bid_volume > 0 else 0
    vwap_ask = ask_total / ask_volume if ask_volume > 0 else 0
    # Set acceptable sell price slightly above midpoint
    if vwap_bid > 0 and vwap_ask > 0:
        midpoint = (vwap_bid + vwap_ask) / 2
        return midpoint * 1.01  # Sell slightly above midpoint
    elif vwap_bid > 0:
        return vwap_bid * 1.02  # If no asks, use bid price with bigger premium
    elif vwap_ask > 0:
        return vwap_ask * 1.01  # If no bids, use ask price with small premium
    else:
        return 0  # No orders in book
    