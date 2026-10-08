import React, { useState, useEffect, useRef } from "react";
import { RefreshCw, Search } from "lucide-react";
import { api } from "../lib/api";
import { labels } from "../lib/presentation";
import EventTable from "../components/EventTable";

export default function ExplorerPage({ setSelected }) {
  const [filters, setFilters] = useState({
    q: "",
    priority: "",
    source: "",
    dataset: "",
    sort_by: "received_at",
    order: "desc",
    limit: "100",
  });
  const [facets, setFacets] = useState({ sources: [], datasets: [] });
  const [result, setResult] = useState({ items: [], total: 0 });
  const [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [refresh, setRefresh] = useState(0);
  const sequence = useRef(0);
  useEffect(() => {
    const generation = ++sequence.current;
    setLoading(true);
    const timer = setTimeout(async () => {
      setLoading(true);
      setError("");
      try {
        const params = new URLSearchParams(
          Object.entries(filters).filter(([, v]) => v !== ""),
        );
        const [data, options] = await Promise.all([
          api("/explorer?" + params),
          api("/events/facets"),
        ]);
        if (generation === sequence.current) {
          setResult(data);
          setFacets(options);
        }
      } catch (e) {
        if (generation === sequence.current) setError(e.message);
      } finally {
        if (generation === sequence.current) setLoading(false);
      }
    }, 200);
    return () => {
      clearTimeout(timer);
      sequence.current++;
    };
  }, [filters, refresh]);
  const update = (key, value) =>
    setFilters((current) => ({ ...current, [key]: value }));
  return (
    <section className="panel">
      <div className="explorer-filters">
        <label className="explorer-search">
          Search
          <div className="search">
            <Search size={16} />
            <input
              aria-label="Search logs"
              value={filters.q}
              onChange={(e) => update("q", e.target.value)}
              placeholder="message or service…"
            />
          </div>
        </label>
        <label>
          Priority
          <select
            aria-label="Priority"
            value={filters.priority}
            onChange={(e) => update("priority", e.target.value)}
          >
            <option value="">All</option>
            {Object.keys(labels).map((p) => (
              <option key={p} value={p}>
                {p} · {labels[p]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Source
          <select
            aria-label="Source"
            value={filters.source}
            onChange={(e) => update("source", e.target.value)}
          >
            <option value="">All</option>
            {facets.sources.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Dataset
          <select
            aria-label="Dataset"
            value={filters.dataset}
            onChange={(e) => update("dataset", e.target.value)}
          >
            <option value="">All</option>
            {facets.datasets.map((v) => (
              <option key={v}>{v}</option>
            ))}
            {facets.has_unspecified_dataset && (
              <option value="__none__">Unspecified</option>
            )}
          </select>
        </label>
        <label>
          Sort by
          <select
            aria-label="Sort by"
            value={filters.sort_by}
            onChange={(e) => update("sort_by", e.target.value)}
          >
            <option value="received_at">Ingested at</option>
            <option value="timestamp">Event time</option>
            <option value="priority">Priority</option>
          </select>
        </label>
        <label>
          Order
          <select
            aria-label="Order"
            value={filters.order}
            onChange={(e) => update("order", e.target.value)}
          >
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
        </label>
        <label>
          Limit
          <select
            aria-label="Limit"
            value={filters.limit}
            onChange={(e) => update("limit", e.target.value)}
          >
            {[25, 50, 100, 250, 500, 1000].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <button
          className="secondary"
          disabled={loading}
          onClick={() => setRefresh((n) => n + 1)}
        >
          <RefreshCw size={14} className={loading ? "spin" : ""} />
          Refresh
        </button>
      </div>
      {error && (
        <div role="alert" className="error">
          {error}
        </div>
      )}
      <div className="explorer-summary" role="status">
        {loading
          ? "Loading matching logs…"
          : `${result.items.length.toLocaleString()} shown · ${result.total.toLocaleString()} matching events`}
        <span>Filters apply across both databases</span>
      </div>
      {loading ? (
        <div className="empty" role="status">
          Loading matching logs…
        </div>
      ) : error ? null : (
        <EventTable
          rows={result.items}
          onSelect={setSelected}
          emptyTitle="No matching events"
          emptyDescription="Change the filters or ingest logs from your sources."
          showDataset
        />
      )}
    </section>
  );
}
