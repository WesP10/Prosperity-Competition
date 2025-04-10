from typing import Dict, List
# from data.datamodel import OrderDepth, TradingState, Order
from datamodel import OrderDepth, TradingState, Order
import math

SUBMISSION = "SUBMISSION"
RAINFOREST_RESIN = "RAINFOREST_RESIN"
SQUID_INK = "SQUID_INK"
KELP = "KELP"

PRODUCTS = [RAINFOREST_RESIN, SQUID_INK, KELP]

DEFAULT_VALUES = {
  RAINFOREST_RESIN: 10000,
  # Only use resin rn
  SQUID_INK: 2000,
  KELP: 2000,
}

class Trader:

    def __init__(self) -> None:
        self.position_limit = {
            RAINFOREST_RESIN : 50,
            SQUID_INK : 50,
            KELP : 50,
        }

        self.round = 0

        # Values to compute pnl
        self.cash = 0
        # positions can be obtained from state.position
        
        # self.past_prices keeps the list of all past prices
        self.past_prices = dict()
        for product in PRODUCTS:
            self.past_prices[product] = []

        # self.ema_prices keeps an exponential moving average of prices
        self.ema_prices = dict()
        for product in PRODUCTS:
            self.ema_prices[product] = None

        self.ema_param = {
            SQUID_INK: 0.0115,      # 60 tick half-life
            RAINFOREST_RESIN: 0.0228,  # 30 tick half-life
            KELP: 0.0451,           # 15 tick half-life
        }

        # Rolling window sizes (in tick units)
        self.RSI_WINDOW_TICKS = 50   # change to whatever is best profit
        self.PCR_WINDOW_TICKS = 50   # change to whatever is best profit

        # Add these new parameters for dynamic spread calculation
        self.volatility_window = 50  # Number of ticks to look back for volatility
        self.min_spread = 1  # Minimum spread to maintain
        self.max_spread = 5  # Maximum spread to allow
        self.spread_multiplier = 2.0  # Multiplier for volatility-based spread

        # Add position target parameters
        self.target_position = 15  # Target position to maintain
        self.position_penalty_factor = 0.1  # How much to adjust prices based on position deviation

        # Add volatility threshold parameter
        self.volatility_threshold = 3.0  # Adjust this value based on testing
        self.volatility_cooldown = 5  # Number of ticks to wait after high volatility
        self.last_high_volatility_tick = -1  # Initialize the tracking variable
        self.high_volatility_price = None  # Price when high volatility was detected
        self.high_volatility_direction = None  # 'up' or 'down' based on price movement
        self.high_volatility_position = 0  # Position we took during high volatility

        self.volatility = 0.0  # Initialize volatility variable

    def get_position(self, product, state : TradingState):
        return state.position.get(product, 0)    

    def get_mid_price(self, product, state : TradingState):

        default_price = self.ema_prices[product]
        if default_price is None:
            default_price = DEFAULT_VALUES[product]

        if product not in state.order_depths:
            return default_price

        market_bids = state.order_depths[product].buy_orders
        if len(market_bids) == 0:
            # There are no bid orders in the market (midprice undefined)
            return default_price
        
        market_asks = state.order_depths[product].sell_orders
        if len(market_asks) == 0:
            # There are no bid orders in the market (mid_price undefined)
            return default_price
        
        best_bid = max(market_bids)
        best_ask = min(market_asks)
        return (best_bid + best_ask)/2

    def get_value_on_product(self, product, state : TradingState):
        """
        Returns the amount of MONEY currently held on the product.  
        """
        return self.get_position(product, state) * self.get_mid_price(product, state)
            
    def update_pnl(self, state : TradingState):
        """
        Updates the pnl.
        """
        def update_cash():
            # Update cash
            for product in state.own_trades:
                for trade in state.own_trades[product]:
                    if trade.timestamp != state.timestamp - 100:
                        # Trade was already analyzed
                        continue

                    if trade.buyer == SUBMISSION:
                        self.cash -= trade.quantity * trade.price
                    if trade.seller == SUBMISSION:
                        self.cash += trade.quantity * trade.price
        
        def get_value_on_positions():
            value = 0
            for product in state.position:
                value += self.get_value_on_product(product, state)
            return value
        
        # Update cash
        update_cash()
        return self.cash + get_value_on_positions()

    def update_price_history(self, current_timestamp: int, price: float, product) -> None:
        """Append the current (timestamp, price) and prune any too-old data."""
        self.past_prices[product].append((current_timestamp, price))
        # Prune history older than the maximum window needed for our indicators.
        max_window = max(self.RSI_WINDOW_TICKS, self.PCR_WINDOW_TICKS)
        self.past_prices[product] = [(ts, p) for ts, p in self.past_prices[KELP] if current_timestamp - ts <= max_window]

    def compute_modified_rsi(self, current_timestamp: int, current_price: float, product):
        """
        Compute modified RSI as percentage change compared to the price from
        RSI_WINDOW_TICKS ago.
        """
        target_time = current_timestamp - self.RSI_WINDOW_TICKS
        price_old = None
        # Look for the oldest price at or before the target_time.
        for ts, p in self.past_prices[product]:
            if ts <= target_time:
                price_old = p
            else:
                break
        if price_old is None:
            return None
        return (current_price - price_old) / price_old * 100

    def compute_pcr(self, current_timestamp: int, product):
        """
        Compute the Price Change Ratio (PCR) over the PCR_WINDOW_TICKS.
        PCR = up_moves / (up_moves + down_moves)
        """
        window_start = current_timestamp - self.PCR_WINDOW_TICKS
        window_prices = [p for ts, p in self.past_prices[product] if ts >= window_start]
        if len(window_prices) < 2:
            return None
        up_moves = 0
        down_moves = 0
        for i in range(1, len(window_prices)):
            if window_prices[i] > window_prices[i - 1]:
                up_moves += 1
            elif window_prices[i] < window_prices[i - 1]:
                down_moves += 1
        total_moves = up_moves + down_moves
        if total_moves == 0:
            return 0.5  # Neutral if no movement
        return up_moves / total_moves

    def generate_signal(self, current_timestamp: int, current_price: float, product) -> str:
        """
        Combine modified RSI and PCR indicators to produce a trading signal.
          - 'buy' if RSI < 30 and PCR > 0.7
          - 'sell' if RSI > 70 and PCR < 0.3
          - otherwise, 'hold'
        """
        rsi_value = self.compute_modified_rsi(current_timestamp, current_price, product)
        pcr_value = self.compute_pcr(current_timestamp, product)
        if rsi_value is None or pcr_value is None:
            return "hold"

        rsi_buy_threshold = 30
        rsi_sell_threshold = 70
        pcr_bullish_threshold = 0.7
        pcr_bearish_threshold = 0.3

        if rsi_value < rsi_buy_threshold and pcr_value > pcr_bullish_threshold:
            return "buy"
        elif rsi_value > rsi_sell_threshold and pcr_value < pcr_bearish_threshold:
            return "sell"
        else:
            return "hold"

    def update_ema_prices(self, state : TradingState):
        """
        Update the exponential moving average of the prices of each product.
        """
        for product in PRODUCTS:
            mid_price = self.get_mid_price(product, state)
            if mid_price is None:
                continue

            # Update ema price
            if self.ema_prices[product] is None:
                self.ema_prices[product] = mid_price
            else:
                self.ema_prices[product] = self.ema_param[product] * mid_price + (1-self.ema_param[product]) * self.ema_prices[product]

    def calculate_volatility(self, product: str, state: TradingState) -> float:
        """
        Calculate the volatility of a product based on recent price movements.
        Returns the standard deviation of recent price changes.
        """
        if len(self.past_prices[product]) < 2:
            return 0.0
        
        # Get recent prices within the volatility window
        recent_prices = [p for ts, p in self.past_prices[product][-self.volatility_window:]]
        
        if len(recent_prices) < 2:
            return 0.0
        
        # Calculate price changes
        price_changes = [abs(recent_prices[i] - recent_prices[i-1]) 
                        for i in range(1, len(recent_prices))]
        
        # Calculate standard deviation of price changes
        mean = sum(price_changes) / len(price_changes)
        variance = sum((x - mean) ** 2 for x in price_changes) / len(price_changes)
        return math.sqrt(variance) * 100

    def squid_strategy(self, state : TradingState) -> List[Order]:
        """
        Market-making Strategy for SQUID_INK with volatility-based trading
        """
        position_squid = self.get_position(SQUID_INK, state)
        self.volatility = self.calculate_volatility(SQUID_INK, state)

        current_price = self.get_mid_price(KELP, state)
        self.update_price_history(state.timestamp, current_price, KELP)

        position_kelp = self.get_position(KELP, state)
        signal = self.generate_signal(state.timestamp, current_price, KELP)

        bid_volume = self.position_limit[SQUID_INK] - position_squid
        ask_volume = - self.position_limit[SQUID_INK] - position_squid

        orders = []

        if signal == "buy":
            orders.append(Order(SQUID_INK, math.floor(self.ema_prices[SQUID_INK] - 1), bid_volume))
        elif signal == "sell": 
            orders.append(Order(SQUID_INK, math.ceil(self.ema_prices[SQUID_INK] + 1), ask_volume))
        else:
            # In a neutral case, place orders on both sides.
            orders.append(Order(SQUID_INK, math.floor(self.ema_prices[SQUID_INK] - 1), bid_volume))
            orders.append(Order(SQUID_INK, math.ceil(self.ema_prices[SQUID_INK] + 1), ask_volume))

        # if position_squid == 0:
        #     # Not long nor short
        #     orders.append(Order(SQUID_INK, math.floor(self.ema_prices[SQUID_INK] - 1), bid_volume))
        #     orders.append(Order(SQUID_INK, math.ceil(self.ema_prices[SQUID_INK] + 1), ask_volume))
        
        # if position_squid > 0:
        #     # Long position
        #     orders.append(Order(SQUID_INK, math.floor(self.ema_prices[SQUID_INK] - 2), bid_volume))
        #     orders.append(Order(SQUID_INK, math.ceil(self.ema_prices[SQUID_INK]), ask_volume))

        # if position_squid < 0:
        #     # Short position
        #     orders.append(Order(SQUID_INK, math.floor(self.ema_prices[SQUID_INK]), bid_volume))
        #     orders.append(Order(SQUID_INK, math.ceil(self.ema_prices[SQUID_INK] + 2), ask_volume))

        return orders

    def resin_strategy(self, state : TradingState) -> List[Order]:
        """
        Market-Making Strategy for RAINFOREST_RESIN (Stable)
        """
        orders: list[Order] = []
        order_depth: OrderDepth = state.order_depths[RAINFOREST_RESIN]

        position_pearls = self.get_position(RAINFOREST_RESIN, state)

        bid_volume = self.position_limit[RAINFOREST_RESIN] - position_pearls
        ask_volume = - self.position_limit[RAINFOREST_RESIN] - position_pearls

        orders = []
        orders.append(Order(RAINFOREST_RESIN, DEFAULT_VALUES[RAINFOREST_RESIN] - 1, bid_volume))
        orders.append(Order(RAINFOREST_RESIN, DEFAULT_VALUES[RAINFOREST_RESIN] + 1, ask_volume))

        return orders

    def kelp_strategy(self, state : TradingState) -> List[Order]:
        """
        EMA Strategy for KELP (Mildly Volatile)
        """
        current_price = self.get_mid_price(KELP, state)
        self.update_price_history(state.timestamp, current_price, KELP)

        position_kelp = self.get_position(KELP, state)
        signal = self.generate_signal(state.timestamp, current_price, KELP)

        orders = []
        bid_volume = self.position_limit[KELP] - position_kelp
        ask_volume = -self.position_limit[KELP] - position_kelp

        # Use the EMA value as the reference price.
        if signal == "buy":
            orders.append(Order(KELP, math.floor(self.ema_prices[KELP] - 1), bid_volume))
        elif signal == "sell":
            orders.append(Order(KELP, math.ceil(self.ema_prices[KELP] + 1), ask_volume))
        else:
            # In a neutral case, place orders on both sides.
            orders.append(Order(KELP, math.floor(self.ema_prices[KELP] - 1), bid_volume))
            orders.append(Order(KELP, math.ceil(self.ema_prices[KELP] + 1), ask_volume))
        return orders

    def run(self, state: TradingState) -> Dict[str, List[Order]]:
        """
        Only method required. It takes all buy and sell orders for all symbols as an input,
        and outputs a list of orders to be sent
        """
        self.round += 1
        pnl = self.update_pnl(state)
        self.update_ema_prices(state)

        print(f"Log round {self.round}")

        print("TRADES:")
        for product in state.own_trades:
            for trade in state.own_trades[product]:
                if trade.timestamp == state.timestamp - 100:
                    print(trade)

        print(f"Cash {self.cash}")
        for product in PRODUCTS:
            print(f" Product {product}, Position {self.get_position(product, state)}, Midprice {self.get_mid_price(product, state)}, Value {self.get_value_on_product(product, state)}, EMA {self.ema_prices[product]}, Volatility {self.volatility}")
        print(f" PnL {pnl}")
        
        result = {}

        # SQUID_INK STRATEGY
        try:
            result[SQUID_INK] = self.squid_strategy(state)
        except Exception as e:
            print("Error in squid strategy")
            print(e)

        # # RAINFOREST_RESIN STRATEGY
        # try:
        #     result[RAINFOREST_RESIN] = self.resin_strategy(state)
        # except Exception as e:
        #     print("Error in resin strategy")
        #     print(e)

        # KELP STRATEGY
        try:
            result[KELP] = self.kelp_strategy(state)
        except Exception as e:
            print("Error in kelp strategy")
            print(e)
                
        traderData = state.traderData + "1"
        traderData = 'WACK'
        
        conversions = 1 

        return result, conversions, traderData
    
