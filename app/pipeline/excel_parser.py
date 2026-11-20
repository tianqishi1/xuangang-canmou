# -*- coding: utf-8 -*-
"""省份模板驱动的 Excel 解析：列名映射 YAML → 规范化行。

支持 .xlsx（openpyxl）与 .xls（xlrd）；表头匹配忽略空白/全角空格
（真实省考表头形如「学　历」「隶属  关系」）。
"""
import re
import yaml


def load_template(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return yaml.safe_load(f)


def _norm(s):
    return re.sub(r"\s+", "", str(s)) if s is not None else ""


def _read_rows(path, sheet=0):
    if str(path).lower().endswith(".xls"):
        import xlrd
        wb = xlrd.open_workbook(str(path))
        ws = wb.sheet_by_name(sheet) if isinstance(sheet, str) else wb.sheet_by_index(sheet)
        return [ws.row_values(i) for i in range(ws.nrows)]
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    name = sheet if isinstance(sheet, str) else wb.sheetnames[sheet]
    ws = wb[name]
    return list(ws.iter_rows(values_only=True))


def parse_excel(path, template):
    rows = _read_rows(path, template.get("sheet", 0))
    colmap = {canon: _norm(name) for canon, name in template["columns"].items()}
    header_idx = None
    for i, r in enumerate(rows[:10]):
        cells = [_norm(c) for c in r]
        if colmap["org_name"] in cells:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"未找到表头行（需包含列「{template['columns']['org_name']}」）")
    header = [_norm(c) for c in rows[header_idx]]
    idx = {}
    for canon, name in colmap.items():
        if name in header:
            idx[canon] = header.index(name)
    out = []
    for rn, r in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if r is None or all(c is None or str(c).strip() == "" for c in r):
            continue
        row = {canon: (str(r[i]).strip() if i < len(r) and r[i] is not None else "")
               for canon, i in idx.items()}
        if not row.get("org_name"):
            continue
        row["_source_row"] = rn
        out.append(row)
    return out
