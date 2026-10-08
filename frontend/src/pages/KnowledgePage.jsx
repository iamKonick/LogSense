import React, { useEffect, useState } from "react";
import { BookOpen, Plus } from "lucide-react";
import { api } from "../lib/api";
import { Modal } from "../components/Shared";

const tabs = [
  ["references", "Runbooks & references"],
  ["resolutions", "Verified resolutions"],
  ["patterns", "Observed patterns"],
  ["all", "All knowledge"],
];
export default function KnowledgePage({
  knowledge,
  setAddKnowledge,
  askReference,
}) {
  const [category, setCategory] = useState("references"),
    [q, setQ] = useState(""),
    [offset, setOffset] = useState(0),
    [result, setResult] = useState(null),
    [selected, setSelected] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      api(
        `/knowledge/search?category=${category}&q=${encodeURIComponent(q)}&offset=${offset}`,
      )
        .then((r) => {
          if (active) {
            setResult(r);
            setError("");
          }
        })
        .catch((e) => active && setError(e.message));
    }, 200);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [category, q, offset, knowledge]);
  return (
    <>
      <section className="panel knowledge-intro">
        <h2>Find a fix. Preserve what worked.</h2>
        <p>
          Use runbooks to guide checks, verified resolutions to learn from
          closed incidents, and observed patterns to recognise recurring
          messages. A pattern alone is not a diagnosis or a solution.
        </p>
        <button className="primary" onClick={() => setAddKnowledge(true)}>
          <Plus size={16} />
          Add reference
        </button>
      </section>
      <div
        className="knowledge-tabs"
        role="group"
        aria-label="Knowledge category"
      >
        {tabs.map(([id, label]) => (
          <button
            key={id}
            className={category === id ? "primary" : "secondary"}
            aria-pressed={category === id}
            onClick={() => {
              setCategory(id);
              setOffset(0);
              setResult(null);
            }}
          >
            {label}
          </button>
        ))}
      </div>
      <label className="knowledge-search">
        Search titles, content, or sources
        <input
          placeholder="e.g. database connection timeout"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOffset(0);
          }}
        />
      </label>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {!result ? (
        <p role="status">Loading knowledge…</p>
      ) : (
        <>
          <p className="hint">
            {result.total} matching entries · PDF pages are split into
            searchable passages
          </p>
          <div className="knowledge-grid">
            {result.items.map((k) => (
              <article className="knowledge-card" key={k.id}>
                <span className="asset-type">
                  <BookOpen size={14} />
                  {k.verified
                    ? "Engineer-verified resolution"
                    : k.kind === "pattern"
                      ? "Observed pattern"
                      : "Reference · not verified"}
                </span>
                <h3>{k.title}</h3>
                <p className="knowledge-preview">
                  {k.content.slice(0, 240)}
                  {k.content.length > 240 ? "…" : ""}
                </p>
                <footer>
                  <span>
                    {k.kind === "pattern"
                      ? `${k.observations} observations`
                      : k.source}
                  </span>
                  <button className="secondary" onClick={() => setSelected(k)}>
                    Read full entry
                  </button>
                </footer>
              </article>
            ))}
          </div>
          {result.total === 0 && (
            <section className="panel knowledge-intro">
              <h3>No entries found</h3>
              <p>
                {category === "resolutions"
                  ? "Close an incident with a verified root cause and resolution to preserve the solution here."
                  : category === "references"
                    ? "Add a runbook, troubleshooting note, or text-based PDF. The assistant can retrieve relevant passages with source citations."
                    : "Try a broader search or another category."}
              </p>
            </section>
          )}
          <div className="section-toolbar">
            <button
              className="secondary"
              disabled={!offset}
              onClick={() => setOffset(Math.max(0, offset - 24))}
            >
              Previous
            </button>
            <span>
              {result.total
                ? `${offset + 1}–${Math.min(offset + 24, result.total)} of ${result.total}`
                : "0 entries"}
            </span>
            <button
              className="secondary"
              disabled={offset + 24 >= result.total}
              onClick={() => setOffset(offset + 24)}
            >
              Next
            </button>
          </div>
        </>
      )}
      {selected && (
        <Modal title="Knowledge entry" close={() => setSelected(null)} wide>
          <h2>{selected.title}</h2>
          <p className="hint">
            {selected.source} ·{" "}
            {selected.verified
              ? "Engineer verified"
              : "Supporting evidence; assess before applying"}
          </p>
          <div className="knowledge-full">{selected.content}</div>
          <button className="primary" onClick={() => askReference(selected)}>
            Investigate with assistant
          </button>
        </Modal>
      )}
    </>
  );
}
