"""盘点 MinIO bucket 占用：按前缀分组统计对象数与体积"""
import os
import sys
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from minio import Minio

client = Minio(
    endpoint=os.environ["MINIO_ENDPOINT"],
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
)

bucket = os.environ.get("MINIO_BUCKET", "test-management")

groups = defaultdict(lambda: [0, 0])  # prefix -> [count, bytes]
largest = []  # (size, name, last_modified)

for obj in client.list_objects(bucket, recursive=True):
    parts = obj.object_name.split("/")
    prefix = parts[0] if len(parts) > 1 else "(root)"
    g = groups[prefix]
    g[0] += 1
    g[1] += obj.size or 0
    largest.append((obj.size or 0, obj.object_name, obj.last_modified))

print(f"bucket: {bucket}  总对象数: {sum(v[0] for v in groups.values())}  总体积: {sum(v[1] for v in groups.values())/1024/1024:.1f} MB\n")
print(f"{'前缀':<40} {'对象数':>8} {'体积(MB)':>12}")
for prefix, (cnt, size) in sorted(groups.items(), key=lambda kv: -kv[1][1]):
    print(f"{prefix:<40} {cnt:>8} {size/1024/1024:>12.1f}")

print("\n最大的 20 个对象:")
for size, name, mtime in sorted(largest, reverse=True)[:20]:
    print(f"{size/1024/1024:>10.1f} MB  {mtime}  {name}")
