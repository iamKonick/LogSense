import React from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Database,
  GitBranch,
  ShieldCheck,
  Terminal,
  TriangleAlert,
} from "lucide-react";
import { labels, colors } from "../lib/presentation";

import EventTable from "../components/EventTable";
export default function OverviewPage({
  overview,
  events,
  total,
  counts,
  open,
  setPage,
  setSelected,
}) {
  return (
    <>
      <div className="metrics">
        {[
          [Terminal, "Events processed", total, "Unique normalized events"],
          [TriangleAlert, "Needs investigation", open, "Open + investigating"],
          [
            BookOpen,
            "Knowledge assets",
            overview?.knowledge || 0,
            "Patterns & reference material",
          ],
          [Database, "Storage destinations", "02", "Severity-aware routing"],
        ].map(([Icon, title, value, sub]) => (
          <div className="metric" key={title}>
            <div>
              {title}
              <Icon size={17} />
            </div>
            <strong>
              {typeof value === "number" ? value.toLocaleString() : value}
            </strong>
            <small>
              {title === "Needs investigation" && <span className="mini-dot" />}
              {sub}
            </small>
          </div>
        ))}
      </div>
      <div className="overview-grid">
        <section className="panel severity-panel">
          <div className="panel-heading">
            <div>
              <h2>Severity distribution</h2>
              <p>P1 is lowest · P5 is highest</p>
            </div>
            <span className="subtle-tag">ALL PROCESSED EVENTS</span>
          </div>
          <div className="distribution">
            <div
              className="donut"
              style={{
                background: total
                  ? `conic-gradient(${Object.keys(labels)
                      .map(
                        (p, i, a) =>
                          `${colors[p]} ${(a.slice(0, i).reduce((n, k) => n + (counts[k] || 0), 0) / total) * 100}% ${(a.slice(0, i + 1).reduce((n, k) => n + (counts[k] || 0), 0) / total) * 100}%`,
                      )
                      .join(",")})`
                  : "#e7ebe7",
              }}
            >
              <div>
                <strong>{total.toLocaleString()}</strong>
                <small>total events</small>
              </div>
            </div>
            <div className="legend">
              {Object.keys(labels).map((p) => (
                <div key={p}>
                  <span style={{ background: colors[p] }} />
                  <b>{p}</b>
                  <label>{labels[p]}</label>
                  <strong>{counts[p] || 0}</strong>
                  <small>
                    {total ? Math.round(((counts[p] || 0) / total) * 100) : 0}%
                  </small>
                </div>
              ))}
            </div>
          </div>
        </section>
        <section className="panel routing-panel">
          <div className="panel-heading">
            <div>
              <h2>One event. The right destination.</h2>
              <p>Exclusive storage by predicted severity</p>
            </div>
            <GitBranch size={19} />
          </div>
          <div className="route">
            <span className="db-icon mongo">
              <Database size={22} />
            </span>
            <div>
              <h3>
                MongoDB <span>P1–P3</span>
              </h3>
              <p>Low & medium severity</p>
            </div>
            <strong>{overview?.storage?.MongoDB || 0}</strong>
          </div>
          <div className="route">
            <span className="db-icon postgres">
              <Database size={22} />
            </span>
            <div>
              <h3>
                PostgreSQL <span>P4–P5</span>
              </h3>
              <p>High-severity events</p>
            </div>
            <strong>{overview?.storage?.PostgreSQL || 0}</strong>
          </div>
          <div className="routing-note">
            <GitBranch size={15} />
            Knowledge extraction runs independently for every event.
          </div>
        </section>
      </div>
      <section className="pipeline-strip">
        <div>
          <Activity size={19} />
          <strong>Processing pipeline</strong>
        </div>
        {["Ingest", "Normalize", "Classify", "Route", "Learn"].map((v, i) => (
          <React.Fragment key={v}>
            <span>
              <i>{String(i + 1).padStart(2, "0")}</i>
              {v}
            </span>
            {i < 4 && <ArrowRight size={14} />}
          </React.Fragment>
        ))}
        <button onClick={() => setPage("Models & pipeline")}>
          View details
          <ArrowUpRight size={15} />
        </button>
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>
              Recent events{" "}
              <span className="count">{Math.min(events.length, 6)}</span>
            </h2>
            <p>Latest events across your connected sources</p>
          </div>
          <button
            className="text-button"
            onClick={() => setPage("Log explorer")}
          >
            Explore all logs
            <ArrowRight size={15} />
          </button>
        </div>
        <EventTable rows={events.slice(0, 6)} onSelect={setSelected} />
      </section>
      <div className="footer-note">
        <span>
          <ShieldCheck size={14} /> Human review stays in the loop
        </span>
        <span>
          {overview?.model?.mode?.startsWith("trained_")
            ? `Trained model active · ${overview.model.selected_model || "legacy ensemble"}`
            : "Rule fallback active · no trained model configured"}
        </span>
      </div>
    </>
  );
}
