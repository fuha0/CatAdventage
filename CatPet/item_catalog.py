# -*- coding: utf-8 -*-
"""兼容旧接口；实际读取逻辑统一由 ContentRepository 提供。"""
from pathlib import Path
from content_repository import ContentRepository


def load_item_overrides(items, path):
    if not path:
        return {key: dict(info) for key, info in items.items()}
    repository = ContentRepository(Path(path).parent, mode='dev')
    result, errors = repository.load_items_only(items)
    repository.write_error_log(errors)
    return result


def build_code_lookup(items):
    result = {}
    for key, info in items.items():
        try:
            result[int(info.get('code'))] = key
        except (TypeError, ValueError):
            continue
    return result
