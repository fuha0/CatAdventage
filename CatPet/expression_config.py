# -*- coding: utf-8 -*-
"""单击表情概率配置加载器。"""
import copy
import json
import os


DEFAULT_CLICK_EXPRESSION_CHOICES = {
    'mouth': {
        'mouth_happy': 20,
        'mouth_huya': 20,
        'mouth_sad': 20,
        'mouth_comfy': 40,
    },
    'eye': {
        'eye': 25,
        'eye_1': 25,
        'eye_close2': 25,
        'eye_close3': 25,
        'eye_comfy': 25,
    },
    'brow': {
        'brow': 60,
        'brow_1': 40,
    },
}


def _default_config():
    return {
        'choices': copy.deepcopy(DEFAULT_CLICK_EXPRESSION_CHOICES),
        'assets': {},
    }


def _parse_part(raw_values, defaults):
    if not isinstance(raw_values, dict):
        return dict(defaults)
    parsed = {}
    for key, value in raw_values.items():
        key = str(key).strip()
        if not key or key.startswith('_'):
            continue
        if isinstance(value, dict):
            weight = value.get('weight', 0)
        else:
            weight = value
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            continue
        if weight > 0:
            parsed[key] = weight
    return parsed or dict(defaults)


def load_click_expression_config(path):
    """读取概率与新增素材配置；无效时使用内置默认值。"""
    result = _default_config()
    if not path or not os.path.exists(path):
        return result
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return result
        for part in ('mouth', 'eye', 'brow'):
            result['choices'][part] = _parse_part(
                data.get(part), DEFAULT_CLICK_EXPRESSION_CHOICES[part])
        raw_assets = data.get('assets', {})
        if isinstance(raw_assets, dict):
            for key, filename in raw_assets.items():
                key = str(key).strip()
                filename = str(filename or '').strip()
                if key and filename:
                    result['assets'][key] = filename
        # 便于在同一部位表中直接写入新素材：
        # "new_mouth": {"weight": 10, "file": "new_mouth.png"}
        for part in ('mouth', 'eye', 'brow'):
            raw_part = data.get(part)
            if not isinstance(raw_part, dict):
                continue
            for key, value in raw_part.items():
                if isinstance(value, dict) and value.get('file'):
                    result['assets'][str(key).strip()] = str(value['file']).strip()
    except Exception:
        return result
    return result


def choose_weighted(choices, rng):
    """按相对权重选择一个素材 ID。"""
    keys = [str(key) for key, weight in choices.items() if float(weight) > 0]
    weights = [float(choices[key]) for key in keys]
    if not keys:
        return None
    return rng.choices(keys, weights=weights, k=1)[0]
