import React, { useEffect, useRef } from "react";
import { FileText, X } from "lucide-react";
import { labels } from "../lib/presentation";
export const Badge = ({ priority }) => (
  <span className={"badge " + priority}>
    <i />
    {priority}
    <span>{labels[priority]}</span>
  </span>
);
export function Empty({ icon: Icon = FileText, title, children }) {
  return (
    <div className="empty">
      <Icon size={30} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export function Modal({ title, close, children, wide = false }) {
  const dialog = useRef(null);
  const onClose = useRef(close);
  onClose.current = close;
  useEffect(() => {
    const previous = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = () => [
      ...dialog.current.querySelectorAll(
        "button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), a[href]",
      ),
    ];
    focusable()[0]?.focus();
    const h = (e) => {
      if (e.key === "Escape") onClose.current();
      if (e.key === "Tab") {
        const elements = focusable();
        const first = elements[0],
          last = elements[elements.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", h);
    return () => {
      document.removeEventListener("keydown", h);
      document.body.style.overflow = previousOverflow;
      previous?.focus();
    };
  }, []);
  return (
    <div className="overlay" onClick={close}>
      <section
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={"modal " + (wide ? "wide" : "")}
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <h2>{title}</h2>
          <button
            className="icon-button"
            aria-label="Close dialog"
            onClick={close}
          >
            <X size={21} />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}
