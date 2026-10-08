import React, { useState } from "react";
import { api } from "../lib/api";
import { Modal } from "./Shared";
export default function KnowledgeModal({ close, done }) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [pdf, setPdf] = useState(false),
    [success, setSuccess] = useState("");
  return (
    <Modal title="Add a reference" close={close}>
      <div className="knowledge-tabs">
        <button
          className={!pdf ? "primary" : "secondary"}
          onClick={() => {
            setPdf(false);
            setError("");
          }}
        >
          Write a note
        </button>
        <button
          className={pdf ? "primary" : "secondary"}
          onClick={() => {
            setPdf(true);
            setError("");
          }}
        >
          Upload PDF
        </button>
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          setSuccess("");
          const form = new FormData(e.currentTarget);
          try {
            const r = await api(pdf ? "/knowledge/pdf" : "/knowledge", {
              method: "POST",
              body: pdf ? form : JSON.stringify(Object.fromEntries(form)),
            });
            done();
            if (pdf)
              setSuccess(
                `${r.inserted} searchable passages added from ${r.pages} pages. ${r.duplicates} existing passages skipped. ${r.empty_pages} pages had no extractable text. You can close this window.`,
              );
            else close();
          } catch (e) {
            setError(e.message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Title
          <input name="title" required minLength={3} maxLength={200} />
        </label>
        <label>
          Reference type
          <select name="kind">
            <option value="runbook">Runbook</option>
            <option value="troubleshooting">Troubleshooting guide</option>
            <option value="root_cause">Root-cause reference</option>
          </select>
        </label>
        {pdf ? (
          <label>
            PDF file
            <input
              name="file"
              type="file"
              accept="application/pdf,.pdf"
              required
            />
            <small>
              Text-based PDF, up to 10 MB and 100 pages. Scans need OCR first.
              Extracted passages are saved with filename and page citations; the
              original file is not retained.
            </small>
          </label>
        ) : (
          <>
            <label>
              Source / provenance
              <input
                name="source"
                required
                maxLength={500}
                placeholder="Document name, URL, or reference identifier"
              />
            </label>
            <label>
              Content
              <textarea
                name="content"
                required
                minLength={10}
                maxLength={20000}
                rows={8}
              />
            </label>
          </>
        )}
        <p className="hint">
          Include the symptoms, affected service, checks, and resolution steps.
          References become searchable by the assistant. Uploading a document
          does not mark its solution as verified; verification happens when an
          engineer closes an incident.
        </p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {success && (
          <p className="notice" role="status">
            {success}
          </p>
        )}
        <button disabled={busy} className="primary">
          {busy
            ? "Reading and saving…"
            : pdf
              ? "Upload and index PDF"
              : "Save reference"}
        </button>
      </form>
    </Modal>
  );
}
