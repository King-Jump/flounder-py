from typing import Dict, Optional, List, Tuple
from trading.models import Order, OrderType, OrderSide, OrderStatus, DepthData
import logging

logger = logging.getLogger(__name__)

class OrderManager:
    
    def __init__(self):
        self.orders: Dict[str, Order] = {}
    
    def create_order(self, symbol: str, order_type: OrderType, side: OrderSide,
                     quantity: float, price: Optional[float] = None) -> Order:
        order = Order(
            order_id="",
            symbol=symbol,
            order_type=order_type,
            side=side,
            price=price,
            quantity=quantity
        )
        self.orders[order.order_id] = order
        logger.debug(f"Created order: {order.order_id}")
        return order
    
    def get_order(self, order_id: str) -> Optional[Order]:
        return self.orders.get(order_id)
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        orders = [order for order in self.orders.values() if order.is_open]
        if symbol:
            orders = [order for order in orders if order.symbol == symbol]
        return orders
    
    def update_order(self, order_id: str, **kwargs) -> Optional[Order]:
        if order_id not in self.orders:
            return None
        order = self.orders[order_id]
        for key, value in kwargs.items():
            if hasattr(order, key):
                setattr(order, key, value)
        order.updated_at = int(__import__('datetime').datetime.now().timestamp() * 1000)
        return order
    
    def cancel_order(self, order_id: str) -> Optional[Order]:
        order = self.get_order(order_id)
        if not order or not order.is_open:
            return None
        order.status = OrderStatus.CANCELLED
        order.updated_at = int(__import__('datetime').datetime.now().timestamp() * 1000)
        logger.info(f"Order {order_id} cancelled")
        return order
    
    def get_all_orders(self) -> List[Order]:
        return list(self.orders.values())

class OrderMatcher:
    
    def __init__(self, order_manager: OrderManager):
        self.order_manager = order_manager
    
    def match_order(self, order: Order, depth: DepthData) -> Order:
        if order.order_type == OrderType.MARKET:
            return self._match_market_order(order, depth)
        elif order.order_type == OrderType.LIMIT:
            return self._match_limit_order(order, depth)
        return order
    
    def _match_market_order(self, order: Order, depth: DepthData) -> Order:
        remaining = order.remaining_quantity
        filled_price_sum = 0.0
        filled_count = 0
        
        if order.side == OrderSide.BUY:
            for ask_price, ask_quantity in depth.asks:
                if remaining <= 0:
                    break
                fill_quantity = min(remaining, ask_quantity)
                filled_price_sum += ask_price * fill_quantity
                filled_count += fill_quantity
                remaining -= fill_quantity
        else:
            for bid_price, bid_quantity in depth.bids:
                if remaining <= 0:
                    break
                fill_quantity = min(remaining, bid_quantity)
                filled_price_sum += bid_price * fill_quantity
                filled_count += fill_quantity
                remaining -= fill_quantity
        
        if filled_count > 0:
            order.filled_quantity += filled_count
            order.avg_fill_price = filled_price_sum / filled_count
        
        if remaining <= 0:
            order.status = OrderStatus.FILLED
        elif order.filled_quantity > 0:
            order.status = OrderStatus.PARTIALLY_FILLED
        
        order.updated_at = int(__import__('datetime').datetime.now().timestamp() * 1000)
        self.order_manager.update_order(order.order_id, **{k: v for k, v in vars(order).items() if k != 'order_id'})
        return order
    
    def _match_limit_order(self, order: Order, depth: DepthData) -> Order:
        if order.price is None:
            return order
        
        remaining = order.remaining_quantity
        filled_price_sum = 0.0
        filled_count = 0
        
        if order.side == OrderSide.BUY:
            for ask_price, ask_quantity in depth.asks:
                if ask_price > order.price or remaining <= 0:
                    break
                fill_quantity = min(remaining, ask_quantity)
                filled_price_sum += ask_price * fill_quantity
                filled_count += fill_quantity
                remaining -= fill_quantity
        else:
            for bid_price, bid_quantity in depth.bids:
                if bid_price < order.price or remaining <= 0:
                    break
                fill_quantity = min(remaining, bid_quantity)
                filled_price_sum += bid_price * fill_quantity
                filled_count += fill_quantity
                remaining -= fill_quantity
        
        if filled_count > 0:
            order.filled_quantity += filled_count
            if order.avg_fill_price is None:
                order.avg_fill_price = filled_price_sum / filled_count
            else:
                total_filled = order.filled_quantity
                order.avg_fill_price = (order.avg_fill_price * (total_filled - filled_count) + filled_price_sum) / total_filled
        
        if remaining <= 0:
            order.status = OrderStatus.FILLED
        elif order.filled_quantity > 0:
            order.status = OrderStatus.PARTIALLY_FILLED
        
        order.updated_at = int(__import__('datetime').datetime.now().timestamp() * 1000)
        self.order_manager.update_order(order.order_id, **{k: v for k, v in vars(order).items() if k != 'order_id'})
        return order
    
    def match_pending_orders(self, depth: DepthData) -> List[Order]:
        updated_orders = []
        pending_orders = self.order_manager.get_open_orders()
        for order in pending_orders:
            if order.order_type == OrderType.LIMIT:
                original_status = order.status
                self._match_limit_order(order, depth)
                if order.status != original_status:
                    updated_orders.append(order)
        return updated_orders
