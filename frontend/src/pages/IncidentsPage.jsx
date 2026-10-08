import React from "react";
import { ChevronRight, ShieldCheck } from "lucide-react";
import { time } from "../lib/presentation";
import { Badge, Empty } from "../components/Shared";
import EventTable from "../components/EventTable";
export default function IncidentsPage({ incidents, setIncident }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Investigation queue</h2>
          <p>P4/P5 records enter as candidates for engineer review</p>
        </div>
        <span className="subtle-tag">{incidents.length} RECORDS</span>
      </div>
      {incidents.length ? (
        <div className="incident-list">
          {incidents.map((i) => (
            <button
              className="incident-row"
              key={i.id}
              onClick={() => setIncident(i)}
            >
              <Badge priority={i.priority} />
              <div>
                <strong>{i.message}</strong>
                <small>
                  {i.service} · {time(i.created_at)}
                </small>
              </div>
              <span className={"state " + i.status}>{i.status}</span>
              <ChevronRight size={16} />
            </button>
          ))}
        </div>
      ) : (
        <Empty icon={ShieldCheck} title="Nothing to investigate yet">
          High-severity events will appear here after ingestion.
        </Empty>
      )}
    </section>
  );
}
