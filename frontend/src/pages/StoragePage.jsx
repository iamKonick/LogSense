import React, { useState, useEffect } from "react";
import { api } from "../lib/api";
const bytes = (n) =>
  new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(
    n / 1048576,
  ) + " MiB";
export default function StoragePage() {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [rate, setRate] = useState("");
  async function refresh() {
    try {
      setData(await api("/storage"));
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    refresh();
  }, []);
  const b = data?.benchmark,
    delta = b ? b.baseline.total_bytes - b.hybrid.total_bytes : 0;
  return (
    <>
      <div className="section-toolbar">
        <span>
          {data
            ? `Measured ${new Date(data.measured_at).toLocaleString()}`
            : "Loading storage measurements…"}
        </span>
        <button className="secondary" onClick={refresh}>
          Refresh measurements
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {data && (
        <>
          <div className="storage-cards">
            <section className="panel">
              <h2>MongoDB event storage</h2>
              <strong>{bytes(data.mongo.total_bytes)}</strong>
              <p>
                {data.mongo.count.toLocaleString()} lower-severity events ·
                allocated data + indexes
              </p>
            </section>
            <section className="panel">
              <h2>PostgreSQL application tables</h2>
              <strong>{bytes(data.postgres.relations_bytes)}</strong>
              <p>Includes knowledge, incidents, and routing receipts</p>
            </section>
            <section className="panel">
              <h2>PostgreSQL whole database</h2>
              <strong>{bytes(data.postgres.database_bytes)}</strong>
              <p>
                Includes database overhead; not additive to application tables.
              </p>
            </section>
          </div>
          <section className="panel storage-section">
            <h2>Where PostgreSQL space goes</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Table</th>
                    <th>Data & auxiliary storage</th>
                    <th>Indexes</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {data.postgres.tables.map((t) => (
                    <tr key={t.name}>
                      <td>{t.name}</td>
                      <td>{bytes(t.data_bytes)}</td>
                      <td>{bytes(t.index_bytes)}</td>
                      <td>{bytes(t.total_bytes)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="hint">
              Actual allocation includes free space and page overhead. Redis
              queues, backups, replication, and container images are excluded.
            </p>
          </section>
        </>
      )}
      <section className="panel storage-section">
        <h2>Controlled comparison</h2>
        {!b ? (
          <p>
            No completed benchmark yet. Live sizes alone cannot establish
            savings.
          </p>
        ) : (
          <>
            <p>
              {b.event_count.toLocaleString()} identical payloads ·{" "}
              {new Date(b.measured_at).toLocaleString()} · isolated local
              databases
            </p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Measurement</th>
                    <th>All PostgreSQL + event vectors</th>
                    <th>Hybrid routing</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    [
                      "Event data + indexes",
                      bytes(b.baseline.total_bytes),
                      bytes(b.hybrid.total_bytes),
                    ],
                    [
                      "Load elapsed time",
                      b.baseline.load_seconds.toFixed(3) + " s",
                      b.hybrid.load_seconds.toFixed(3) + " s",
                    ],
                    [
                      "Lookup workload elapsed time",
                      b.baseline.query_seconds.toFixed(3) + " s",
                      b.hybrid.query_seconds.toFixed(3) + " s",
                    ],
                    [
                      "Database CPU during workload",
                      b.baseline.cpu_seconds.toFixed(3) + " s",
                      b.hybrid.cpu_seconds.toFixed(3) + " s",
                    ],
                    [
                      "Observed database memory after workload",
                      bytes(b.baseline.memory_bytes),
                      bytes(b.hybrid.memory_bytes),
                    ],
                  ].map(([name, a, c]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td>{a}</td>
                      <td>{c}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h3>
              {bytes(Math.abs(delta))} {delta >= 0 ? "less" : "more"} event
              storage with hybrid routing
            </h3>
            <p>
              {delta >= 0
                ? "This sample shows an event-storage reduction."
                : "This sample does not support a storage-saving claim."}{" "}
              That is{" "}
              {Math.abs((delta / b.baseline.total_bytes) * 100).toFixed(1)}% of
              the baseline event allocation. Larger or different workloads may
              change the outcome.
            </p>
            <p>
              Observed hybrid database memory was{" "}
              {b.hybrid.memory_bytes > b.baseline.memory_bytes
                ? "higher"
                : "lower"}{" "}
              in this trial. This does not measure production server capacity or
              total running cost.
            </p>
            <label>
              Storage price per GB/month (your currency)
              <input
                type="number"
                min="0"
                step="0.01"
                value={rate}
                onChange={(e) => setRate(e.target.value)}
                placeholder="Enter your provider’s price"
              />
            </label>
            {rate !== "" && Number(rate) >= 0 && (
              <p>
                Estimated monthly disk-cost{" "}
                {delta >= 0 ? "reduction" : "increase"}:{" "}
                <strong>
                  {((Math.abs(delta) / 1e9) * Number(rate)).toFixed(6)}
                </strong>{" "}
                in your currency.
              </p>
            )}
            <p className="hint">{b.methodology}</p>
            <p className="hint">{b.limitations}</p>
          </>
        )}
      </section>
    </>
  );
}
