import re
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from app.domain.models import Event, IncidentUpdate, Prediction
from app.knowledge.embedding import vector_literal
from app.preprocessing.parser import redact
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool
from pymongo import DESCENDING, MongoClient


def destination(priority: str) -> str:
    if priority in ("P1", "P2", "P3"):
        return "MongoDB"
    if priority in ("P4", "P5"):
        return "PostgreSQL"
    raise ValueError("Unknown priority")


class Repository:
    def __init__(self, settings):
        self.mongo = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=5000)
        self.logs = self.mongo.logsense.events
        self.pool = ConnectionPool(
            settings.postgres_uri,
            min_size=1,
            max_size=8,
            kwargs={"row_factory": dict_row},
            timeout=10,
            open=True,
        )
        self.pool.wait(timeout=20)

    def initialize(self):
        self.mongo.admin.command("ping")
        self.logs.create_index([("timestamp", DESCENDING)])
        self.logs.create_index("prediction.priority")
        self.logs.create_index("received_at")
        self.logs.create_index("source")
        self.logs.create_index("dataset")
        with self.pool.connection() as conn:
            conn.execute(Path(__file__).with_name("schema.sql").read_text())

    def close(self):
        self.pool.close()
        self.mongo.close()

    def health(self):
        self.mongo.admin.command("ping")
        with self.pool.connection() as conn:
            conn.execute("SELECT 1")
        return {"MongoDB": "healthy", "PostgreSQL": "healthy"}

    def save_event(self, event: Event, prediction: Prediction):
        # Persist the first routing decision before the database write. A retry,
        # including after model replacement, must use the same destination.
        with self.pool.connection() as conn:
            conn.execute(
                "INSERT INTO routing_receipts(event_id,prediction) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                (event.id, Jsonb(prediction.model_dump())),
            )
            first = conn.execute(
                "SELECT prediction FROM routing_receipts WHERE event_id=%s", (event.id,)
            ).fetchone()
            prediction = Prediction.model_validate(first["prediction"])
        target = destination(prediction.priority)
        payload = event.model_dump() | {
            "prediction": prediction.model_dump(),
            "storage": target,
        }
        if target == "MongoDB":
            self.logs.update_one({"_id": event.id}, {"$setOnInsert": payload}, upsert=True)
        else:
            with self.pool.connection() as conn:
                conn.execute(
                    "INSERT INTO events(id,priority,timestamp,payload) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (event.id, prediction.priority, event.timestamp, Jsonb(payload)),
                )
                conn.execute(
                    "INSERT INTO incidents(id) VALUES(%s) ON CONFLICT DO NOTHING",
                    (event.id,),
                )
        return payload

    def event(self, event_id):
        with self.pool.connection() as conn:
            row = conn.execute("SELECT payload FROM events WHERE id=%s", (event_id,)).fetchone()
        return row["payload"] if row else self.logs.find_one({"_id": event_id}, {"_id": 0})

    def explore(
        self,
        priority=None,
        query="",
        limit=100,
        source=None,
        dataset=None,
        sort_by="received_at",
        order="desc",
    ):
        if sort_by not in {"received_at", "timestamp", "priority"} or order not in {"asc", "desc"}:
            raise ValueError("Invalid sort option")
        selector = {}
        clauses, parameters = [], []
        if priority:
            selector["prediction.priority"] = priority
            clauses.append("priority=%s")
            parameters.append(priority)
        if source:
            selector["source"] = source
            clauses.append("payload->>'source'=%s")
            parameters.append(source)
        if dataset:
            if dataset == "__none__":
                selector["dataset"] = {"$in": [None, ""]}
                clauses.append("COALESCE(payload->>'dataset','')=''")
            else:
                selector["dataset"] = dataset
                clauses.append("payload->>'dataset'=%s")
                parameters.append(dataset)
        if query:
            matcher = {"$regex": re.escape(query), "$options": "i"}
            selector["$or"] = [{"message": matcher}, {"service": matcher}]
            clauses.append(
                "(strpos(lower(payload->>'message'),lower(%s))>0 OR strpos(lower(payload->>'service'),lower(%s))>0)"
            )
            parameters.extend([query, query])
        direction = -1 if order == "desc" else 1
        mongo_sort = "prediction.priority" if sort_by == "priority" else sort_by
        sql_sort = {
            "priority": "priority",
            "timestamp": "timestamp",
            "received_at": "(payload->>'received_at')::timestamptz",
        }[sort_by]
        where = " AND ".join(clauses) or "TRUE"
        sql_direction = "DESC" if order == "desc" else "ASC"
        low, low_count = [], 0
        if priority not in ("P4", "P5"):
            low_count = self.logs.count_documents(selector)
            low = list(
                self.logs.find(selector, {"_id": 0})
                .sort([(mongo_sort, direction), ("id", direction)])
                .limit(limit)
            )
        high, high_count = [], 0
        if priority not in ("P1", "P2", "P3"):
            with self.pool.connection() as conn:
                high_count = conn.execute(
                    f"SELECT count(*) AS n FROM events WHERE {where}", parameters
                ).fetchone()["n"]
                high = conn.execute(
                    f"SELECT payload FROM events WHERE {where} ORDER BY {sql_sort} {sql_direction}, id {sql_direction} LIMIT %s",
                    [*parameters, limit],
                ).fetchall()

        def key(event):
            value = (
                event["prediction"]["priority"]
                if sort_by == "priority"
                else datetime.fromisoformat(event[sort_by]).timestamp()
            )
            return value, event["id"]

        items = sorted(low + [row["payload"] for row in high], key=key, reverse=order == "desc")[
            :limit
        ]
        return {"items": items, "total": low_count + high_count, "limit": limit}

    def events(self, priority=None, query="", limit=100):
        return self.explore(priority=priority, query=query, limit=limit, sort_by="timestamp")[
            "items"
        ]

    def event_facets(self):
        sources = set(self.logs.distinct("source"))
        datasets = set(self.logs.distinct("dataset"))
        missing_dataset = bool(self.logs.count_documents({"dataset": {"$in": [None, ""]}}))
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT payload->>'source' AS source, COALESCE(payload->>'dataset','') AS dataset FROM events"
            ).fetchall()
        for row in rows:
            sources.add(row["source"])
            datasets.add(row["dataset"])
            missing_dataset = missing_dataset or not row["dataset"]
        return {
            "sources": sorted(x for x in sources if x),
            "datasets": sorted(x for x in datasets if x),
            "has_unspecified_dataset": missing_dataset,
        }

    def stats(self):
        counts = {f"P{i}": 0 for i in range(1, 6)}
        for row in self.logs.aggregate(
            [{"$group": {"_id": "$prediction.priority", "count": {"$sum": 1}}}]
        ):
            counts[row["_id"]] = row["count"]
        with self.pool.connection() as conn:
            for row in conn.execute(
                "SELECT priority,count(*) AS count FROM events GROUP BY priority"
            ).fetchall():
                counts[row["priority"]] = row["count"]
            incident_counts = conn.execute(
                "SELECT status,count(*) AS count FROM incidents GROUP BY status"
            ).fetchall()
            knowledge = conn.execute("SELECT count(*) AS count FROM knowledge").fetchone()["count"]
        return {
            "priorities": counts,
            "total": sum(counts.values()),
            "knowledge": knowledge,
            "incidents": {r["status"]: r["count"] for r in incident_counts},
            "storage": {
                "MongoDB": sum(counts[p] for p in ("P1", "P2", "P3")),
                "PostgreSQL": counts["P4"] + counts["P5"],
            },
        }

    def observe(self, event: Event):
        classified = self.event(event.id)
        if classified is None:
            raise ValueError("Knowledge observation requires a persisted classification")
        prediction = classified["prediction"]
        pattern_id = sha256((event.service + "\n" + event.template).encode()).hexdigest()
        title = f"{event.service}: {event.template[:130]}"
        content = f"Observed log pattern for service {event.service}: {event.template}. This observation alone does not establish a root cause or resolution."
        with self.pool.connection() as conn:
            conn.execute(
                "INSERT INTO knowledge(id,title,content,kind,source,embedding) VALUES(%s,%s,%s,'pattern',%s,%s::vector) ON CONFLICT DO NOTHING",
                (
                    pattern_id,
                    title,
                    content,
                    "log:" + event.id,
                    vector_literal(content),
                ),
            )
            inserted = conn.execute(
                "INSERT INTO knowledge_observations(event_id,knowledge_id,observed_at,predicted_priority,model_version) VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING event_id",
                (
                    event.id,
                    pattern_id,
                    event.timestamp,
                    prediction["priority"],
                    prediction["model_version"],
                ),
            ).fetchone()
            if inserted:
                conn.execute(
                    "UPDATE knowledge SET observations=observations+1,updated_at=now() WHERE id=%s",
                    (pattern_id,),
                )

    def add_knowledge(self, title, content, source, kind, verified=False, asset_id=None):
        asset_id = asset_id or str(uuid4())
        title, content, source = map(redact, (title, content, source))
        with self.pool.connection() as conn:
            conn.execute(
                "INSERT INTO knowledge(id,title,content,kind,source,verified,embedding) VALUES(%s,%s,%s,%s,%s,%s,%s::vector) ON CONFLICT DO NOTHING",
                (
                    asset_id,
                    title,
                    content,
                    kind,
                    source,
                    verified,
                    vector_literal(content),
                ),
            )
        return asset_id

    def knowledge(self, limit=100):
        with self.pool.connection() as conn:
            return conn.execute(
                "SELECT id,title,content,kind,source,verified,observations,updated_at FROM knowledge ORDER BY updated_at DESC LIMIT %s",
                (limit,),
            ).fetchall()

    def search_knowledge(self, q="", category="references", offset=0, limit=24):
        categories = {
            "references": "kind NOT IN ('pattern','resolution')",
            "patterns": "kind='pattern'",
            "resolutions": "kind='resolution'",
            "all": "TRUE",
        }
        clause = categories[category]
        with self.pool.connection() as conn:
            counts = conn.execute(
                "SELECT kind,count(*) AS count FROM knowledge GROUP BY kind"
            ).fetchall()
            params = (q, q, q)
            where = f"{clause} AND (strpos(lower(title),lower(%s))>0 OR strpos(lower(content),lower(%s))>0 OR strpos(lower(source),lower(%s))>0)"
            total = conn.execute(
                f"SELECT count(*) AS n FROM knowledge WHERE {where}", params
            ).fetchone()["n"]
            items = conn.execute(
                f"SELECT id,title,content,kind,source,verified,observations,updated_at FROM knowledge WHERE {where} ORDER BY updated_at DESC,id LIMIT %s OFFSET %s",
                (*params, limit, offset),
            ).fetchall()
        return {"items": items, "total": total, "counts": {r["kind"]: r["count"] for r in counts}}

    def add_pdf_reference(self, extracted):
        inserted = 0
        with self.pool.connection() as conn:
            for chunk in extracted["chunks"]:
                result = conn.execute(
                    "INSERT INTO knowledge(id,title,content,kind,source,verified,embedding) VALUES(%s,%s,%s,%s,%s,false,%s::vector) ON CONFLICT DO NOTHING",
                    (
                        chunk["id"],
                        chunk["title"],
                        chunk["content"],
                        chunk["kind"],
                        chunk["source"],
                        vector_literal(chunk["content"]),
                    ),
                )
                inserted += result.rowcount
        return {
            "document_id": extracted["document_id"],
            "pages": extracted["pages"],
            "empty_pages": extracted["empty_pages"],
            "inserted": inserted,
            "duplicates": len(extracted["chunks"]) - inserted,
        }

    def storage_findings(self):
        from datetime import timezone

        mongo = self.logs.database.command("collStats", "events", scale=1)
        with self.pool.connection() as conn:
            tables = conn.execute(
                "SELECT relname AS name,pg_total_relation_size(relid) AS total_bytes,pg_table_size(relid) AS data_bytes,pg_indexes_size(relid) AS index_bytes,n_live_tup AS estimated_rows FROM pg_stat_user_tables ORDER BY relname"
            ).fetchall()
            database = conn.execute(
                "SELECT pg_database_size(current_database()) AS bytes"
            ).fetchone()["bytes"]
        return {
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "mongo": {
                "count": mongo["count"],
                "logical_bytes": mongo["size"],
                "data_bytes": mongo["storageSize"],
                "index_bytes": mongo["totalIndexSize"],
                "total_bytes": mongo["storageSize"] + mongo["totalIndexSize"],
            },
            "postgres": {
                "database_bytes": database,
                "tables": tables,
                "relations_bytes": sum(t["total_bytes"] for t in tables),
            },
        }

    def retrieve(self, query, limit=6):
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT id,title,content,kind,source,verified,observations,1-(embedding <=> %s::vector) AS score FROM knowledge ORDER BY embedding <=> %s::vector LIMIT %s",
                (vector_literal(query), vector_literal(query), limit),
            ).fetchall()
        return [r for r in rows if r["score"] is not None and 0.15 <= r["score"] <= 1.000001]

    def incidents(self):
        with self.pool.connection() as conn:
            return conn.execute(
                "SELECT i.*,e.priority,e.payload->>'message' AS message,e.payload->>'service' AS service FROM incidents i JOIN events e USING(id) ORDER BY i.created_at DESC LIMIT 200"
            ).fetchall()

    def incident(self, event_id):
        with self.pool.connection() as conn:
            row = conn.execute("SELECT * FROM incidents WHERE id=%s", (event_id,)).fetchone()
            if row:
                row["history"] = conn.execute(
                    "SELECT status,actor,note,created_at FROM incident_history WHERE incident_id=%s ORDER BY id",
                    (event_id,),
                ).fetchall()
            return row

    def update_incident(self, event_id, update: IncidentUpdate):
        if update.status == "resolved" and (
            not update.root_cause.strip() or not update.resolution.strip()
        ):
            raise ValueError("Record a verified root cause and resolution before closing")
        with self.pool.connection() as conn:
            row = conn.execute(
                "SELECT status FROM incidents WHERE id=%s FOR UPDATE", (event_id,)
            ).fetchone()
            if not row:
                raise KeyError(event_id)
            allowed = {
                "open": {"investigating"},
                "investigating": {"investigating", "resolved"},
                "resolved": set(),
            }
            if update.status not in allowed[row["status"]]:
                raise ValueError(f"Cannot move from {row['status']} to {update.status}")
            cause, resolution, note, actor = map(
                redact,
                (update.root_cause, update.resolution, update.note, update.actor),
            )
            conn.execute(
                "UPDATE incidents SET status=%s,root_cause=%s,resolution=%s,updated_at=now() WHERE id=%s",
                (update.status, cause, resolution, event_id),
            )
            conn.execute(
                "INSERT INTO incident_history(incident_id,status,actor,note) VALUES(%s,%s,%s,%s)",
                (event_id, update.status, actor, note),
            )
            if update.status == "resolved":
                event = conn.execute(
                    "SELECT payload FROM events WHERE id=%s", (event_id,)
                ).fetchone()["payload"]
                title = f"Resolved: {event['service']} — {event['message'][:100]}"
                content = f"Incident: {event['message']}\nVerified root cause: {cause}\nVerified resolution: {resolution}\nReported by: {actor}"
                conn.execute(
                    "INSERT INTO knowledge(id,title,content,kind,source,verified,embedding) VALUES(%s,%s,%s,'resolution',%s,true,%s::vector) ON CONFLICT DO NOTHING",
                    (
                        "resolution:" + event_id,
                        title,
                        content,
                        "incident:" + event_id,
                        vector_literal(content),
                    ),
                )
        return self.incident(event_id)
