import React from "react";
import { ChevronRight, Database } from "lucide-react";
import { time } from "../lib/presentation";
import { Badge, Empty } from "./Shared";
export default function EventTable({
  rows,
  onSelect,
  showDataset = false,
  emptyTitle = "Your logs start here",
  emptyDescription = "Import a log file, paste an event, or load the labeled demo.",
}) {
  return rows.length ? (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Severity</th>
            <th>Event / service</th>
            {showDataset && <th>Dataset</th>}
            <th>Destination</th>
            <th>Observed</th>
            {showDataset && <th>Ingested at</th>}
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => (
            <tr key={e.id} onClick={() => onSelect(e)}>
              <td>
                <Badge priority={e.prediction.priority} />
              </td>
              <td className="message-cell">
                <button
                  className="event-link"
                  onClick={(x) => {
                    x.stopPropagation();
                    onSelect(e);
                  }}
                >
                  {e.message}
                </button>
                <small>
                  <span className="service-dot" />
                  {e.service} <span className="dim">/ {e.source}</span>
                </small>
              </td>
              {showDataset && <td>{e.dataset || "Unspecified"}</td>}
              <td>
                <span className="storage-label">
                  <Database size={13} />
                  {e.storage}
                </span>
              </td>
              <td className="time">{time(e.timestamp)}</td>
              {showDataset && <td className="time">{time(e.received_at)}</td>}
              <td>
                <ChevronRight size={16} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty title={emptyTitle}>{emptyDescription}</Empty>
  );
}
