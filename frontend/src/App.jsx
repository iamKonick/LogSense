import React, { useState, useEffect, useCallback } from "react";
import {
  Activity,
  Database,
  FileText,
  BarChart3,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  GitBranch,
  LayoutDashboard,
  Plus,
  PanelLeftClose,
  PanelLeftOpen,
  ShieldCheck,
  Settings,
  Sparkles,
  Terminal,
  TriangleAlert,
} from "lucide-react";
import { api, getApiKey, setApiKey } from "./lib/api";
import { time } from "./lib/presentation";
import { Badge, Modal } from "./components/Shared";
const nav = [
  ["Overview", LayoutDashboard],
  ["Log explorer", Terminal],
  ["Incidents", TriangleAlert],
  ["Knowledge base", BookOpen],
  ["AI assistant", Sparkles],
  ["Model evaluation", BarChart3],
  ["Models & pipeline", GitBranch],
  ["Storage findings", Database],
  ["Documentation", FileText],
];
import Ingest from "./components/Ingest";
import KnowledgeModal from "./components/KnowledgeModal";
import IncidentModal from "./components/IncidentModal";
import OverviewPage from "./pages/OverviewPage";
import ExplorerPage from "./pages/ExplorerPage";
import IncidentsPage from "./pages/IncidentsPage";
import KnowledgePage from "./pages/KnowledgePage";
import AssistantPage from "./pages/AssistantPage";
import ModelsPage from "./pages/ModelsPage";
import EvaluationPage from "./pages/EvaluationPage";
import DocumentationPage from "./pages/DocumentationPage";
import StoragePage from "./pages/StoragePage";
export default function App() {
  const [sidebarHidden, setSidebarHidden] = useState(() => {
    try {
      return localStorage.getItem("logsense-sidebar-hidden") === "true";
    } catch {
      return false;
    }
  });
  function toggleSidebar() {
    const hidden = !sidebarHidden;
    setSidebarHidden(hidden);
    try {
      localStorage.setItem("logsense-sidebar-hidden", String(hidden));
    } catch {
      // Navigation remains usable when browser storage is unavailable.
    }
  }
  const [page, setPage] = useState("Overview"),
    [overview, setOverview] = useState(null),
    [events, setEvents] = useState([]),
    [incidents, setIncidents] = useState([]),
    [knowledge, setKnowledge] = useState([]),
    [error, setError] = useState(""),
    [upload, setUpload] = useState(false),
    [selected, setSelected] = useState(null),
    [incident, setIncident] = useState(null),
    [addKnowledge, setAddKnowledge] = useState(false),
    [question, setQuestion] = useState(""),
    [context, setContext] = useState(null),
    [answer, setAnswer] = useState(null),
    [asking, setAsking] = useState(false),
    [auth, setAuth] = useState(false),
    [notice, setNotice] = useState("");
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, [page]);
  const refresh = useCallback(async () => {
    try {
      const [o, e, i, k] = await Promise.all([
        api("/overview"),
        api("/events?limit=200"),
        api("/incidents"),
        api("/knowledge"),
      ]);
      setOverview(o);
      setEvents(e);
      setIncidents(i);
      setKnowledge(k);
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }, []);
  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    const h = () => setAuth(true);
    window.addEventListener("logsense-auth", h);
    return () => {
      clearInterval(interval);
      window.removeEventListener("logsense-auth", h);
    };
  }, [refresh]);
  useEffect(() => {
    if (notice) {
      const t = setTimeout(() => setNotice(""), 6000);
      return () => clearTimeout(t);
    }
  }, [notice]);
  const counts = overview?.priorities || {},
    total = overview?.total || 0,
    open =
      (overview?.incidents?.open || 0) +
      (overview?.incidents?.investigating || 0),
    workers = overview?.queue?.workers || {},
    healthy = overview && Object.values(workers).every(Boolean) && !error;
  const askAbout = (e) => {
    setContext(e);
    setQuestion(
      "What evidence could explain this event, and what should I check next?",
    );
    setPage("AI assistant");
    setSelected(null);
  };
  async function ask(e) {
    e.preventDefault();
    setAsking(true);
    setAnswer(null);
    try {
      setAnswer(
        await api("/assistant", {
          method: "POST",
          body: JSON.stringify({ question, event_id: context?.id }),
        }),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setAsking(false);
    }
  }
  return (
    <div className={`app${sidebarHidden ? " sidebar-hidden" : ""}`}>
      <aside
        className="sidebar"
        id="workspace-sidebar"
        aria-label="Workspace navigation"
      >
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("Overview");
          }}
        >
          <span className="brand-mark">
            <Activity size={24} />
          </span>
          LogSense<span className="brand-dot">.</span>
        </a>
        <div className="workspace">Research Workspace</div>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {nav.map(([name, Icon]) => (
            <button
              key={name}
              aria-label={name}
              title={name}
              aria-current={page === name ? "page" : undefined}
              className={page === name ? "active" : ""}
              onClick={() => {
                setPage(name);
                setError("");
              }}
            >
              <Icon size={18} />
              <span>{name}</span>
              {name === "Incidents" && open > 0 && <b>{open}</b>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-note">
            <ShieldCheck size={17} />
            <div>
              Built for investigation
              <small>Every finding, linked to evidence.</small>
            </div>
          </div>
          <button className="profile" onClick={() => setAuth(true)}>
            <Settings size={18} />
            <div>
              Connection settings<small>Local workspace</small>
            </div>
            <CircleHelp size={16} />
          </button>
        </div>
      </aside>
      <main>
        <div className="topbar">
          <div>
            <button
              className="sidebar-toggle"
              onClick={toggleSidebar}
              aria-label={sidebarHidden ? "Show sidebar" : "Hide sidebar"}
              title={sidebarHidden ? "Show sidebar" : "Hide sidebar"}
              aria-expanded={!sidebarHidden}
              aria-controls="workspace-sidebar"
            >
              {sidebarHidden ? (
                <PanelLeftOpen size={20} />
              ) : (
                <PanelLeftClose size={20} />
              )}
            </button>
            <span className="breadcrumb-workspace">
              Workspace <ChevronRight size={13} />
            </span>{" "}
            <strong>{page}</strong>
          </div>
          <div>
            <span className={"status-dot " + (healthy ? "" : "amber")} />
            {healthy
              ? "Pipeline connected"
              : overview
                ? "Check pipeline status"
                : "Connecting"}
            <span className="divider" />
            <span className="local-pill">LOCAL</span>
            <button
              className="sidebar-toggle topbar-settings"
              aria-label="Connection settings"
              title="Connection settings"
              onClick={() => setAuth(true)}
            >
              <Settings size={18} />
            </button>
          </div>
        </div>
        <div className="content">
          <div className="page-heading">
            <div className="eyebrow">
              {page === "Overview"
                ? "FROM LOGS TO UNDERSTANDING"
                : "LOGSENSE WORKSPACE"}
            </div>
            <div className="heading-row">
              <div>
                <h1>{page === "Overview" ? "Operational overview" : page}</h1>
                <p>
                  {
                    {
                      Overview:
                        "A clear view of your events, their severity, and what needs attention.",
                      "Log explorer":
                        "Follow each event from its source to its storage destination.",
                      Incidents:
                        "Investigate high-severity events and preserve what you learn.",
                      "Knowledge base":
                        "Observed patterns, reference material, and engineer-verified resolutions.",
                      "AI assistant":
                        "Investigate with evidence from your operational knowledge.",
                      "Model evaluation":
                        "Compare severity predictions on held-out logs and inspect the evidence behind the scores.",
                      "Storage findings":
                        "Measure storage use and compare the routing strategy with an all-PostgreSQL baseline.",
                      Documentation:
                        "A practical guide to using this research prototype.",
                      "Models & pipeline":
                        "Inspect how LogSense turns raw events into informed decisions.",
                    }[page]
                  }
                </p>
              </div>
              {["Overview", "Log explorer"].includes(page) && (
                <button className="primary" onClick={() => setUpload(true)}>
                  <Plus size={17} />
                  Ingest logs
                </button>
              )}
            </div>
          </div>
          {error && (
            <div role="alert" className="error">
              <TriangleAlert size={17} />
              {error}
              <button onClick={refresh}>Retry</button>
            </div>
          )}
          {notice && (
            <div role="status" className="notice">
              <CheckCircle2 size={17} />
              {notice}
            </div>
          )}
          {page === "Overview" && !overview && (
            <div className="panel empty" role="status">
              {error
                ? "Dashboard data is unavailable. Retry the connection above."
                : "Loading dashboard…"}
            </div>
          )}
          {page === "Overview" && overview && (
            <OverviewPage
              overview={overview}
              events={events}
              total={total}
              counts={counts}
              open={open}
              setPage={setPage}
              setSelected={setSelected}
            />
          )}
          {page === "Log explorer" && (
            <ExplorerPage setSelected={setSelected} />
          )}
          {page === "Incidents" && (
            <IncidentsPage incidents={incidents} setIncident={setIncident} />
          )}
          {page === "Knowledge base" && (
            <KnowledgePage
              knowledge={knowledge}
              askReference={(item) => {
                setContext(null);
                setAnswer(null);
                setQuestion(
                  `What checks and resolution steps are supported for ${item.title}?`,
                );
                setPage("AI assistant");
              }}
              setAddKnowledge={setAddKnowledge}
            />
          )}
          {page === "AI assistant" && (
            <AssistantPage
              context={context}
              setContext={setContext}
              answer={answer}
              question={question}
              setQuestion={setQuestion}
              ask={ask}
              asking={asking}
            />
          )}
          {page === "Documentation" && <DocumentationPage />}
          {page === "Storage findings" && <StoragePage />}
          {page === "Model evaluation" && <EvaluationPage />}
          {page === "Models & pipeline" && (
            <ModelsPage overview={overview} workers={workers} />
          )}
        </div>
      </main>
      {upload && (
        <Ingest
          close={() => setUpload(false)}
          done={(m) => {
            setNotice(m);
            refresh();
          }}
        />
      )}
      {selected && (
        <Modal title="Event details" close={() => setSelected(null)} wide>
          <div className="detail-top">
            <Badge priority={selected.prediction.priority} />
            <span className="subtle-tag">{selected.storage}</span>
          </div>
          <pre className="log-message">{selected.message}</pre>
          <dl className="details">
            {[
              ["Service", selected.service],
              ["Source", selected.source],
              ["Dataset", selected.dataset || "Unspecified"],
              ["Source severity", selected.source_level || "Unavailable"],
              [
                "Reference priority",
                selected.reference_priority || "Unlabeled",
              ],
              [
                "Reference provenance",
                selected.reference_provenance || "Not provided",
              ],
              ["Ingested", time(selected.received_at)],
              ["Host", selected.host],
              ["Observed", time(selected.timestamp)],
              ["Classification", selected.prediction.mode],
              [
                "Review",
                selected.prediction.needs_review ? "Recommended" : "Standard",
              ],
              ["Model", selected.prediction.model_version],
              [
                "Confidence",
                selected.prediction.confidence === null
                  ? "Not scored"
                  : `${(selected.prediction.confidence * 100).toFixed(1)}% · uncalibrated`,
              ],
            ].map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
          {Object.keys(selected.prediction.individual).length > 0 && (
            <div className="individual-results">
              {Object.entries(selected.prediction.individual).map(([n, v]) => (
                <div key={n}>
                  {n}
                  <Badge priority={v.priority} />
                </div>
              ))}
            </div>
          )}
          <label>Normalized pattern</label>
          <pre className="pattern">{selected.template}</pre>
          {selected.warnings.map((w) => (
            <p className="hint" key={w}>
              {w}
            </p>
          ))}
          <button className="primary" onClick={() => askAbout(selected)}>
            <Sparkles size={17} />
            Investigate with assistant
          </button>
        </Modal>
      )}
      {incident && (
        <IncidentModal
          incident={incident}
          close={() => setIncident(null)}
          done={() => {
            setNotice("Incident updated");
            refresh();
          }}
        />
      )}
      {addKnowledge && (
        <KnowledgeModal
          close={() => setAddKnowledge(false)}
          done={() => {
            setNotice("Reference added to knowledge");
            refresh();
          }}
        />
      )}
      {auth && (
        <Modal title="Connection settings" close={() => setAuth(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setApiKey(new FormData(e.currentTarget).get("key"));
              setAuth(false);
              refresh();
            }}
          >
            <p className="hint">
              This is the optional LogSense access key configured by your
              administrator using LOGSENSE_API_KEY. It is not an OpenAI key.
              Leave it blank for an unsecured local instance. It is kept only
              for this browser session.
            </p>
            <label>
              LogSense access key (optional)
              <input
                name="key"
                type="password"
                autoComplete="off"
                defaultValue={getApiKey()}
              />
            </label>
            <button className="primary">Save connection</button>
          </form>
        </Modal>
      )}
    </div>
  );
}
