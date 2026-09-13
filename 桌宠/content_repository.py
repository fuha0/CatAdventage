# -*- coding: utf-8 -*-
"""统一内容数据入口：开发模式读取 Excel，发布模式读取 JSON 缓存。"""
import copy
import datetime
import importlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

QUALITY_NAMES = {'粗劣', '普通', '少见', '稀有', '史诗', '传说'}
PREFIX_GRADES = {'D级', 'C级', 'B级', 'A级', 'S级'}
EVENT_REGIONS = {1, 2, 3}


@dataclass
class ContentLoadResult:
    items: dict = field(default_factory=dict)
    event_book: list = field(default_factory=list)
    treasure_book: list = field(default_factory=list)
    treasure_prefixes: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    source: str = 'dev-excel'
    region_config: dict = field(default_factory=dict)

    @property
    def ok(self):
        return not self.errors

    def format_errors(self, limit=30):
        lines = list(self.errors)
        if limit and len(lines) > int(limit):
            extra = len(lines) - int(limit)
            lines = lines[:int(limit)] + [f'……另有 {extra} 条错误']
        return '\\n'.join(lines)


class ContentRepository:
    ITEM_FILE = '物品簿.xlsx'
    EVENT_FILE = '探险事件簿.xlsx'
    TREASURE_FILE = '探险宝藏簿.xlsx'
    CACHE_FILE = 'content_cache.json'

    def __init__(self, asset_dir, frozen=False, mode=None):
        self.asset_dir = Path(asset_dir)
        self.frozen = bool(frozen)
        self.mode = (mode or os.environ.get('CAT_CONTENT_MODE')
                     or ('release' if self.frozen else 'dev')).strip().lower()
        self.cache_path = self.asset_dir / self.CACHE_FILE
        self._last_result = None

    @property
    def paths(self):
        return {
            'items': self.asset_dir / self.ITEM_FILE,
            'events': self.asset_dir / self.EVENT_FILE,
            'treasures': self.asset_dir / self.TREASURE_FILE,
            'cache': self.cache_path,
        }

    def load(self, default_items=None):
        defaults = copy.deepcopy(default_items or {})
        if self.mode == 'release':
            result = self._load_json(defaults)
        else:
            result = self._load_excel(defaults)
        for info in result.items.values():
            self._normalize_market_fields(info)
        self._last_result = result
        return result

    def reload_events(self):
        if self.mode != 'dev':
            cached = self._last_result.event_book if self._last_result else []
            return copy.deepcopy(cached), []
        errors = []
        events = self._load_event_book(errors, self._import_openpyxl(errors))
        return events, errors

    def reload_treasures(self):
        if self.mode != 'dev':
            cached = self._last_result
            if cached is None:
                return [], [], []
            return (copy.deepcopy(cached.treasure_book),
                    copy.deepcopy(cached.treasure_prefixes), [])
        errors = []
        openpyxl = self._import_openpyxl(errors)
        book, prefixes = self._load_treasure_book(errors, openpyxl)
        return book, prefixes, errors

    def load_items_only(self, defaults=None):
        errors = []
        items = copy.deepcopy(defaults or {})
        if self.mode == 'release':
            if self._last_result is None:
                self.load(items)
            return copy.deepcopy(self._last_result.items), list(self._last_result.errors)
        openpyxl = self._import_openpyxl(errors)
        if openpyxl is not None:
            self._load_item_book(items, errors, openpyxl)
        return items, errors

    def export_cache(self, result=None, cache_path=None):
        result = result or self._last_result
        if result is None:
            return None, ['没有可导出的内容数据']
        if result.errors:
            return None, list(result.errors)
        target = Path(cache_path) if cache_path else self.cache_path
        payload = {
            'version': 1,
            'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
            'source': 'excel',
            'items': result.items,
            'events': [
                {**event, 'regions': sorted(int(v) for v in event.get('regions', []))}
                for event in result.event_book
            ],
            'treasures': result.treasure_book,
            'treasure_prefixes': result.treasure_prefixes,
            'regions': result.region_config,
        }
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + '.tmp')
            with open(temporary, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(temporary, target)
        except Exception as exc:
            return None, [f'写入内容缓存失败：{exc}']
        return target, []

    def write_error_log(self, errors=None, log_path=None):
        errors = list(errors or (self._last_result.errors if self._last_result else []))
        target = Path(log_path) if log_path else Path.home() / '.cat_pet_content_errors.log'
        try:
            if errors:
                text = '\n'.join([
                    f'[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]',
                    *errors,
                ]) + '\n'
                with open(target, 'w', encoding='utf-8') as handle:
                    handle.write(text)
            elif target.exists():
                target.unlink()
        except Exception:
            return None
        return target

    def _load_excel(self, defaults):
        errors = []
        openpyxl = self._import_openpyxl(errors)
        items = copy.deepcopy(defaults)
        if openpyxl is not None:
            self._load_item_book(items, errors, openpyxl)
        regions = self._load_region_config(errors, openpyxl)
        events = self._load_event_book(errors, openpyxl)
        treasures, prefixes = self._load_treasure_book(errors, openpyxl)
        return ContentLoadResult(
            items, events, treasures, prefixes, errors, 'dev-excel',
            region_config=regions)

    def _load_json(self, defaults):
        errors = []
        result = ContentLoadResult(
            items=copy.deepcopy(defaults), source='release-json')
        if not self.cache_path.exists():
            errors.append(f'缺少内容缓存：{self.cache_path}，请先运行 build_content.py')
            result.errors = errors
            return result
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as handle:
                payload = json.load(handle)
        except Exception as exc:
            errors.append(f'内容缓存无法读取：{exc}')
            result.errors = errors
            return result
        if not isinstance(payload, dict):
            errors.append('内容缓存根节点必须是对象')
            result.errors = errors
            return result
        version = payload.get('version')
        if version != 1:
            errors.append(f'内容缓存版本不支持：{version!r}')
        raw_items = payload.get('items', {})
        if not isinstance(raw_items, dict):
            errors.append('内容缓存字段 items 必须是对象')
        else:
            for key, info in raw_items.items():
                if not isinstance(info, dict):
                    errors.append(f'内容缓存物品 {key!r} 不是对象')
                    continue
                result.items[str(key)] = info
        result.event_book = self._validate_event_rows(
            payload.get('events', []), errors, source='内容缓存')
        result.treasure_book = self._validate_treasure_rows(
            payload.get('treasures', []), errors)
        result.treasure_prefixes = self._validate_prefix_rows(
            payload.get('treasure_prefixes', []), errors)
        result.region_config = self._validate_region_config(
            payload.get('regions', {}), errors)
        result.errors = errors
        return result

    def _import_openpyxl(self, errors):
        try:
            return importlib.import_module('openpyxl')
        except Exception as exc:
            errors.append(f'开发模式无法导入 openpyxl：{exc}')
            return None

    @staticmethod
    def _cell(row, columns, name):
        index = columns.get(name)
        if index is None or index >= len(row):
            return None
        value = row[index]
        return value

    @staticmethod
    def _headers(sheet):
        rows = sheet.iter_rows(values_only=True)
        try:
            values = next(rows)
        except StopIteration:
            return [], rows
        headers = [str(v).strip() if v is not None else '' for v in values]
        return headers, rows

    def _resolve_asset_path(self, value):
        """将 Excel 中的素材文件名解析为相对素材目录的路径。"""
        normalized = str(value).strip().replace('\\', '/')
        candidate = self.asset_dir / normalized
        if candidate.is_file():
            return candidate.relative_to(self.asset_dir).as_posix()
        name = Path(normalized).name
        matches = sorted(
            path for path in self.asset_dir.rglob(name) if path.is_file())
        if len(matches) == 1:
            return matches[0].relative_to(self.asset_dir).as_posix()
        return None

    def _set_asset_files(self, info, row, columns, sheet_title, row_no,
                         errors):
        """读取素材文件列，并补全分类目录。"""
        raw = self._cell(row, columns, '素材文件')
        if raw in (None, ''):
            info.pop('asset_file', None)
            return
        paths = []
        for value in re.split(r'[\uff1b;]', str(raw)):
            value = value.strip()
            if not value:
                continue
            resolved = self._resolve_asset_path(value)
            if resolved is None:
                errors.append(
                    f'{self.ITEM_FILE} / {sheet_title} / 第{row_no}行：'
                    f'找不到素材文件“{value}”')
                resolved = value.replace('\\', '/')
            paths.append(resolved)
        if paths:
            info['asset_file'] = ';'.join(paths)
        else:
            info.pop('asset_file', None)

    @staticmethod
    def _default_market_page(category):
        if category == '书籍':
            return '书店'
        if category in ('头饰', '服装', '饰品'):
            return '服装店'
        return '杂货铺'

    @staticmethod
    def _optional_bool(value, default=False):
        if value in (None, ''):
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in (
            '1', 'true', 'yes', 'y', '是', '可', '可以', '能')

    @staticmethod
    def _optional_price(value):
        if value in (None, ''):
            return None
        try:
            return max(0, int(float(value)))
        except (TypeError, ValueError):
            return None

    def _set_market_fields(self, info, row, columns, sheet_title, row_no,
                           errors):
        category = str(info.get('category', ''))
        legacy_price = self._optional_price(self._cell(row, columns, '价格'))
        buy_value = self._cell(row, columns, '购买价格')
        buy_price = (legacy_price if buy_value in (None, '')
                     else self._optional_price(buy_value))
        can_buy_value = self._cell(row, columns, '可否购买')
        can_buy = self._optional_bool(
            can_buy_value, default=buy_price is not None)
        if can_buy and buy_price is None:
            can_buy = False
            errors.append(
                f'{self.ITEM_FILE} / {sheet_title} / 第{row_no}行：'
                '标记为可购买但没有有效购买价格')

        sell_value = self._cell(row, columns, '出售价格')
        sell_price = self._optional_price(sell_value)
        default_sell = (False if category in ('服装', '书籍')
                        else sell_price is not None)
        can_sell = self._optional_bool(
            self._cell(row, columns, '可否出售'),
            default=default_sell)
        if can_sell and sell_price is None:
            can_sell = False
            errors.append(
                f'{self.ITEM_FILE} / {sheet_title} / 第{row_no}行：'
                '标记为可出售但没有有效出售价格')

        market_page = self._cell(row, columns, '对应集市子页')
        info['can_buy'] = bool(can_buy)
        info['buy_price'] = buy_price
        info['price'] = buy_price if can_buy else None
        info['can_sell'] = bool(can_sell)
        info['sell_price'] = sell_price
        info['market_page'] = (str(market_page).strip()
                               if market_page not in (None, '')
                               else self._default_market_page(category))

    @classmethod
    def _normalize_market_fields(cls, info):
        category = str(info.get('category', ''))
        buy_price = info.get('buy_price')
        if buy_price is None:
            buy_price = info.get('price')
        buy_price = cls._optional_price(buy_price)
        can_buy = cls._optional_bool(
            info.get('can_buy'), default=buy_price is not None)
        if not can_buy or buy_price is None:
            can_buy = False
            buy_price = None

        sell_price = cls._optional_price(info.get('sell_price'))
        default_sell = (False if category in ('服装', '书籍')
                        else sell_price is not None)
        can_sell = cls._optional_bool(
            info.get('can_sell'), default=default_sell)
        if not can_sell or sell_price is None:
            can_sell = False
            sell_price = None

        info['can_buy'] = can_buy
        info['buy_price'] = buy_price
        info['price'] = buy_price
        info['can_sell'] = can_sell
        info['sell_price'] = sell_price
        info['market_page'] = (str(info.get('market_page') or '').strip()
                               or cls._default_market_page(category))

    def _load_item_book(self, items, errors, openpyxl):
        path = self.paths['items']
        if not path.exists():
            errors.append(f'缺少物品簿：{path}')
            return
        workbook = None
        try:
            workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
            code_to_key = {}
            for key, info in items.items():
                try:
                    code_to_key[int(info.get('code'))] = key
                except (TypeError, ValueError):
                    pass
            for sheet in workbook.worksheets:
                if sheet.title == '说明':
                    continue
                headers, rows = self._headers(sheet)
                if '键名' not in headers:
                    errors.append(f'{self.ITEM_FILE} / {sheet.title}：缺少必需列“键名”')
                    continue
                columns = {name: headers.index(name) for name in headers if name}
                for row_no, row in enumerate(rows, start=2):
                    key_value = self._cell(row, columns, '键名')
                    key = str(key_value).strip() if key_value not in (None, '') else ''
                    raw_code = self._cell(row, columns, '编号')
                    code = None
                    if raw_code not in (None, ''):
                        try:
                            code = int(float(raw_code))
                        except (TypeError, ValueError):
                            errors.append(
                                f'{self.ITEM_FILE} / {sheet.title} / 第{row_no}行：编号“{raw_code}”不是数字')
                    if not key and code in code_to_key:
                        key = code_to_key[code]
                    if not key:
                        if code is not None:
                            errors.append(
                                f'{self.ITEM_FILE} / {sheet.title} / 第{row_no}行：找不到编号 {code} 对应的键名')
                        continue
                    info = items.setdefault(key, {})
                    if code is not None:
                        previous = code_to_key.get(code)
                        if previous is not None and previous != key:
                            errors.append(
                                f'{self.ITEM_FILE} / {sheet.title} / 第{row_no}行：编号 {code} 与 {previous} 重复')
                        info['code'] = code
                        code_to_key[code] = key
                    self._set_text(info, 'name', row, columns, '名称')
                    self._set_text(info, 'kind', row, columns, '类型')
                    info['category'] = sheet.title
                    self._set_text(info, 'quality', row, columns, '品质')
                    quality = info.get('quality')
                    if quality and quality not in QUALITY_NAMES:
                        errors.append(
                            f'{self.ITEM_FILE} / {sheet.title} / 第{row_no}行：品质“{quality}”不在允许范围内')
                    self._set_optional_text(info, 'hidden_attribute', row, columns, '隐藏属性')
                    region_text = str(
                        self._cell(row, columns, '可获得地区') or '')
                    regions = sorted({
                        int(value) for value in re.findall(r'\d+', region_text)})
                    invalid_regions = sorted(set(regions) - EVENT_REGIONS)
                    if invalid_regions:
                        errors.append(
                            f'{self.ITEM_FILE} / {sheet.title} / 第{row_no}行：'
                            f'可获得地区编号 {invalid_regions} 无效')
                    info['regions'] = regions
                    self._set_optional_text(info, 'desc', row, columns, '用途')
                    self._set_asset_files(info, row, columns, sheet.title, row_no, errors)
                    self._set_market_fields(
                        info, row, columns, sheet.title, row_no, errors)
                    exp = self._cell(row, columns, '经验')
                    if exp in (None, ''):
                        info.pop('exp', None)
                    else:
                        try:
                            info['exp'] = int(float(exp))
                        except (TypeError, ValueError):
                            info.pop('exp', None)
                            errors.append(
                                f'{self.ITEM_FILE} / {sheet.title} / 第{row_no}行：经验“{exp}”不是数字')
                    effect = self._cell(row, columns, '特殊效果')
                    if effect in (None, ''):
                        info.pop('eat_effect', None)
                    else:
                        try:
                            parsed = json.loads(str(effect))
                            if not isinstance(parsed, dict):
                                raise ValueError('必须是 JSON 对象')
                            info['eat_effect'] = parsed
                        except Exception:
                            info.pop('eat_effect', None)
                            errors.append(
                                f'{self.ITEM_FILE} / {sheet.title} / 第{row_no}行：特殊效果不是有效 JSON 对象')
                    self._set_optional_text(info, 'clothes_style', row, columns, '服装样式')
        except Exception as exc:
            errors.append(f'{self.ITEM_FILE}：读取失败：{exc}')
        finally:
            self._close_workbook(workbook)

    @staticmethod
    def _set_text(info, target, row, columns, source):
        for candidate in (source, source + ' '):
            index = columns.get(candidate)
            if index is not None and index < len(row):
                value = row[index]
                if value not in (None, ''):
                    info[target] = str(value).strip()
                return

    @staticmethod
    def _set_optional_text(info, target, row, columns, source):
        index = columns.get(source)
        if index is None or index >= len(row) or row[index] in (None, ''):
            info.pop(target, None)
        else:
            info[target] = str(row[index]).strip()

    def _load_region_config(self, errors, openpyxl):
        """读取地区配置（包括额外宝藏上限）。"""
        if openpyxl is None:
            return {}
        path = self.paths['events']
        if not path.exists():
            return {}
        workbook = None
        regions = {}
        try:
            workbook = openpyxl.load_workbook(
                path, data_only=True, read_only=True)
            if '地区配置' not in workbook.sheetnames:
                errors.append(f'{self.EVENT_FILE}：缺少工作表“地区配置”')
                return {}
            sheet = workbook['地区配置']
            headers, rows = self._headers(sheet)
            required = ('地区编号', '额外宝藏上限')
            missing = [name for name in required if name not in headers]
            if missing:
                errors.append(
                    f'{self.EVENT_FILE} / {sheet.title}：缺少列 '
                    + '、'.join(missing))
                return {}
            columns = {name: headers.index(name) for name in required}
            for row_no, row in enumerate(rows, start=2):
                raw_id = self._cell(row, columns, '地区编号')
                if raw_id in (None, ''):
                    continue
                try:
                    region_id = int(float(raw_id))
                except (TypeError, ValueError):
                    errors.append(
                        f'{self.EVENT_FILE} / {sheet.title} / 第{row_no}行：'
                        f'地区编号“{raw_id}”不是数字')
                    continue
                raw_extra = self._cell(row, columns, '额外宝藏上限')
                try:
                    extra_max = int(float(raw_extra))
                except (TypeError, ValueError):
                    errors.append(
                        f'{self.EVENT_FILE} / {sheet.title} / 第{row_no}行：'
                        f'额外宝藏上限“{raw_extra}”不是数字')
                    continue
                if extra_max < 0:
                    errors.append(
                        f'{self.EVENT_FILE} / {sheet.title} / 第{row_no}行：'
                        f'额外宝藏上限不能为负数')
                    continue
                key = str(region_id)
                if key in regions:
                    errors.append(
                        f'{self.EVENT_FILE} / {sheet.title} / 第{row_no}行：'
                        f'地区编号 {region_id} 重复')
                    continue
                name_col = headers.index('地区名称') if '地区名称' in headers else None
                name = (str(row[name_col]).strip()
                        if name_col is not None and row[name_col] not in (None, '')
                        else '')
                desc_col = headers.index('说明') if '说明' in headers else None
                description = (str(row[desc_col]).strip()
                               if desc_col is not None and row[desc_col] not in (None, '')
                               else '')
                quality_weights = {}
                weight_columns = {
                    '粗劣权重': 1, '普通权重': 2, '少见权重': 3,
                    '稀有权重': 4, '史诗权重': 5, '传说权重': 6,
                }
                for column_name, quality in weight_columns.items():
                    if column_name not in headers:
                        continue
                    raw_weight = self._cell(row, columns, column_name) if column_name in columns else row[headers.index(column_name)]
                    if raw_weight in (None, ''):
                        continue
                    try:
                        quality_weights[quality] = max(0.0, float(raw_weight))
                    except (TypeError, ValueError):
                        errors.append(
                            f'{self.EVENT_FILE} / {sheet.title} / 第{row_no}行：'
                            f'{column_name}“{raw_weight}”不是数字')
                regions[key] = {
                    'name': name,
                    'extra_treasure_max': extra_max,
                    'description': description,
                    'quality_weights': quality_weights,
                }
        except Exception as exc:
            errors.append(f'{self.EVENT_FILE}：地区配置读取失败：{exc}')
        finally:
            self._close_workbook(workbook)
        return regions

    @staticmethod
    def _validate_region_config(raw, errors):
        if raw in (None, ''):
            return {}
        if not isinstance(raw, dict):
            errors.append('内容缓存字段 regions 必须是对象')
            return {}
        result = {}
        for raw_id, info in raw.items():
            try:
                region_id = int(raw_id)
            except (TypeError, ValueError):
                errors.append(f'内容缓存地区编号 {raw_id!r} 不是数字')
                continue
            if not isinstance(info, dict):
                errors.append(f'内容缓存地区 {region_id} 配置不是对象')
                continue
            try:
                extra_max = max(0, int(info.get('extra_treasure_max', 0)))
            except (TypeError, ValueError):
                errors.append(f'内容缓存地区 {region_id} 的额外宝藏上限不是数字')
                continue
            raw_weights = info.get('quality_weights', {})
            quality_weights = {}
            if isinstance(raw_weights, dict):
                for raw_quality, raw_weight in raw_weights.items():
                    try:
                        quality = int(raw_quality)
                        weight = max(0.0, float(raw_weight))
                    except (TypeError, ValueError):
                        continue
                    if 1 <= quality <= 6:
                        quality_weights[quality] = weight
            result[str(region_id)] = {
                'name': str(info.get('name', '')),
                'extra_treasure_max': extra_max,
                'description': str(info.get('description', '')),
                'quality_weights': quality_weights,
            }
        return result

    def _load_event_book(self, errors, openpyxl):
        if openpyxl is None:
            return []
        path = self.paths['events']
        if not path.exists():
            errors.append(f'缺少探险事件簿：{path}')
            return []
        workbook = None
        events = []
        try:
            workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
            if '事件簿' in workbook.sheetnames:
                sheet = workbook['事件簿']
            else:
                sheet = workbook.active
                errors.append(f'{self.EVENT_FILE}：找不到工作表“事件簿”，已读取活动工作表')
            headers, rows = self._headers(sheet)
            required = ('事件名', '事件概述', '事件可能遭遇的地区', '事件难度',
                        '成功描述', '成功奖励', '失败描述', '失败惩罚')
            missing = [name for name in required if name not in headers]
            if missing:
                errors.append(
                    f'{self.EVENT_FILE} / {sheet.title}：缺少列 ' + '、'.join(missing))
                return []
            columns = {name: headers.index(name) for name in required}
            for row_no, row in enumerate(rows, start=2):
                name = str(self._cell(row, columns, '事件名') or '').strip()
                if not name:
                    continue
                region_text = str(self._cell(row, columns, '事件可能遭遇的地区') or '')
                regions = {int(value) for value in re.findall(r'\d+', region_text)}
                if not regions:
                    errors.append(
                        f'{self.EVENT_FILE} / {sheet.title} / 第{row_no}行：事件地区为空或格式错误')
                    continue
                invalid_regions = sorted(regions - EVENT_REGIONS)
                if invalid_regions:
                    errors.append(
                        f'{self.EVENT_FILE} / {sheet.title} / 第{row_no}行：地区编号 {invalid_regions} 无效')
                raw_difficulty = self._cell(row, columns, '事件难度')
                try:
                    difficulty = max(1, int(float(raw_difficulty)))
                except (TypeError, ValueError):
                    errors.append(
                        f'{self.EVENT_FILE} / {sheet.title} / 第{row_no}行：事件难度“{raw_difficulty}”不是数字')
                    continue
                events.append({
                    'name': name,
                    'summary': str(self._cell(row, columns, '事件概述') or '').strip(),
                    'regions': regions,
                    'difficulty': difficulty,
                    'success_desc': str(self._cell(row, columns, '成功描述') or '').strip(),
                    'success_reward': str(self._cell(row, columns, '成功奖励') or '').strip(),
                    'failure_desc': str(self._cell(row, columns, '失败描述') or '').strip(),
                    'failure_penalty': str(self._cell(row, columns, '失败惩罚') or '').strip(),
                })
        except Exception as exc:
            errors.append(f'{self.EVENT_FILE}：读取失败：{exc}')
        finally:
            self._close_workbook(workbook)
        return events

    def _load_treasure_book(self, errors, openpyxl):
        if openpyxl is None:
            return [], []
        path = self.paths['treasures']
        if not path.exists():
            errors.append(f'缺少探险宝藏簿：{path}')
            return [], []
        workbook = None
        treasures = []
        prefixes = []
        try:
            workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
            if '宝藏汇总' not in workbook.sheetnames:
                errors.append(f'{self.TREASURE_FILE}：缺少工作表“宝藏汇总”')
            else:
                treasures = self._read_treasure_summary(
                    workbook['宝藏汇总'], errors)
            if '前缀' not in workbook.sheetnames:
                errors.append(f'{self.TREASURE_FILE}：缺少工作表“前缀”')
            else:
                prefixes = self._read_treasure_prefixes(
                    workbook['前缀'], errors)
        except Exception as exc:
            errors.append(f'{self.TREASURE_FILE}：读取失败：{exc}')
        finally:
            self._close_workbook(workbook)
        return treasures, prefixes

    def _read_treasure_summary(self, sheet, errors):
        result = []
        headers, rows = self._headers(sheet)
        required = ('宝藏名字', '宝藏可能拥有的品质', '宝藏基础价值', '可能获得地区')
        missing = [name for name in required if name not in headers]
        if missing:
            errors.append(
                f'{self.TREASURE_FILE} / {sheet.title}：缺少列 ' + '、'.join(missing))
            return result
        columns = {name: headers.index(name) for name in required}
        for row_no, row in enumerate(rows, start=2):
            name = str(self._cell(row, columns, '宝藏名字') or '').strip()
            if not name:
                continue
            quality_text = str(self._cell(row, columns, '宝藏可能拥有的品质') or '')
            qualities = sorted({int(value) for value in re.findall(r'\d+', quality_text)
                                if 1 <= int(value) <= 6})
            if not qualities:
                errors.append(
                    f'{self.TREASURE_FILE} / {sheet.title} / 第{row_no}行：宝藏品质为空或格式错误')
                continue
            raw_value = self._cell(row, columns, '宝藏基础价值')
            try:
                base_value = max(1, int(float(raw_value)))
            except (TypeError, ValueError):
                errors.append(
                    f'{self.TREASURE_FILE} / {sheet.title} / 第{row_no}行：基础价值“{raw_value}”不是数字')
                continue
            region_text = str(self._cell(row, columns, '可能获得地区') or '')
            regions = sorted({int(value) for value in re.findall(r'\d+', region_text)})
            if not regions or any(value not in EVENT_REGIONS for value in regions):
                errors.append(
                    f'{self.TREASURE_FILE} / {sheet.title} / 第{row_no}行：可能获得地区为空或格式错误')
                continue
            result.append({'name': name, 'qualities': qualities,
                           'regions': regions, 'base_value': base_value})
        return result

    def _read_treasure_prefixes(self, sheet, errors):
        result = []
        headers, rows = self._headers(sheet)
        required = ('前缀等级', '前缀名称', '价值倍率')
        missing = [name for name in required if name not in headers]
        if missing:
            errors.append(
                f'{self.TREASURE_FILE} / {sheet.title}：缺少列 ' + '、'.join(missing))
            return result
        columns = {name: headers.index(name) for name in required}
        for row_no, row in enumerate(rows, start=2):
            grade = str(self._cell(row, columns, '前缀等级') or '').strip()
            name = str(self._cell(row, columns, '前缀名称') or '').strip()
            if not grade and not name:
                continue
            if not grade or not name:
                errors.append(
                    f'{self.TREASURE_FILE} / {sheet.title} / 第{row_no}行：前缀等级或名称为空')
                continue
            if grade not in PREFIX_GRADES:
                errors.append(
                    f'{self.TREASURE_FILE} / {sheet.title} / 第{row_no}行：前缀等级“{grade}”无效')
            raw_multiplier = self._cell(row, columns, '价值倍率')
            try:
                multiplier = max(0.01, float(raw_multiplier))
            except (TypeError, ValueError):
                errors.append(
                    f'{self.TREASURE_FILE} / {sheet.title} / 第{row_no}行：价值倍率“{raw_multiplier}”不是数字')
                continue
            result.append({'grade': grade, 'name': name, 'multiplier': multiplier})
        return result

    def _validate_event_rows(self, rows, errors, source):
        result = []
        if not isinstance(rows, list):
            errors.append(f'{source}：events 必须是数组')
            return result
        for index, event in enumerate(rows, start=1):
            if not isinstance(event, dict):
                errors.append(f'{source}：第{index}个事件不是对象')
                continue
            regions = event.get('regions', [])
            if not isinstance(regions, (list, tuple)):
                errors.append(f'{source}：第{index}个事件 regions 必须是数组')
                continue
            try:
                difficulty = max(1, int(event.get('difficulty', 1)))
            except (TypeError, ValueError):
                errors.append(f'{source}：第{index}个事件 difficulty 不是数字')
                continue
            result.append({**event,
                           'regions': {int(v) for v in regions},
                           'difficulty': difficulty})
        return result

    def _validate_treasure_rows(self, rows, errors):
        result = []
        if not isinstance(rows, list):
            errors.append('内容缓存：treasures 必须是数组')
            return result
        for index, item in enumerate(rows, start=1):
            if not isinstance(item, dict):
                errors.append(f'内容缓存：第{index}个宝藏不是对象')
                continue
            qualities = item.get('qualities', [])
            if not isinstance(qualities, (list, tuple)):
                errors.append(f'内容缓存：第{index}个宝藏 qualities 必须是数组')
                continue
            regions = item.get('regions', [])
            if not isinstance(regions, (list, tuple)):
                errors.append(f'内容缓存：第{index}个宝藏 regions 必须是数组')
                continue
            region_values = sorted({int(v) for v in regions})
            if not region_values or any(v not in EVENT_REGIONS for v in region_values):
                errors.append(f'内容缓存：第{index}个宝藏 regions 无效')
                continue
            try:
                base_value = max(1, int(item.get('base_value', 1)))
            except (TypeError, ValueError):
                errors.append(f'内容缓存：第{index}个宝藏 base_value 不是数字')
                continue
            result.append({**item,
                           'qualities': [int(v) for v in qualities],
                           'regions': region_values,
                           'base_value': base_value})
        return result

    def _validate_prefix_rows(self, rows, errors):
        result = []
        if not isinstance(rows, list):
            errors.append('内容缓存：treasure_prefixes 必须是数组')
            return result
        for index, item in enumerate(rows, start=1):
            if not isinstance(item, dict):
                errors.append(f'内容缓存：第{index}个前缀不是对象')
                continue
            try:
                multiplier = max(0.01, float(item.get('multiplier', 1)))
            except (TypeError, ValueError):
                errors.append(f'内容缓存：第{index}个前缀 multiplier 不是数字')
                continue
            result.append({**item, 'multiplier': multiplier})
        return result

    @staticmethod
    def _close_workbook(workbook):
        if workbook is None:
            return
        try:
            workbook.close()
        except Exception:
            pass
