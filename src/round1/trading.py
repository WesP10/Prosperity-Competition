from typing import Dict, List
from data.datamodel import OrderDepth, TradingState, Order
import json


class Trader:

    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        """
        Only method required. It takes all buy and sell orders for all symbols as an input,
        and outputs a list of orders to be sent
        """
        result = {}
        print("Saved Data", state.traderData)

        for product in state.order_depths.keys():
            order_depth: OrderDepth = state.order_depths[product]
            orders: list[Order] = []
            if product == 'RAINFOREST_RESIN':
                add_resin_orders(orders, order_depth)
            elif product == 'KELP':
                add_kelp_orders(orders, order_depth)
            elif product == 'SQUID_INK':
                add_squid_orders(orders, order_depth)
            result[product] = orders
                
        traderData = state.traderData + "1"
        traderData = 'WACK'
        
        conversions = 1 

        return result, conversions, traderData
    


def add_resin_orders(orders, order_depth):
    pass

def add_kelp_orders(orders, order_depth):
    pass

def add_squid_orders(orders, order_depth):
    pass