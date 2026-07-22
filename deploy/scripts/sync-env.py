#!/usr/bin/env python3
"""
同步 .env.example 中的托管键到运行中的 .env 文件。

设计原则：
- 只更新 allowlist 中的键，避免覆盖密码/API key 等用户自定义值。
- 如果 target 中不存在该键，会追加到文件末尾。
- 修改前自动备份 target 为 .env.bak.<timestamp>。
- 幂等：重复执行不会产生重复键或重复备份（1 分钟内只保留一个备份）。

用法：
    python3 deploy/scripts/sync-env.py \
        --example deploy/lightrag/.env.example \
        --target deploy/lightrag/.env \
        --keys LIGHTRAG_PARSER MULTIMODAL_PARSER DOCLING_DO_OCR

或在 deploy/deploy.sh 中调用：
    python3 "$SCRIPT_DIR/scripts/sync-env.py" \
        --example "$SCRIPT_DIR/lightrag/.env.example" \
        --target "$SCRIPT_DIR/lightrag/.env" \
        --keys LIGHTRAG_PARSER MULTIMODAL_PARSER DOCLING_DO_OCR
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable


def parse_env(path: Path) -> dict[str, tuple[str, int]]:
    """解析 .env 文件，返回 {key: (value, line_index)}。"""
    result: dict[str, tuple[str, int]] = {}
    if not path.exists():
        return result
    for idx, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        line = raw_line.rstrip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        # 支持 KEY=value 或 KEY="value" 或 KEY='value'
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        # 去除引号
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        result[key] = (value, idx)
    return result


def backup_target(path: Path) -> Path:
    """创建带时间戳的备份，同一分钟内不重复创建。"""
    ts = datetime.now().strftime("%Y%m%d%H%M")
    backup = path.with_suffix(f".env.bak.{ts}")
    if not backup.exists():
        shutil.copy2(path, backup)
    return backup


def sync_env(example: Path, target: Path, keys: Iterable[str], dry_run: bool = False) -> list[str]:
    """同步 allowlist 键，返回变更说明列表。"""
    keys = set(keys)
    example_data = parse_env(example)
    target_data = parse_env(target)

    changes: list[str] = []
    for key in sorted(keys):
        if key not in example_data:
            continue
        example_value = example_data[key][0]
        if key not in target_data:
            changes.append(f"ADD {key}={example_value}")
        elif target_data[key][0] != example_value:
            changes.append(f"UPDATE {key}: {target_data[key][0]!r} -> {example_value!r}")

    if not changes:
        return []

    if dry_run:
        return changes

    if target.exists():
        backup_target(target)

    text = target.read_text(encoding="utf-8") if target.exists() else ""
    lines = text.splitlines()

    # 记录已经写入的新增键，避免重复追加
    appended_keys: set[str] = set()

    for key in sorted(keys):
        if key not in example_data:
            continue
        value = example_data[key][0]
        if key in target_data:
            line_idx = target_data[key][1]
            old_line = lines[line_idx]
            # 保留原始缩进/引号风格，只替换值部分
            new_line = re.sub(
                r"^([A-Za-z_][A-Za-z0-9_]*\s*=\s*).*?\s*$",
                lambda m: f"{m.group(1)}{value}",
                old_line,
            )
            lines[line_idx] = new_line
        else:
            if key not in appended_keys:
                if lines and lines[-1].strip():
                    lines.append("")
                lines.append(f"{key}={value}")
                appended_keys.add(key)

    target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync managed env keys from example to target .env")
    parser.add_argument("--example", required=True, type=Path, help="Source .env.example file")
    parser.add_argument("--target", required=True, type=Path, help="Target .env file")
    parser.add_argument("--keys", nargs="+", required=True, help="Keys to sync")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args(argv)

    if not args.example.exists():
        print(f"[sync-env] example not found: {args.example}", file=sys.stderr)
        return 1

    changes = sync_env(args.example, args.target, args.keys, dry_run=args.dry_run)
    if not changes:
        print(f"[sync-env] {args.target}: no managed keys need update")
        return 0

    action = "(dry-run) " if args.dry_run else ""
    print(f"[sync-env] {action}{args.target}:")
    for change in changes:
        print(f"  {change}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
