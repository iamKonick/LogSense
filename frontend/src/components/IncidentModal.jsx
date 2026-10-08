import React, { useState, useEffect } from "react";
import { Check } from "lucide-react";
import { api } from "../lib/api";
import { time } from "../lib/presentation";
import { Badge, Modal } from "./Shared";
export default function IncidentModal({ incident, close, done }) {
  const [current, setCurrent] = useState(incident),
    [history, setHistory] = useState([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    api("/incidents/" + incident.id)
      .then((d) => {
        setCurrent({ ...incident, ...d });
        setHistory(d.history);
      })
      .catch((e) => setError(e.message));
  }, [incident.id]);
  return (
    <Modal title="Incident investigation" close={close} wide>
      <div className="detail-top">
        <Badge priority={incident.priority} />
        <span className={"state " + current.status}>{current.status}</span>
      </div>
      <pre className="log-message">{incident.message}</pre>
      {current.status === "resolved" ? (
        <>
          <h3>Verified root cause</h3>
          <p>{current.root_cause}</p>
          <h3>Resolution</h3>
          <p>{current.resolution}</p>
        </>
      ) : (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const data = Object.fromEntries(new FormData(e.currentTarget));
            setBusy(true);
            setError("");
            try {
              const result = await api("/incidents/" + incident.id, {
                method: "PATCH",
                body: JSON.stringify(data),
              });
              setCurrent({ ...incident, ...result });
              setHistory(result.history);
              done();
            } catch (e) {
              setError(e.message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Your name
            <input name="actor" required maxLength={100} />
          </label>
          <label>
            Next state
            <select
              name="status"
              key={current.status}
              defaultValue={
                current.status === "open" ? "investigating" : "resolved"
              }
            >
              {current.status === "open" ? (
                <option value="investigating">Start investigation</option>
              ) : (
                <>
                  <option value="resolved">
                    Resolve with verified findings
                  </option>
                  <option value="investigating">Continue investigation</option>
                </>
              )}
            </select>
          </label>
          <label>
            Investigation note
            <textarea name="note" required minLength={3} rows={2} />
          </label>
          {current.status === "investigating" && (
            <>
              <label>
                Root cause
                <textarea
                  name="root_cause"
                  rows={2}
                  placeholder="Required to resolve"
                />
              </label>
              <label>
                Successful resolution
                <textarea
                  name="resolution"
                  rows={3}
                  placeholder="Record what worked; required to resolve"
                />
              </label>
            </>
          )}
          {error && <p className="form-error">{error}</p>}
          <button disabled={busy} className="primary">
            <Check size={17} />
            Save findings
          </button>
        </form>
      )}
      {history.length > 0 && (
        <div className="history">
          <h3>Review history</h3>
          {history.map((h, i) => (
            <div key={i}>
              <strong>
                {h.actor} · {h.status}
              </strong>
              <small>{time(h.created_at)}</small>
              <p>{h.note}</p>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}
