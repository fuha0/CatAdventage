from pathlib import Path
from collections import OrderedDict


class RenderCache:
    """Small LRU cache for composed images, display images and PhotoImage objects."""

    def __init__(self, compose_limit=24, display_limit=72, photo_limit=120):
        self._limits = {
            'compose': max(4, int(compose_limit)),
            'display': max(4, int(display_limit)),
            'photo': max(4, int(photo_limit)),
        }
        self._stores = {name: OrderedDict() for name in self._limits}

    def get(self, layer, key):
        store = self._stores[layer]
        value = store.get(key)
        if value is None:
            return None
        store.move_to_end(key)
        return value

    def put(self, layer, key, value):
        store = self._stores[layer]
        store[key] = value
        store.move_to_end(key)
        limit = self._limits[layer]
        while len(store) > limit:
            store.popitem(last=False)

    def get_or_create(self, layer, key, factory):
        value = self.get(layer, key)
        if value is None:
            value = factory()
            self.put(layer, key, value)
        return value

    def clear(self, layer=None):
        if layer is None:
            for store in self._stores.values():
                store.clear()
            return
        self._stores[layer].clear()

    def stats(self):
        return {name: len(store) for name, store in self._stores.items()}