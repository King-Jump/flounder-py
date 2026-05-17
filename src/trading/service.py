import logging
import time
from typing import Optional
from trading.config import Config
from trading.models import OrderType, OrderSide, DepthData, Order
from strategy.engine import StrategyEngine
from matcher.engine import OrderManager, OrderMatcher
from account.manager import AccountManager
from pnl.tracker import PnLTracker, PnLChart
from ws.connector import BinanceWsConnector, MarketDataProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

class TradingService:
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.order_manager = OrderManager()
        self.order_matcher = OrderMatcher(self.order_manager)
        self.account_manager = AccountManager(self.config)
        self.pnl_tracker = PnLTracker(self.account_manager, self.config.INITIAL_BALANCE)
        self.pnl_chart = PnLChart(self.pnl_tracker)
        self.strategy_engine = StrategyEngine()
        self.market_data_processor = MarketDataProcessor()
        self.ws_connector = BinanceWsConnector(
            symbol=self.config.SYMBOL,
            depth_level=self.config.DEPTH_LEVEL
        )
        
        self.account_manager.create_account(self.config.INITIAL_BALANCE)
        
        self.ws_connector.on_depth_update = self._on_depth_update
        
        self.last_pnl_update = 0
    
    def _on_depth_update(self, depth: DepthData):
        """ on depth update, match open orders by depth data, then update pnl and strategy
        """
        processed_depth = self.market_data_processor.process_depth_update(depth)
        
        pending_orders = self.order_manager.get_open_orders()
        for order in pending_orders:
            if order.order_type == OrderType.LIMIT:
                self.order_matcher.match_order(order, processed_depth)
        
        now = depth.timestamp
        if now - self.last_pnl_update >= self.config.PNL_UPDATE_INTERVAL:
            self.pnl_tracker.update_pnl(processed_depth)
            self.last_pnl_update = now
        
        self.strategy_engine.on_depth_update(processed_depth)
        
        self._check_order_updates()
    
    def _check_order_updates(self):
        for order in self.order_manager.get_filled_orders():
            self.pnl_tracker.record_trade_pnl(order)
            self.strategy_engine.on_order_update(order)
    
    def place_order(self, symbol: str, order_type: OrderType, side: OrderSide,
                    quantity: float, price: float = None) -> Optional[Order]:
        base_asset = symbol[:-4]
        quote_asset = "USDT"
        
        match_price = self.market_data_processor.get_best_ask() if order_type == OrderType.MARKET else price
        # check balance and update balance
        if side == OrderSide.BUY:
            total_cost = quantity * match_price * (1 + self.config.COMMISSION_RATE)
            if not self.account_manager.check_balance("default", quote_asset, total_cost):
                logger.error("Insufficient balance for buy order")
                return
            self.account_manager.update_balance("default", quote_asset, locked_change=total_cost)
        else:
            if not self.account_manager.check_balance("default", base_asset, quantity):
                logger.error("Insufficient balance for sell order")
                return
            self.account_manager.update_balance("default", base_asset, locked_change=quantity)
        
        order = self.order_manager.create_order(symbol, order_type, side, quantity, price)
        return order
    
    def cancel_order(self, order_id: str) -> Optional[Order]:
        order = self.order_manager.cancel_order(order_id)
        if order:
            base_asset = order.symbol[:-4]
            quote_asset = "USDT"
            
            if order.side == OrderSide.BUY:
                remaining = order.remaining_quantity
                price = order.price or self.market_data_processor.get_best_ask()
                cost = remaining * price * (1 + self.config.COMMISSION_RATE)
                self.account_manager.update_balance("default", quote_asset, locked_change=-cost)
            else:
                self.account_manager.update_balance("default", base_asset, locked_change=-order.remaining_quantity)
        
        return order
    
    def get_order(self, order_id: str):
        return self.order_manager.get_order(order_id)
    
    def get_open_orders(self, symbol: str = None):
        return self.order_manager.get_open_orders(symbol)
    
    def start(self):
        logger.info("Starting trading service...")
        self.ws_connector.connect()
        
        strategies = self.strategy_engine.get_registered_strategies()
        for strategy in strategies:
            self.strategy_engine.start_strategy(strategy)
        
        logger.info("Trading service started")
    
    def stop(self):
        logger.info("Stopping trading service...")
        
        strategies = self.strategy_engine.get_running_strategies()
        for strategy in strategies:
            self.strategy_engine.stop_strategy(strategy)
        
        self.ws_connector.disconnect()
        self.pnl_chart.print_pnl_summary()
        logger.info("Trading service stopped")
    
    def get_account_info(self):
        account = self.account_manager.get_account("default")
        if not account:
            return {}
        
        usdt_balance = account.get_balance("USDT")
        positions = {k: v for k, v in self.account_manager.positions.items() if v.quantity != 0}
        
        return {
            "balances": {asset: {"free": bal.free, "locked": bal.locked, "total": bal.total}
                        for asset, bal in account.balances.items()},
            "positions": {sym: {"quantity": pos.quantity, "avg_cost": pos.avg_cost,
                               "unrealized_pnl": pos.unrealized_pnl}
                         for sym, pos in positions.items()},
            "equity": self.account_manager.get_total_equity(),
            "initial_balance": account.initial_balance
        }

def main():
    config = Config()
    trading_service = TradingService(config)
    
    try:
        trading_service.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        trading_service.stop()

if __name__ == "__main__":
    main()
