import redis
from redis.exceptions import ResponseError

STREAM = "logsense:events"
GROUPS = ("classification", "knowledge")


class Queue:
    def __init__(self, uri):
        self.redis = redis.Redis.from_url(uri, decode_responses=True)

    def initialize(self):
        for group in GROUPS:
            try:
                self.redis.xgroup_create(STREAM, group, "0", mkstream=True)
            except ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise

    def publish(self, event):
        # Atomic enqueue + receipt prevents concurrent exact-event duplicates.
        script = """
        if redis.call('EXISTS', KEYS[1]) == 1 then return 0 end
        redis.call('XADD', KEYS[2], '*', 'event', ARGV[1])
        redis.call('HSET', KEYS[1], 'classification', 'queued', 'knowledge', 'queued')
        return 1
        """
        return bool(
            self.redis.eval(
                script,
                2,
                "logsense:status:" + event.id,
                STREAM,
                event.model_dump_json(),
            )
        )

    def status(self, event_id):
        return self.redis.hgetall("logsense:status:" + event_id)

    def stats(self):
        groups = self.redis.xinfo_groups(STREAM)
        return {
            "groups": [
                {"name": r["name"], "pending": r["pending"], "lag": r.get("lag", 0)} for r in groups
            ],
            "dead_letters": self.redis.xlen("logsense:dead"),
            "workers": {g: bool(self.redis.exists("logsense:worker:" + g)) for g in GROUPS},
        }

    def next(self, group, consumer):
        # Recover messages left pending by a crashed worker before new work.
        idle_ms = 2000 if group == "knowledge" else 60000
        claimed = self.redis.xautoclaim(STREAM, group, consumer, idle_ms, "0-0", count=10)
        if claimed[1]:
            return claimed[1]
        rows = self.redis.xreadgroup(group, consumer, {STREAM: ">"}, count=10, block=2000)
        return rows[0][1] if rows else []

    def finish(self, group, entry_id, event_id, state="done"):
        key = "logsense:status:" + event_id
        with self.redis.pipeline() as pipe:
            pipe.hset(key, group, state)
            pipe.xack(STREAM, group, entry_id)
            pipe.execute()
        status = self.status(event_id)
        if all(status.get(g) in ("done", "failed") for g in GROUPS):
            # Both independent branches have finished; payload can be removed.
            self.redis.xdel(STREAM, entry_id)
            self.redis.expire(key, 7 * 86400)

    def fail(self, group, entry_id, event_id, payload):
        key = f"logsense:attempt:{group}:{entry_id}"
        attempts = self.redis.incr(key)
        self.redis.expire(key, 86400)
        self.redis.hset("logsense:status:" + event_id, group, "retrying")
        if attempts >= 5:
            self.redis.xadd(
                "logsense:dead",
                {
                    "group": group,
                    "event": payload,
                    "reason": "Processing failed five times; inspect worker logs",
                },
            )
            self.finish(group, entry_id, event_id, "failed")
