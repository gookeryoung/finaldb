"""打包统计脚本：输出构建产物的大小与构成。"""

from __future__ import annotations

from pathlib import Path

_UNITS = ("B", "KB", "MB", "GB")


def get_dir_size(path: Path) -> int:
    """计算目录总大小（字节）。."""
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def format_size(size: float) -> str:
    """格式化文件大小。."""
    for unit in _UNITS:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def print_build_stats(dist_dir: Path) -> None:
    """打印构建统计摘要。."""
    print("=" * 60)
    print("构建统计摘要")
    print("=" * 60)

    for item in sorted(dist_dir.iterdir()):
        if item.is_dir():
            size = get_dir_size(item)
            file_count = sum(1 for f in item.rglob("*") if f.is_file())
            print(f"  {item.name:30s} {format_size(size):>12s}  ({file_count} 文件)")
        else:
            print(f"  {item.name:30s} {format_size(item.stat().st_size):>12s}")

    total = get_dir_size(dist_dir)
    print("-" * 60)
    print(f"  {'总计':30s} {format_size(total):>12s}")
    print("=" * 60)


if __name__ == "__main__":
    print_build_stats(Path("dist"))
