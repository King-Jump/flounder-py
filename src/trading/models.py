from enum import Enum
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
import uuid
from datetime import datetime

class OrderType(Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(Enum):
    NEW = "NEW"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"

@dataclass
class Order:
    order_id: str
    symbol: str
    order_type: OrderType
    side: OrderSide
    price: Optional[float]
    quantity: float
    filled_quantity: float = 0.0
    avg_fill_price: Optional[float] = None
    status: OrderStatus = OrderStatus.NEW
    created_at: int = 0
    updated_at: int = 0
    
    def __post_init__(self):
        if not self.order_id:
            self.order_id = str(uuid.uuid4())
        if self.created_at == 0:
            self.created_at = int(datetime.now().timestamp() * 1000)
        self.updated_at = self.created_at
    
    @property
    def remaining_quantity(self) -> float:
        return self.quantity - self.filled_quantity
    
    @property
    def is_open(self) -> bool:
        return self.status in (OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED)

@dataclass
class DepthData:
    symbol: str
    bids: List[Tuple[float, float]]
    asks: List[Tuple[float, float]]
    timestamp: int = 0
    
    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = int(datetime.now().timestamp() * 1000)
        self.bids = sorted(self.bids, key=lambda x: -x[0])
        self.asks = sorted(self.asks, key=lambda x: x[0])
    
    @property
    def best_bid(self) -> float:
        return self.bids[0][0] if self.bids else 0.0
    
    @property
    def best_ask(self) -> float:
        return self.asks[0][0] if self.asks else 0.0
    
    @property
    def mid_price(self) -> float:
        return (self.best_bid + self.best_ask) / 2 if self.best_bid and self.best_ask else 0.0

@dataclass
class Balance:
    asset: str
    free: float = 0.0
    locked: float = 0.0
    
    @property
    def total(self) -> float:
        return self.free + self.locked

@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_cost: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    @property
    def is_long(self) -> bool:
        return self.quantity > 0
    
    @property
    def is_short(self) -> bool:
        return self.quantity < 0

@dataclass
class Account:
    account_id: str
    balances: Dict[str, Balance]
    initial_balance: float = 10000.0
    created_at: int = 0
    
    def __post_init__(self):
        if not self.account_id:
            self.account_id = str(uuid.uuid4())
        if self.created_at == 0:
            self.created_at = int(datetime.now().timestamp() * 1000)
        if "USDT" not in self.balances:
            self.balances["USDT"] = Balance("USDT", free=self.initial_balance)
    
    def get_balance(self, asset: str) -> Optional[Balance]:
        return self.balances.get(asset)
    
    def update_balance(self, asset: str, free_change: float = 0.0, locked_change: float = 0.0):
        if asset not in self.balances:
            self.balances[asset] = Balance(asset)
        self.balances[asset].free += free_change
        self.balances[asset].locked += locked_change
