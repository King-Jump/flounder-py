from typing import Dict, Optional
from trading.models import Account, Balance, Position, Order, OrderSide
from trading.config import Config
import logging

logger = logging.getLogger(__name__)

class AccountManager:
    
    def __init__(self, config: Config = None):
        self.account_id_counter = 0
        self.config = config or Config()
        self.accounts: Dict[str, Account] = {}
        self.positions: Dict[str, Position] = {}
    
    def create_account(self, initial_balance: Optional[float] = None) -> Account:
        balance = initial_balance or self.config.INITIAL_BALANCE
        self.account_id_counter += 1
        account = Account(
            account_id=str(self.account_id_counter),
            balances={"USDT": Balance("USDT", free=balance)},
            initial_balance=balance
        )
        self.accounts[account.account_id] = account
        logger.info(f"Created account: {account.account_id} with balance {balance}")
        return account
    
    def get_account(self, account_id: str) -> Optional[Account]:
        return self.accounts.get(account_id)
    
    def get_balance(self, account_id: str, asset: str) -> Optional[Balance]:
        account = self.get_account(account_id)
        if not account:
            return None
        return account.get_balance(asset)
    
    def update_balance(self, account_id: str, asset: str, free_change: float = 0.0, locked_change: float = 0.0):
        account = self.get_account(account_id)
        if not account:
            logger.error(f"Account {account_id} not found")
            return
        account.update_balance(asset, free_change, locked_change)
    
    def check_balance(self, account_id: str, asset: str, amount: float) -> bool:
        balance = self.get_balance(account_id, asset)
        if not balance:
            return False
        return balance.free >= amount
    
    def get_position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol)
        return self.positions[symbol]
    
    def update_position(self, symbol: str, quantity: float, price: float):
        position = self.get_position(symbol)
        
        if position.quantity == 0:
            position.avg_cost = price
            position.quantity = quantity
        else:
            total_cost = position.avg_cost * abs(position.quantity) + price * abs(quantity)
            total_quantity = abs(position.quantity) + abs(quantity)
            position.avg_cost = total_cost / total_quantity
            position.quantity += quantity
        
        logger.debug(f"Updated position for {symbol}: quantity={position.quantity}, avg_cost={position.avg_cost}")
    
    def process_order_fill(self, order: Order, filled_quantity: float, fill_price: float):
        if filled_quantity <= 0:
            return
        
        base_asset = order.symbol[:-4]
        quote_asset = "USDT"
        
        if order.side == OrderSide.BUY:
            cost = filled_quantity * fill_price * (1 + self.config.COMMISSION_RATE)
            self.update_balance("default", quote_asset, free_change=-cost)
            self.update_position(order.symbol, filled_quantity, fill_price)
            self.update_balance("default", base_asset, free_change=filled_quantity)
        else:
            revenue = filled_quantity * fill_price * (1 - self.config.COMMISSION_RATE)
            self.update_balance("default", base_asset, free_change=-filled_quantity)
            self.update_position(order.symbol, -filled_quantity, fill_price)
            self.update_balance("default", quote_asset, free_change=revenue)
        
        logger.info(f"Processed order fill: {order.side} {filled_quantity} {order.symbol} at {fill_price}")
    
    def recalculate_unrealized_pnl(self, symbol: str, current_price: float):
        position = self.get_position(symbol)
        if position.quantity == 0:
            position.unrealized_pnl = 0.0
            return
        
        if position.is_long:
            position.unrealized_pnl = (current_price - position.avg_cost) * position.quantity
        else:
            position.unrealized_pnl = (position.avg_cost - current_price) * abs(position.quantity)
    
    def get_total_equity(self) -> float:
        total = 0.0
        for position in self.positions.values():
            total += position.unrealized_pnl
        
        account = self.get_account("default")
        if account:
            usdt_balance = account.get_balance("USDT")
            if usdt_balance:
                total += usdt_balance.total
        
        return total
