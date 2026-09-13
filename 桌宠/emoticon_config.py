# -*- coding: utf-8 -*-
"""颜文字配置加载器。"""
import json
import os

DEFAULT_EMOTICONS = {
    '狂欢': ('(๑•̀ㅂ•́)و', '(ฅ´ω`ฅ)', '(๑>؂<๑)','(๑˃ᴗ˂)ﻭ♡'),
    '开心': ('(*^ω^*)', 'ฅ( ̳• ◡ • ̳)ฅ', '(￣▽￣)','( ⁰▿⁰)','ദ്ദി*ˊᗜˋ*)'),
    '慵懒': ('(✿◡‿◡)', '( _ _ )..zzZ', '(・_・?)','( ˘ω˘ )ﾉﾞ','(¯﹃¯)'),
    '悲伤': ('(；ω；)', '(╥﹏╥)', '(＞﹏＜)', '(っ˘̩╭╮˘̩)っ','(。>﹏<。)'),
    '绝望': ('(；´д｀)ゞ', '(っ´Ι`)っ','(இ﹏இ`)','•̩̩̩̩ᯅ•̩̩̩'),
}


def load_emoticons(path):
    """读取 JSON；格式错误或文件不存在时使用默认颜文字。"""
    if not path or not os.path.exists(path):
        return {key: list(value) for key, value in DEFAULT_EMOTICONS.items()}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError('emoticon config must be an object')
        # 默认配置保底，JSON 中的自定义颜文字再追加进去，
        # 这样在任一文件中新增的条目都能生效。
        result = {key: list(values)
                  for key, values in DEFAULT_EMOTICONS.items()}
        for key, values in data.items():
            if not isinstance(values, list):
                continue
            clean = [str(value) for value in values if str(value).strip()]
            if not clean:
                continue
            merged = result.setdefault(str(key), [])
            for value in clean:
                if value not in merged:
                    merged.append(value)
        return result
    except Exception:
        return {key: list(value) for key, value in DEFAULT_EMOTICONS.items()}
