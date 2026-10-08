"""Isolated, reproducible event-storage comparison. Requires Docker and app dependencies.

Run from project root: python scripts/benchmark_storage.py
Creates three disposable containers; never changes application data.
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.knowledge.embedding import vector_literal

ROOT = Path(__file__).resolve().parents[1]


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True, cwd=ROOT).strip()


def counters(names):
    cpu = memory = 0
    for name in names:
        raw = docker(
            "exec",
            name,
            "sh",
            "-c",
            "cat /sys/fs/cgroup/cpu.stat; cat /sys/fs/cgroup/memory.current",
        )
        lines = raw.splitlines()
        cpu += int(next(line.split()[1] for line in lines if line.startswith("usage_usec "))) / 1e6
        memory += int(lines[-1])
    return cpu, memory


def pg_setup(conn, vectors):
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.execute(
        "CREATE TABLE events(id text PRIMARY KEY,priority text,timestamp timestamptz,payload jsonb"
        + (",embedding vector(384)" if vectors else "")
        + ")"
    )
    conn.execute("CREATE INDEX ON events(timestamp DESC)")
    conn.execute("CREATE INDEX ON events(priority)")
    for field in ("received_at", "source", "dataset"):
        conn.execute(f"CREATE INDEX ON events((payload->>'{field}'))")


def insert_pg(conn, rows, vectors):
    sql = "INSERT INTO events VALUES(%s,%s,%s,%s" + (",%s::vector)" if vectors else ")")
    with conn.transaction(), conn.cursor() as cursor:
        cursor.executemany(
            sql,
            [
                (
                    r["id"],
                    r["prediction"]["priority"],
                    r["timestamp"],
                    Jsonb(r),
                    *([vector_literal(r["message"])] if vectors else []),
                )
                for r in rows
            ],
        )


def main():
    export = "from app.storage.repository import Repository; from app.config import settings; import json; r=Repository(settings); rows=list(r.logs.find({}, {'_id':0})); c=r.pool.getconn(); rows += [x['payload'] for x in c.execute('SELECT payload FROM events').fetchall()]; r.pool.putconn(c); print(json.dumps(sorted(rows,key=lambda x:x['id']),default=str)); r.close()"
    rows = json.loads(docker("compose", "exec", "-T", "api", "python", "-c", export))
    if not rows:
        raise SystemExit("Ingest logs before running the benchmark")
    prefix = "logsense-bench-" + uuid4().hex[:10]
    names = [prefix + "-baseline", prefix + "-hybrid", prefix + "-mongo"]
    created = []
    connections = []
    password = uuid4().hex
    try:
        for name in names[:2]:
            docker(
                "run",
                "-d",
                "--name",
                name,
                "--label",
                "logsense.disposable-benchmark=true",
                "-e",
                f"POSTGRES_PASSWORD={password}",
                "-p",
                "127.0.0.1::5432",
                "pgvector/pgvector:pg17",
            )
            created.append(name)
        docker(
            "run",
            "-d",
            "--name",
            names[2],
            "--label",
            "logsense.disposable-benchmark=true",
            "-p",
            "127.0.0.1::27017",
            "mongo:8.0",
        )
        created.append(names[2])
        for name in names[:2]:
            port = int(docker("port", name, "5432/tcp").rsplit(":", 1)[1])
            deadline = time.monotonic() + 60
            while True:
                try:
                    conn = psycopg.connect(
                        host="127.0.0.1",
                        port=port,
                        user="postgres",
                        password=password,
                        autocommit=True,
                        connect_timeout=2,
                    )
                    connections.append(conn)
                    break
                except psycopg.OperationalError:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(0.5)
        mongo = MongoClient(
            "mongodb://127.0.0.1:" + docker("port", names[2], "27017/tcp").rsplit(":", 1)[1],
            serverSelectionTimeoutMS=60000,
        )
        mongo.admin.command("ping")
        collection = mongo.benchmark.events
        collection.create_index([("timestamp", -1)])
        for field in ("prediction.priority", "received_at", "source", "dataset"):
            collection.create_index(field)
        low = [r for r in rows if r["prediction"]["priority"] in ("P1", "P2", "P3")]
        high = [r for r in rows if r["prediction"]["priority"] in ("P4", "P5")]
        result = {}
        for index, label in enumerate(("baseline", "hybrid")):
            conn = connections[index]
            pg_setup(conn, index == 0)
            involved = [names[index]] + ([names[2]] if index else [])
            cpu_start, _ = counters(involved)
            started = time.perf_counter()
            insert_pg(conn, rows if index == 0 else high, index == 0)
            if index and low:
                collection.insert_many([dict(r, _id=r["id"]) for r in low])
            load_seconds = time.perf_counter() - started
            started = time.perf_counter()
            # Same 500 point reads, repeated five times; route is known for both.
            for _ in range(5):
                for row in rows[:500]:
                    if index and row["prediction"]["priority"] in ("P1", "P2", "P3"):
                        assert collection.find_one({"_id": row["id"]})
                    else:
                        assert conn.execute(
                            "SELECT payload FROM events WHERE id=%s", (row["id"],)
                        ).fetchone()
            query_seconds = time.perf_counter() - started
            cpu_end, memory = counters(involved)
            conn.execute("VACUUM ANALYZE events")
            conn.execute("CHECKPOINT")
            pg_bytes = conn.execute("SELECT pg_total_relation_size('events')").fetchone()[0]
            mongo_bytes = 0
            if index:
                mongo.admin.command("fsync")
                stats = collection.database.command("collStats", "events", scale=1)
                mongo_bytes = stats["storageSize"] + stats["totalIndexSize"]
            result[label] = {
                "total_bytes": pg_bytes + mongo_bytes,
                "postgres_bytes": pg_bytes,
                "mongo_bytes": mongo_bytes,
                "load_seconds": load_seconds,
                "query_seconds": query_seconds,
                "cpu_seconds": max(0, cpu_end - cpu_start),
                "memory_bytes": memory,
            }
        result.update(
            {
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "event_count": len(rows),
                "low_priority_count": len(low),
                "high_priority_count": len(high),
                "sample_sha256": sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(),
                "versions": {
                    "postgres": docker("exec", names[0], "postgres", "--version"),
                    "mongo": mongo.server_info()["version"],
                },
                "methodology": "Single local trial using isolated PostgreSQL 17/pgvector and MongoDB 8 containers, identical payloads and comparable lookup/filter indexes. Baseline adds one 384-float lexical vector per event; hybrid stores no per-event vectors. No vector ANN index. Load includes client vector generation; queries are 5 × up to 500 identical ID lookups. Sizes measured after checkpoint; CPU uses database cgroup usage deltas during load and lookups. Memory is the post-workload sum of database cgroup memory.current, including cache, not configured RAM or a peak.",
                "limitations": "Event-only allocation excludes shared knowledge, routing receipts, incidents, Redis, WAL/journals, backups, and replication. Hybrid includes both database processes in CPU/memory. Baseline supports per-event vectors whereas hybrid uses shared knowledge retrieval: capabilities differ. One trial, warm lookups, local Docker host, small sample, and measurement overhead limit generalisation. These measurements cannot establish production CPU/RAM or total infrastructure cost savings.",
            }
        )
        folder = ROOT / "experiments/storage-runs"
        folder.mkdir(exist_ok=True)
        text = json.dumps(result, indent=2)
        temporary = folder / "latest.tmp"
        temporary.write_text(text)
        temporary.replace(folder / "latest.json")
        (folder / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")).write_text(
            text
        )
        print(text)
        mongo.close()
    finally:
        for conn in connections:
            conn.close()
        for name in created:
            docker("rm", "-f", "-v", name)


if __name__ == "__main__":
    main()
