import React from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Layers,
  Loader2,
  Sparkles,
  X,
} from "lucide-react";

import { Badge } from "../components/Shared";
import EventTable from "../components/EventTable";
export default function AssistantPage({
  provider,
  setProvider,
  providerModel,
  setProviderModel,
  providerKey,
  setProviderKey,
  context,
  setContext,
  answer,
  question,
  setQuestion,
  ask,
  asking,
}) {
  return (
    <div className="assistant-layout">
      <section className="panel chat">
        <div className="panel-heading">
          <div className="assistant-title">
            <span className="assistant-icon">
              <Sparkles size={22} />
            </span>
            <div>
              <h2>Your investigation partner</h2>
              <p>Grounded in your knowledge base</p>
            </div>
          </div>
          <span className="subtle-tag">HUMAN REVIEW</span>
        </div>
        <div className="provider-settings">
          <label>
            Answer provider
            <select
              aria-label="Answer provider"
              value={provider}
              disabled={asking}
              onChange={(e) => {
                setProvider(e.target.value);
                setProviderModel(
                  e.target.value === "openai" ? "gpt-5.4-mini" : "qwen2.5:3b",
                );
                setProviderKey("");
              }}
            >
              <option value="ollama">Ollama · local</option>
              <option value="openai">OpenAI · cloud</option>
              <option value="evidence">Retrieved evidence only</option>
            </select>
          </label>
          {provider !== "evidence" && (
            <label>
              Model
              <input
                aria-label="Model"
                value={providerModel}
                disabled={asking}
                onChange={(e) => setProviderModel(e.target.value)}
              />
            </label>
          )}
          {provider === "openai" && (
            <label className="provider-key">
              OpenAI API key
              <input
                aria-label="OpenAI API key"
                type="password"
                autoComplete="off"
                spellCheck={false}
                value={providerKey}
                disabled={asking}
                onChange={(e) => setProviderKey(e.target.value)}
                placeholder="Enter key, or use server configuration"
              />
              <button
                className="secondary"
                type="button"
                onClick={() => setProviderKey("")}
                disabled={asking || !providerKey}
              >
                Clear key
              </button>
            </label>
          )}
          <p className="hint">
            {provider === "openai"
              ? "Your question, event and retrieved passages are sent to OpenAI when you ask. The entered key is held in memory for this session, not saved; reloading or changing provider clears it."
              : provider === "ollama"
                ? "Uses the local Ollama service. The selected model must be installed on the server."
                : "Shows relevant sources without generating an answer."}
          </p>
        </div>
        {context && (
          <div className="context">
            <Badge priority={context.prediction.priority} />
            <span>{context.message}</span>
            <button
              aria-label="Remove event context"
              onClick={() => setContext(null)}
            >
              <X size={15} />
            </button>
          </div>
        )}
        <div className="conversation">
          {answer ? (
            <>
              <div className="answer-mode">
                <Sparkles size={15} />
                {answer.generated
                  ? `${answer.mode === "rag_openai" ? "OpenAI" : "Ollama"} · retrieval-augmented answer`
                  : "Retrieved evidence · generation not used"}
              </div>
              {answer.notice && <p className="hint">{answer.notice}</p>}
              <div className="answer">{answer.answer}</div>
              <div className="answer-footnote">{answer.confidence_note}</div>
            </>
          ) : (
            <div className="chat-welcome">
              <span>
                <Sparkles size={29} />
              </span>
              <h2>
                Start with a question.
                <br />
                Follow the evidence.
              </h2>
              <p>
                Ask about an error, compare a recurring pattern, or open an
                event from the log explorer.
              </p>
              <div className="suggestions">
                {[
                  "What could cause a database connection failure?",
                  "Which patterns explain repeated timeouts?",
                ].map((s) => (
                  <button key={s} onClick={() => setQuestion(s)}>
                    {s}
                    <ArrowUpRight size={14} />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
        <form className="question-form" onSubmit={ask}>
          <textarea
            aria-label="Question"
            required
            minLength={3}
            maxLength={8000}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about your logs or an incident…"
          />
          <button
            className="primary"
            disabled={
              asking ||
              question.trim().length < 3 ||
              (provider !== "evidence" && !providerModel.trim())
            }
            aria-label="Ask LogSense"
          >
            {asking ? (
              <Loader2 className="spin" size={19} />
            ) : (
              <ArrowRight size={20} />
            )}
          </button>
        </form>
        <div className="chat-caption">
          Suggestions support investigation. LogSense does not execute
          remediation.
        </div>
      </section>
      <aside className="panel evidence">
        <h2>
          <BookOpen size={18} /> Evidence trail
        </h2>
        <p>Sources retrieved for your question appear here.</p>
        {answer?.sources?.length ? (
          answer.sources.map((s, i) => (
            <div className="source-card" key={s.id}>
              <span>
                [{i + 1}] {s.kind}
              </span>
              <h3>{s.title}</h3>
              <small>{s.source}</small>
              <div>
                Similarity {Math.round(s.score * 100)}%
                {s.verified ? " · verified resolution" : ""}
              </div>
            </div>
          ))
        ) : (
          <div className="evidence-empty">
            <Layers size={28} />
            <span>No sources retrieved yet</span>
          </div>
        )}
      </aside>
    </div>
  );
}
