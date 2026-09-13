from dataclasses import dataclass
from .inventory import InventoryService
from .treasure import TreasureService


@dataclass
class PurchaseResult:
    ok: bool
    amount: int
    cost: int
    reason: str = ''


@dataclass
class TreasureSaleResult:
    ok: bool
    count: int
    gain: int
    emotion_gain: int
    reason: str = ''


class MarketService:
    @staticmethod
    def max_affordable(gold, unit_price, cap=99):
        unit_price = max(0, int(unit_price))
        if unit_price <= 0:
            return max(1, int(cap))
        return max(0, min(int(cap), max(0, int(gold)) // unit_price))

    @staticmethod
    def purchase(state, inventory, item_id, unit_price, amount,
                 max_count=None):
        amount = max(1, int(amount))
        if max_count is not None:
            available = max(0, int(max_count) - InventoryService.count(
                inventory, item_id))
            if available <= 0:
                return PurchaseResult(False, 0, 0, 'sold_out')
            amount = min(amount, available)
        unit_price = max(0, int(unit_price))
        cost = unit_price * amount
        if state.gold < cost:
            return PurchaseResult(False, amount, cost, 'insufficient_gold')
        state.gold -= cost
        InventoryService.add(inventory, item_id, amount,
                            max_count=max_count)
        return PurchaseResult(True, amount, cost)

    @staticmethod
    def sell_item(state, inventory, item_id, unit_price, amount=1):
        amount = max(1, int(amount))
        unit_price = max(0, int(unit_price))
        removed = InventoryService.remove(inventory, item_id, amount)
        if removed <= 0:
            return PurchaseResult(False, 0, 0, 'not_owned')
        gain = unit_price * removed
        state.gold += gain
        return PurchaseResult(True, removed, gain)

    @staticmethod
    def sell_treasures(state, treasures, targets, emotion_by_quality=None):
        emotion_by_quality = emotion_by_quality or {}
        sale = TreasureService.select_sale(
            treasures, targets, emotion_by_quality)
        if not sale.targets:
            return TreasureSaleResult(False, 0, 0, 0, 'no_targets')
        selected = sale.targets
        selected_ids = {int(t.get('uid', 0)) for t in selected}
        gain = sale.gain
        emotion = sale.emotion_gain
        treasures[:] = [
            t for t in treasures
            if int(t.get('uid', 0)) not in selected_ids
        ]
        state.gold += gain
        state.emotion = min(100, int(state.emotion) + emotion)
        return TreasureSaleResult(True, len(selected), gain, emotion)
