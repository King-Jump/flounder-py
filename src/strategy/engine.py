from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from trading.models import DepthData, Order
import logging

logger = logging.getLogger(__name__)

class TradingStrategy(ABC):
    
    @abstractmethod
    def getName(self) -> str:
        pass
    
    @abstractmethod
    def onDepthUpdate(self, depth: DepthData) -> None:
        pass
    
    @abstractmethod
    def onOrderUpdate(self, order: Order) -> None:
        pass
    
    def set_trading_service(self, trading_service):
        self.trading_service = trading_service

class StrategyEngine:
    
    def __init__(self):
        self.strategies: Dict[str, TradingStrategy] = {}
        self.running_strategies: Dict[str, bool] = {}
    
    def register_strategy(self, strategy: TradingStrategy) -> None:
        name = strategy.getName()
        if name in self.strategies:
            logger.warning(f"Strategy {name} already registered")
            return
        self.strategies[name] = strategy
        self.running_strategies[name] = False
        logger.info(f"Strategy {name} registered")
    
    def unregister_strategy(self, strategy_name: str) -> None:
        if strategy_name not in self.strategies:
            logger.warning(f"Strategy {strategy_name} not found")
            return
        if self.running_strategies[strategy_name]:
            self.stop_strategy(strategy_name)
        del self.strategies[strategy_name]
        del self.running_strategies[strategy_name]
        logger.info(f"Strategy {strategy_name} unregistered")
    
    def start_strategy(self, strategy_name: str) -> None:
        if strategy_name not in self.strategies:
            logger.warning(f"Strategy {strategy_name} not found")
            return
        if self.running_strategies[strategy_name]:
            logger.warning(f"Strategy {strategy_name} already running")
            return
        self.running_strategies[strategy_name] = True
        logger.info(f"Strategy {strategy_name} started")
    
    def stop_strategy(self, strategy_name: str) -> None:
        if strategy_name not in self.strategies:
            logger.warning(f"Strategy {strategy_name} not found")
            return
        if not self.running_strategies[strategy_name]:
            logger.warning(f"Strategy {strategy_name} not running")
            return
        self.running_strategies[strategy_name] = False
        logger.info(f"Strategy {strategy_name} stopped")
    
    def on_depth_update(self, depth: DepthData) -> None:
        for name, running in self.running_strategies.items():
            if running:
                try:
                    self.strategies[name].onDepthUpdate(depth)
                except Exception as e:
                    logger.error(f"Error in strategy {name}: {e}")
    
    def on_order_update(self, order: Order) -> None:
        for name, running in self.running_strategies.items():
            if running:
                try:
                    self.strategies[name].onOrderUpdate(order)
                except Exception as e:
                    logger.error(f"Error in strategy {name}: {e}")
    
    def get_strategy(self, strategy_name: str) -> Optional[TradingStrategy]:
        return self.strategies.get(strategy_name)
    
    def get_registered_strategies(self) -> List[str]:
        return list(self.strategies.keys())
    
    def get_running_strategies(self) -> List[str]:
        return [name for name, running in self.running_strategies.items() if running]
