class InventoryService:
    @staticmethod
    def count(inventory, item_id):
        return max(0, int(inventory.get(item_id, 0)))

    @staticmethod
    def has(inventory, item_id, amount=1):
        return InventoryService.count(inventory, item_id) >= max(0, int(amount))

    @staticmethod
    def change(inventory, item_id, delta, max_count=None):
        before = InventoryService.count(inventory, item_id)
        after = max(0, before + int(delta))
        if max_count is not None:
            after = min(after, max(0, int(max_count)))
        inventory[item_id] = after
        return inventory[item_id] - before

    @staticmethod
    def add(inventory, item_id, amount, max_count=None):
        return InventoryService.change(
            inventory, item_id, abs(int(amount)), max_count=max_count)

    @staticmethod
    def remove(inventory, item_id, amount):
        amount = max(0, int(amount))
        before = InventoryService.count(inventory, item_id)
        inventory[item_id] = max(0, before - amount)
        return before - inventory[item_id]
