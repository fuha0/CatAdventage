# -*- coding: utf-8 -*-
"""校验 Excel 内容并生成发布版 JSON 缓存。

用法：
    python 桌宠/build_content.py --check
    python 桌宠/build_content.py
"""
import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import desktop_pet as app


def main():
    parser = argparse.ArgumentParser(description='校验并导出桌宠内容数据')
    parser.add_argument('--check', action='store_true', help='只校验，不写缓存')
    args = parser.parse_args()
    result = app.CONTENT_RESULT
    if not result.ok:
        print('内容校验失败：', file=sys.stderr)
        print(result.format_errors(0), file=sys.stderr)
        print('详细日志：~/.cat_pet_content_errors.log', file=sys.stderr)
        return 1
    print(f'内容校验通过：物品 {len(result.items)}，事件 {len(result.event_book)}，'
          f'宝藏 {len(result.treasure_book)}，前缀 {len(result.treasure_prefixes)}，'
          f'地区 {len(result.region_config)}')
    if args.check:
        return 0
    path, errors = app.CONTENT_REPOSITORY.export_cache(result)
    if errors:
        print('缓存写入失败：', file=sys.stderr)
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'内容缓存已生成：{path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
