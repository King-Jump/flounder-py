from strategy.engine import TradingStrategy
from trading.models import DepthData, Order, OrderType, OrderSide

class SimpleMovingAverageStrategy(TradingStrategy):
    
    def __init__(self, window_size: int = 50):
        self.name = "SimpleMovingAverageStrategy"
        self.window_size = window_size
        self.price_history = []
        self.position = 0
    
    def getName(self) -> str:
        return self.name
    
    def onDepthUpdate(self, depth: DepthData) -> None:
        self.price_history.append(depth.mid_price)
        
        if len(self.price_history) > self.window_size:
            self.price_history = self.price_history[-self.window_size:]
        
        if len(self.price_history) >= self.window_size:
            sma = sum(self.price_history) / len(self.price_history)
            current_price = depth.mid_price
            
            if current_price > sma and self.position <= 0:
                self._place_buy_order(depth.symbol, 0.001)
                self.position = 1
            elif current_price < sma and self.position >= 0:
                self._place_sell_order(depth.symbol, 0.001)
                self.position = -1
    
    def onOrderUpdate(self, order: Order) -> None:
        pass
    
    def _place_buy_order(self, symbol: str, quantity: float):
        if hasattr(self, 'trading_service'):
            self.trading_service.place_order(
                symbol=symbol,
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=quantity
            )
    
    def _place_sell_order(self, symbol: str, quantity: float):
        if hasattr(self, 'trading_service'):
            self.trading_service.place_order(
                symbol=symbol,
                order_type=OrderType.MARKET,
                side=OrderSide.SELL,
                quantity=quantity
            )

class GridTradingStrategy(TradingStrategy):
    
    def __init__(self, grid_count: int = 5, grid_range: float = 0.02):
        self.name = "GridTradingStrategy"
        self.grid_count = grid_count
        self.grid_range = grid_range
        self.base_price = None
        self.grid_levels = []
        self.position_level = 0
    
    def getName(self) -> str:
        return self.name
    
    def onDepthUpdate(self, depth: DepthData) -> None:
        current_price = depth.mid_price
        
        if self.base_price is None:
            self.base_price = current_price
            self._initialize_grid()
        
        current_level = self._get_current_level(current_price)
        
        if current_level > self.position_level:
            for i in range(self.position_level + 1, current_level + 1):
                if i <= self.grid_count:
                    self._place_buy_order(depth.symbol, 0.001)
            self.position_level = current_level
        elif current_level < self.position_level:
            for i in range(self.position_level, current_level, -1):
                if i > 0:
                    self._place_sell_order(depth.symbol, 0.001)
            self.position_level = current_level
    
    def onOrderUpdate(self, order: Order) -> None:
        pass
    
    def _initialize_grid(self):
        grid_interval = self.base_price * self.grid_range / self.grid_count
        self.grid_levels = [self.base_price - i * grid_interval for i in range(self.grid_count + 1)]
    
    def _get_current_level(self, price: float) -> int:
        for i, level in enumerate(self.grid_levels):
            if price >= level:
                return i
        return 0
    
    def _place_buy_order(self, symbol: str, quantity: float):
        if hasattr(self, 'trading_service'):
            self.trading_service.place_order(
                symbol=symbol,
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=quantity
            )
    
    def _place_sell_order(self, symbol: str, quantity: float):
        if hasattr(self, 'trading_service'):
            self.trading_service.place_order(
                symbol=symbol,
                order_type=OrderType.MARKET,
                side=OrderSide.SELL,
                quantity=quantity
            )

class RsiStrategy(TradingStrategy):
    
    def __init__(self, window_size: int = 14, oversold: int = 30, overbought: int = 70):
        self.name = "RsiStrategy"
        self.window_size = window_size
        self.oversold = oversold
        self.overbought = overbought
        self.price_history = []
        self.position = 0
    
    def getName(self) -> str:
        return self.name
    
    def onDepthUpdate(self, depth: DepthData) -> None:
        self.price_history.append(depth.mid_price)
        
        if len(self.price_history) > self.window_size + 1:
            self.price_history = self.price_history[-(self.window_size + 1):]
        
        if len(self.price_history) >= self.window_size + 1:
            rsi = self._calculate_rsi()
            
            if rsi < self.oversold and self.position <= 0:
                self._place_buy_order(depth.symbol, 0.001)
                self.position = 1
            elif rsi > self.overbought and self.position >= 0:
                self._place_sell_order(depth.symbol, 0.001)
                self.position = -1
    
    def onOrderUpdate(self, order: Order) -> None:
        pass
    
    def _calculate_rsi(self) -> float:
        deltas = [self.price_history[i] - self.price_history[i-1] 
                  for i in range(1, len(self.price_history))]
        
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        
        avg_gain = sum(gains) / self.window_size if gains else 0
        avg_loss = sum(losses) / self.window_size if losses else 0
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _place_buy_order(self, symbol: str, quantity: float):
        if hasattr(self, 'trading_service'):
            self.trading_service.place_order(
                symbol=symbol,
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=quantity
            )
    
    def _place_sell_order(self, symbol: str, quantity: float):
        if hasattr(self, 'trading_service'):
            self.trading_service.place_order(
                symbol=symbol,
                order_type=OrderType.MARKET,
                side=OrderSide.SELL,
                quantity=quantity
            )
