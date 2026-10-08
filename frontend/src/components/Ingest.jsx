import React, { useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Database,
  Loader2,
  Upload,
} from "lucide-react";
import { api } from "../lib/api";

import { Modal } from "./Shared";
export default function Ingest({ close, done }) {
  const [mode, setMode] = useState("paste"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      let result;
      if (mode === "file") {
        result = await api("/ingest/file", { method: "POST", body: form });
      } else {
        const logs = String(form.get("message"))
          .split("\n")
          .filter((x) => x.trim())
          .map((message) => ({
            message,
            source: String(form.get("source")),
            service: String(form.get("service")),
            dataset: String(form.get("dataset")),
          }));
        result = await api("/ingest", {
          method: "POST",
          body: JSON.stringify({ logs }),
        });
      }
      done(
        `${result.accepted} events queued; ${result.duplicates} exact duplicates skipped.`,
      );
      close();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function demo() {
    setBusy(true);
    try {
      const timestamp = new Date().toISOString();
      const logs = [
        ["DEBUG", "Request context created", "gateway"],
        ["INFO", "Health check completed successfully", "gateway"],
        ["INFO", "Customer session established", "auth"],
        ["WARN", "Database query exceeded latency threshold", "checkout"],
        ["ERROR", "Connection refused to database primary", "checkout"],
        [
          "CRITICAL",
          "Payment worker out of memory; process terminated",
          "payments",
        ],
        ["INFO", "Cache refresh completed", "catalog"],
        ["WARN", "Upstream request timeout; retry scheduled", "gateway"],
        [
          "ERROR",
          "Payment authorization failed: upstream unavailable",
          "payments",
        ],
        ["INFO", "Order created successfully", "checkout"],
        ["DEBUG", "Cache key lookup started", "catalog"],
        ["INFO", "Background task completed", "worker"],
      ].map(([level, message, service], i) => ({
        message: JSON.stringify({ level, message, service }),
        source: "demo-synthetic",
        timestamp: new Date(Date.parse(timestamp) + i).toISOString(),
      }));
      const result = await api("/ingest", {
        method: "POST",
        body: JSON.stringify({ logs }),
      });
      done(`${result.accepted} clearly labeled synthetic demo events queued.`);
      close();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Bring your logs into focus" close={close}>
      <p className="hint">
        Events are normalized, classified, routed, and added to pattern
        knowledge.
      </p>
      <div className="tabs">
        {["paste", "file"].map((m) => (
          <button
            className={mode === m ? "selected" : ""}
            key={m}
            onClick={() => setMode(m)}
          >
            {m === "paste" ? "Paste logs" : "Upload file"}
          </button>
        ))}
      </div>
      <form onSubmit={submit}>
        <div className="form-row">
          <label>
            Source
            <input
              name="source"
              defaultValue="static"
              required
              maxLength={200}
            />
          </label>
          <label>
            Service
            <input
              name="service"
              defaultValue="application"
              required
              maxLength={100}
            />
          </label>
        </div>
        <label>
          Dataset
          <input
            name="dataset"
            maxLength={100}
            placeholder="Optional dataset name"
          />
        </label>
        {mode === "paste" ? (
          <label>
            Log messages · one per line
            <textarea
              required
              name="message"
              rows={7}
              placeholder={
                '2026-09-30T21:30:00Z ERROR Connection refused to database\n{"level":"INFO","message":"Service started"}'
              }
            />
          </label>
        ) : (
          <label className="file-label">
            <Upload size={26} />
            <strong>Choose a log file</strong>
            <span>
              UTF-8 .log, .txt, .jsonl or .csv · up to 2 MB / 1,000 rows
            </span>
            <input
              required
              name="file"
              type="file"
              accept=".log,.txt,.jsonl,.csv"
            />
          </label>
        )}
        {error && <p className="form-error">{error}</p>}
        <button className="primary" disabled={busy}>
          {busy ? (
            <Loader2 size={17} className="spin" />
          ) : (
            <ArrowDownToLine size={17} />
          )}
          Ingest events
        </button>
      </form>
      <div className="demo-option">
        <span>Just exploring?</span>
        <button className="text-button" onClick={demo} disabled={busy}>
          Load synthetic demo
          <ArrowRight size={14} />
        </button>
      </div>
    </Modal>
  );
}
