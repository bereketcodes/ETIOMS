"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type View = "dashboard" | "pipeline" | "ingest" | "profile" | "admin";

type Match = {
  tender_id: string;
  tender_title: string;
  procuring_entity: string;
  sector: string;
  region: string;
  deadline: string | null;
  budget: number | null;
  requirements: string[];
  total_score: number;
  is_qualified: boolean;
  compliance_decision: string;
  ai_justification: string;
  breakdown: Record<string, number | string>;
  cached: boolean;
};

type ChecklistItem = {
  requirement_name: string;
  is_mandatory: boolean;
  status: string;
  evidence_or_gap: string;
};

type Compliance = {
  bid_decision: string;
  executive_justification: string;
  preliminary_checklist: ChecklistItem[];
  critical_disqualification_risks: string[];
  procurement_safeguards: string[];
};

type OrganizationProfile = {
  company_name: string;
  sectors: string[];
  operating_regions: string[];
  years_experience: number;
  certifications: string[];
  past_projects_summary: string;
};

type Tender = {
  id: string;
  title: string;
  procuring_entity: string;
  sector: string;
  region: string;
  deadline: string | null;
  budget: number | null;
  requirements: string[];
};

type Opportunity = {
  id: string;
  tender_id: string;
  organization_id: string;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
  tender_title: string;
  procuring_entity: string;
  sector: string;
  region: string;
  deadline: string | null;
  budget: number | null;
  match_score: number | null;
  compliance_decision: string | null;
};

type NotificationItem = {
  id: string;
  type: string;
  message: string;
  read_flag: boolean;
  created_at: string;
};

type UserMe = {
  id: string;
  email: string;
  user_name: string;
  organization_id: string;
  role: string;
  company_name?: string;
};

type RAGResult = {
  tender_id: string;
  question: string;
  answer: string;
  citations: string[];
  is_grounded: boolean;
};

type TenderComparison = {
  id: string;
  title: string;
  procuring_entity: string;
  sector: string;
  region: string;
  deadline: string | null;
  budget: number | null;
  status: string;
  requirements: string[];
  ai_summary: string | null;
};

const emptyProfile: OrganizationProfile = {
  company_name: "AfroTech Solutions PLC",
  sectors: [],
  operating_regions: [],
  years_experience: 0,
  certifications: [],
  past_projects_summary: "",
};

const regions = ["Addis Ababa", "Oromia", "Amhara", "Sidama", "Tigray", "Afar", "Somali", "Ethiopia"];
const certifications = ["Renewed Trade License", "Tax Clearance", "VAT Certificate", "TIN Certificate", "Bid Security / CPO"];

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const token = window.sessionStorage.getItem("access_token");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!response.ok) {
    if (response.status === 401) {
      window.sessionStorage.removeItem("access_token");
      window.dispatchEvent(new Event("etioms:unauthorized"));
    }
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch {
      // Keep HTTP status message
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function fetchMatchDetail(tenderId: string, forceRefresh = false) {
  return Promise.all([
    apiRequest<Match>(`/api/profile/match/${tenderId}${forceRefresh ? "?force_refresh=true" : ""}`),
    apiRequest<Compliance>(`/api/profile/compliance/${tenderId}`).catch(() => null),
  ]);
}

function formatDate(value: string | null) {
  if (!value) return "Deadline not specified";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat("en", { day: "numeric", month: "short", year: "numeric" }).format(date);
}

function formatBudget(value: number | null) {
  if (value === null || value === undefined) return "Budget not disclosed";
  return new Intl.NumberFormat("en-ET", { style: "currency", currency: "ETB", maximumFractionDigits: 0 }).format(value);
}

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

function BrandMark() {
  return <span className="brand-mark" aria-hidden="true"><span />E</span>;
}

function AIInsightBanner() {
  return (
    <div className="ai-disclaimer-banner" role="status">
      <span className="spark-icon" aria-hidden="true">✳</span>
      <span>
        <strong>AI-Generated Intelligence (FDRE FPPA Aligned)</strong> — Evaluated by Gemini 3.6 Flash. Verify against official procurement notices before formal envelope sealing.
      </span>
    </div>
  );
}

function AppShell({ view, children }: { view: View; children: React.ReactNode }) {
  const router = useRouter();
  const [currentUser, setCurrentUser] = useState<UserMe | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [showNotifs, setShowNotifs] = useState(false);

  const links: { href: string; label: string; view: View }[] = [
    { href: "/", label: "Ranked opportunities", view: "dashboard" },
    { href: "/opportunities", label: "Opportunity pipeline", view: "pipeline" },
    { href: "/ingest", label: "Upload tender", view: "ingest" },
    { href: "/profile", label: "Company profile", view: "profile" },
    { href: "/admin", label: "Admin console", view: "admin" },
  ];

  useEffect(() => {
    let mounted = true;
    apiRequest<UserMe>("/api/auth/me")
      .then((u) => { if (mounted) setCurrentUser(u); })
      .catch(() => {});
    apiRequest<NotificationItem[]>("/api/notifications")
      .then((n) => { if (mounted) setNotifications(n); })
      .catch(() => {});
    return () => { mounted = false; };
  }, []);

  async function markAllRead() {
    try {
      await apiRequest("/api/notifications/mark-all-read", { method: "POST" });
      setNotifications((prev) => prev.map((n) => ({ ...n, read_flag: true })));
    } catch {
      // Ignored
    }
  }

  const unreadCount = notifications.filter((n) => !n.read_flag).length;

  return (
    <div className="app-frame">
      <header className="topbar">
        <Link className="brand" href="/" aria-label="ETIOMS home">
          <BrandMark />
          <span>ETIOMS<small>PROCUREMENT INTELLIGENCE</small></span>
        </Link>
        <nav className="main-nav" aria-label="Main navigation">
          {links.map((link) => (
            <Link key={link.href} href={link.href} className={view === link.view ? "nav-link active" : "nav-link"}>
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="account-actions">
          {/* Notification Bell */}
          <div style={{ position: "relative" }}>
            <button
              className="notif-button"
              type="button"
              aria-label="View notifications"
              onClick={() => setShowNotifs(!showNotifs)}
            >
              🔔
              {unreadCount > 0 && <span className="notif-badge">{unreadCount}</span>}
            </button>
            {showNotifs && (
              <div className="notif-dropdown">
                <div className="notif-header">
                  <h4>Alerts & Deadlines</h4>
                  {unreadCount > 0 && (
                    <button
                      className="button button-outline"
                      style={{ fontSize: "10px", padding: "2px 6px" }}
                      onClick={markAllRead}
                    >
                      Mark all read
                    </button>
                  )}
                </div>
                {notifications.length === 0 ? (
                  <p style={{ fontSize: "11px", color: "var(--muted)", margin: 0 }}>No new alerts</p>
                ) : (
                  notifications.map((n) => (
                    <div key={n.id} className={`notif-item ${n.read_flag ? "" : "unread"}`}>
                      {n.message}
                      <small>{new Date(n.created_at).toLocaleDateString()}</small>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          <Link className="company-chip" href="/profile">
            <span className="company-avatar">{currentUser?.user_name?.[0] || "A"}</span>
            <span>
              <strong style={{ display: "block", fontSize: "12px", color: "var(--ink)", lineHeight: 1.2 }}>
                {currentUser?.user_name || "Account"}
              </strong>
              <small style={{ display: "block", fontSize: "10px", color: "var(--green-dark)", fontWeight: "700" }}>
                {currentUser?.role || "Business User"}{currentUser?.company_name ? ` · ${currentUser.company_name}` : ""}
              </small>
            </span>
            <span className="chip-arrow">↗</span>
          </Link>
          <button
            className="button button-outline sign-out-button"
            onClick={() => {
              window.sessionStorage.removeItem("access_token");
              window.dispatchEvent(new Event("etioms:auth-changed"));
              router.replace("/");
            }}
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="page-main">{children}</main>
      <footer className="app-footer">
        <span>ETIOMS <span className="footer-dot">/</span> Ethiopian Tender Intelligence</span>
        <span>Built for better bids</span>
      </footer>
    </div>
  );
}

function AuthPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [registerWithInvite, setRegisterWithInvite] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [invitationCode, setInvitationCode] = useState("");
  const [userName, setUserName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const register = mode === "register";
    const body = register
      ? JSON.stringify(registerWithInvite
        ? { invitation_code: invitationCode, user_name: userName, email, password }
        : { company_name: companyName, user_name: userName, email, password })
      : new URLSearchParams({ username: email, password });
    try {
      const response = await fetch(`${API_BASE}/api/auth/${register ? "register" : "token"}`, {
        method: "POST",
        headers: register ? { "Content-Type": "application/json" } : { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(result.detail ?? `Request failed (${response.status})`);
      }
      const result = await response.json() as { access_token: string };
      window.sessionStorage.setItem("access_token", result.access_token);
      window.dispatchEvent(new Event("etioms:auth-changed"));
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <section className="auth-card">
        <BrandMark />
        <p className="eyebrow">{mode === "register" ? "CREATE A COMPANY ACCOUNT" : "SECURE SIGN IN"}</p>
        <h1>{mode === "register" ? "Start with ETIOMS" : "Welcome back"}</h1>
        <p className="auth-description">{mode === "register" ? "Create your company workspace to assess Ethiopian tender opportunities." : "Sign in to view your company’s tender matches and profile."}</p>
        <form className="auth-form" onSubmit={submit}>
          {mode === "register" && <>
            {registerWithInvite
              ? <label className="form-control"><span>Invitation code</span><input required minLength={20} maxLength={128} value={invitationCode} onChange={(event) => setInvitationCode(event.target.value)} autoComplete="off" /></label>
              : <label className="form-control"><span>Company name</span><input required minLength={2} maxLength={255} value={companyName} onChange={(event) => setCompanyName(event.target.value)} autoComplete="organization" /></label>}
            <label className="form-control"><span>Your name</span><input required maxLength={120} value={userName} onChange={(event) => setUserName(event.target.value)} autoComplete="name" /></label>
          </>}
          <label className="form-control"><span>Email</span><input required type="email" maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" /></label>
          <label className="form-control"><span>Password</span><input required type="password" minLength={12} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={mode === "register" ? "new-password" : "current-password"} /><small className="auth-hint">{mode === "register" ? "Use at least 12 characters." : " "}</small></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button button-primary submit-button" type="submit" disabled={loading}>{loading ? "Please wait…" : mode === "register" ? "Create company account" : "Sign in"}</button>
        </form>
        {mode === "register" && <p className="auth-switch"><button type="button" onClick={() => { setRegisterWithInvite(!registerWithInvite); setError(""); }}>{registerWithInvite ? "Create a new company instead" : "Have an invitation code? Join a company"}</button></p>}
        <p className="auth-switch">{mode === "register" ? "Already registered?" : "New to ETIOMS?"}{" "}<button type="button" onClick={() => { setMode(mode === "register" ? "login" : "register"); setRegisterWithInvite(false); setError(""); }}>{mode === "register" ? "Sign in" : "Create a company account"}</button></p>
      </section>
    </div>
  );
}

function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-description">{description}</p></div>{action}</div>;
}

function Dashboard() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState("All sectors");
  const [minScore, setMinScore] = useState(0);
  const [activeMatch, setActiveMatch] = useState<Match | null>(null);

  // Day 2 Features: Comparison and Pipeline
  const [selectedForCompare, setSelectedForCompare] = useState<string[]>([]);
  const [comparisonData, setComparisonData] = useState<TenderComparison[] | null>(null);
  const [comparing, setComparing] = useState(false);
  const [savedTenders, setSavedTenders] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let mounted = true;
    apiRequest<Match[]>("/api/profile/matches")
      .then((data) => { if (mounted) setMatches(data); })
      .catch((reason: unknown) => { if (mounted) setError(getErrorMessage(reason)); })
      .finally(() => { if (mounted) setLoading(false); });

    // Also check saved opportunities to display saved status
    apiRequest<Opportunity[]>("/api/opportunities")
      .then((opps) => {
        if (mounted) {
          const map: Record<string, boolean> = {};
          opps.forEach((o) => { map[o.tender_id] = true; });
          setSavedTenders(map);
        }
      })
      .catch(() => {});

    return () => { mounted = false; };
  }, []);

  async function handleSaveOpportunity(tenderId: string, e?: React.MouseEvent) {
    if (e) e.stopPropagation();
    try {
      await apiRequest(`/api/opportunities/save/${tenderId}`, { method: "POST" });
      setSavedTenders((prev) => ({ ...prev, [tenderId]: true }));
    } catch {
      // Ignored
    }
  }

  function toggleCompare(tenderId: string) {
    setSelectedForCompare((prev) =>
      prev.includes(tenderId) ? prev.filter((id) => id !== tenderId) : prev.length < 5 ? [...prev, tenderId] : prev
    );
  }

  async function runComparison() {
    if (selectedForCompare.length < 2) return;
    setComparing(true);
    try {
      const result = await apiRequest<TenderComparison[]>("/api/tenders/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tender_ids: selectedForCompare }),
      });
      setComparisonData(result);
    } catch (err) {
      alert(getErrorMessage(err));
    } finally {
      setComparing(false);
    }
  }

  const sectorOptions = useMemo(() => ["All sectors", ...Array.from(new Set(matches.map((match) => match.sector).filter(Boolean))).sort()], [matches]);
  const filtered = useMemo(() => matches.filter((match) =>
    (match.procuring_entity.toLowerCase().includes(search.trim().toLowerCase()) || match.tender_title.toLowerCase().includes(search.trim().toLowerCase())) &&
    (sector === "All sectors" || match.sector === sector) && match.total_score >= minScore
  ), [matches, search, sector, minScore]);

  const qualified = matches.filter((match) => match.is_qualified).length;
  const now = new Date();
  const nextWeek = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
  const closingThisWeek = matches.filter((m) => {
    if (!m.deadline) return false;
    const d = new Date(m.deadline);
    return d >= now && d <= nextWeek;
  }).length;
  const averageScore = matches.length ? Math.round(matches.reduce((sum, match) => sum + match.total_score, 0) / matches.length) : 0;

  return (
    <AppShell view="dashboard">
      <AIInsightBanner />
      <PageHeading
        eyebrow="OPPORTUNITY RADAR · ETHIOPIAN TENDERS"
        title="Ranked opportunities"
        description="A real-time, compliance-scored intelligence feed comparing open bids against your company capabilities."
        action={<span className="live-indicator"><i /> Live intelligence</span>}
      />
      <section className="metrics-grid" aria-label="Opportunity metrics">
        <Metric label="Total assessed" value={matches.length} detail="Open tenders processed" tone="ink" symbol="↗" />
        <Metric label="Qualified bids" value={qualified} detail="Match score ≥ 60%" tone="green" symbol="✓" />
        <Metric label="Closing within 7 days" value={closingThisWeek} detail="Urgent submission window" tone="red" symbol="◷" />
        <Metric label="Average match score" value={`${averageScore}%`} detail="Across tender portfolio" tone="gold" symbol="◎" />
      </section>

      <section className="opportunities-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">YOUR PIPELINE</p>
            <h2>Recommended tenders <span className="count-badge">{filtered.length}</span></h2>
          </div>
          <span className="sort-note">Sorted by strongest match <span aria-hidden="true">↓</span></span>
        </div>
        <div className="filter-bar">
          <label className="search-field">
            <span aria-hidden="true">⌕</span>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search title or procuring entity" aria-label="Search tenders" />
          </label>
          <label className="select-field">
            <span>Sector</span>
            <select value={sector} onChange={(event) => setSector(event.target.value)}>
              {sectorOptions.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
          <label className="score-filter">
            <span>Minimum score <b>{minScore}%</b></span>
            <input type="range" min="0" max="100" step="5" value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} aria-label="Minimum match score" />
          </label>
        </div>

        {loading && <div className="tender-list" aria-label="Loading opportunities">{[0, 1, 2].map((item) => <div className="tender-skeleton" key={item}><div className="skeleton-line short" /><div className="skeleton-line wide" /><div className="skeleton-line medium" /></div>)}</div>}
        {!loading && error && <div className="state-panel error-panel"><span className="state-icon">!</span><div><h3>Couldn’t load opportunities</h3><p>{error}</p>{error.toLowerCase().includes("profile") && <Link className="button button-primary" href="/profile">Set up company profile <span>↗</span></Link>}</div><button className="button button-outline" onClick={() => window.location.reload()}>Try again</button></div>}
        {!loading && !error && filtered.length === 0 && <div className="state-panel empty-panel"><span className="state-icon">⌕</span><div><h3>{matches.length ? "No tenders match these filters" : "Your opportunity list is clear"}</h3><p>{matches.length ? "Adjust your search or lower the minimum score." : "Once a company profile is saved and tenders are available, ranked matches will appear here."}</p></div>{!matches.length && <Link className="button button-primary" href="/ingest">Add a tender <span>↗</span></Link>}</div>}
        {!loading && !error && filtered.length > 0 && (
          <div className="tender-list">
            {filtered.map((match) => (
              <TenderCard
                key={match.tender_id}
                match={match}
                isSaved={Boolean(savedTenders[match.tender_id])}
                isSelectedForCompare={selectedForCompare.includes(match.tender_id)}
                onToggleCompare={() => toggleCompare(match.tender_id)}
                onSave={(e) => handleSaveOpportunity(match.tender_id, e)}
                onOpen={() => setActiveMatch(match)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Floating Compare Action Bar */}
      {selectedForCompare.length >= 2 && (
        <aside className="compare-bar">
          <span>Selected <strong>{selectedForCompare.length}</strong> tenders to compare</span>
          <button className="button button-primary" onClick={runComparison} disabled={comparing}>
            {comparing ? "Comparing…" : "Compare side-by-side ↗"}
          </button>
          <button className="button button-outline" style={{ color: "#fff", borderColor: "#64736a" }} onClick={() => setSelectedForCompare([])}>
            Clear
          </button>
        </aside>
      )}

      {/* Comparison Modal */}
      {comparisonData && (
        <CompareModal
          data={comparisonData}
          onClose={() => setComparisonData(null)}
        />
      )}

      {activeMatch && (
        <MatchDrawer
          match={activeMatch}
          isSaved={Boolean(savedTenders[activeMatch.tender_id])}
          onSave={() => handleSaveOpportunity(activeMatch.tender_id)}
          onClose={() => setActiveMatch(null)}
        />
      )}
    </AppShell>
  );
}

function Metric({ label, value, detail, tone, symbol }: { label: string; value: string | number; detail: string; tone: string; symbol: string }) {
  return <article className={`metric-card metric-${tone}`}><div className="metric-top"><span>{label}</span><span className="metric-symbol" aria-hidden="true">{symbol}</span></div><strong>{value}</strong><small>{detail}</small></article>;
}

function TenderCard({
  match,
  isSaved,
  isSelectedForCompare,
  onToggleCompare,
  onSave,
  onOpen,
}: {
  match: Match;
  isSaved: boolean;
  isSelectedForCompare: boolean;
  onToggleCompare: () => void;
  onSave: (e: React.MouseEvent) => void;
  onOpen: () => void;
}) {
  const score = Math.max(0, Math.min(100, match.total_score));
  return (
    <article className="tender-card">
      <div className="tender-main">
        <div className="tender-tags">
          <label className="compare-checkbox" title="Select for side-by-side comparison">
            <input type="checkbox" checked={isSelectedForCompare} onChange={onToggleCompare} />
            <span>Compare</span>
          </label>
          <span className={match.is_qualified ? "decision-badge bid" : "decision-badge no-bid"}>
            <i />{match.compliance_decision || (match.is_qualified ? "BID" : "NO-BID")}
          </span>
          {match.cached && <span className="cached-badge"><span aria-hidden="true">ϟ</span> Cached</span>}
          <span className="sector-tag">{match.sector}</span>
        </div>
        <h3>{match.tender_title}</h3>
        <div className="tender-meta">
          <span><span className="meta-icon">▤</span>{match.procuring_entity}</span>
          <span><span className="meta-icon">◷</span>Due {formatDate(match.deadline)}</span>
          <span><span className="meta-icon">⌖</span>{match.region}</span>
        </div>
      </div>
      <div className="tender-score">
        <div className="score-label">
          <span>Match score</span>
          <strong>{Math.round(score)}<small>%</small></strong>
        </div>
        <div className="score-track"><span style={{ width: `${score}%` }} /></div>
        <small className="score-caption">{score >= 80 ? "Excellent fit" : score >= 60 ? "Good potential" : "Needs review"}</small>
      </div>
      <div style={{ display: "grid", gap: "8px" }}>
        <button className="button button-outline detail-button" onClick={onOpen}>
          Details <span aria-hidden="true">↗</span>
        </button>
        <button
          className="button button-outline"
          style={{ fontSize: "11px", padding: "4px 8px" }}
          onClick={onSave}
        >
          {isSaved ? "✓ In Pipeline" : "＋ Save"}
        </button>
      </div>
    </article>
  );
}

function MatchDrawer({
  match,
  isSaved,
  onSave,
  onClose,
}: {
  match: Match;
  isSaved: boolean;
  onSave: () => void;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<Match>(match);
  const [compliance, setCompliance] = useState<Compliance | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  // RAG Q&A State (FR-14)
  const [question, setQuestion] = useState("");
  const [ragLoading, setRagLoading] = useState(false);
  const [ragResult, setRagResult] = useState<RAGResult | null>(null);

  const samplePrompts = [
    "What documents and licenses are required for this tender?",
    "What is the bid bond / CPO amount?",
    "What is the closing deadline and submission method?",
    "What are the mandatory eligibility criteria?",
  ];

  async function askQuestion(queryText: string) {
    if (!queryText.trim()) return;
    setRagLoading(true);
    setRagResult(null);
    try {
      const res = await apiRequest<RAGResult>(`/api/tenders/${match.tender_id}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: queryText }),
      });
      setRagResult(res);
    } catch (err) {
      alert(getErrorMessage(err));
    } finally {
      setRagLoading(false);
    }
  }

  async function load(forceRefresh = false) {
    setError("");
    if (forceRefresh) setRefreshing(true); else setLoading(true);
    try {
      const [matchResult, complianceResult] = await fetchMatchDetail(match.tender_id, forceRefresh);
      setDetail(matchResult);
      setCompliance(complianceResult);
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    let mounted = true;
    fetchMatchDetail(match.tender_id).then(([matchResult, complianceResult]) => {
      if (mounted) {
        setDetail(matchResult);
        setCompliance(complianceResult);
      }
    }).catch((reason: unknown) => {
      if (mounted) setError(getErrorMessage(reason));
    }).finally(() => {
      if (mounted) setLoading(false);
    });
    return () => { mounted = false; };
  }, [match.tender_id]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) { if (event.key === "Escape") onClose(); }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const breakdown = detail.breakdown ?? {};
  const scoreRows = [
    ["Sector alignment", Number(breakdown.sector_match ?? 0), 25],
    ["Regional coverage", Number(breakdown.region_match ?? 0), 20],
    ["Relevant experience", Number(breakdown.experience_score ?? 0), 25],
    ["AI semantic fit", Number(breakdown.ai_semantic_score ?? 0), 30],
  ] as const;

  return (
    <div className="drawer-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="detail-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <div className="drawer-header">
          <div>
            <p className="eyebrow">TENDER INTELLIGENCE</p>
            <span className={detail.is_qualified ? "decision-badge bid" : "decision-badge no-bid"}>
              <i />{detail.compliance_decision || (detail.is_qualified ? "BID" : "NO-BID")}
            </span>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close details">×</button>
        </div>
        <h2 id="drawer-title">{detail.tender_title}</h2>
        <p className="drawer-entity">{detail.procuring_entity} <span>·</span> {detail.sector}</p>

        <div className="drawer-scroll">
          <AIInsightBanner />
          {error && <div className="inline-error">{error}</div>}
          {loading ? (
            <div className="drawer-loading">
              <div className="skeleton-line short" /><div className="skeleton-line wide" /><div className="skeleton-line wide" />
            </div>
          ) : (
            <>
              <section className="drawer-score-panel">
                <div>
                  <span className="eyebrow">TOTAL MATCH SCORE</span>
                  <strong>{Math.round(detail.total_score)}<small>%</small></strong>
                </div>
                <div className="drawer-score-track">
                  <span style={{ width: `${Math.max(0, Math.min(100, detail.total_score))}%` }} />
                </div>
                <div className="drawer-tender-facts">
                  <span><small>Deadline</small>{formatDate(detail.deadline)}</span>
                  <span><small>Estimated budget</small>{formatBudget(detail.budget)}</span>
                </div>
              </section>

              <section className="drawer-section">
                <div className="drawer-section-title">
                  <h3>Score breakdown</h3>
                  <span>100 pts possible</span>
                </div>
                <div className="breakdown-list">
                  {scoreRows.map(([label, value, max]) => (
                    <div className="breakdown-row" key={label}>
                      <div>
                        <span>{label}</span>
                        <b>{value}<small> / {max}</small></b>
                      </div>
                      <div className="breakdown-track">
                        <span style={{ width: `${Math.max(0, Math.min(100, (value / max) * 100))}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {/* RAG-Based Tender Q&A (FR-14) */}
              <section className="rag-chat-container">
                <div className="rag-chat-title">
                  <span>💬</span> Ask Tender Documents (RAG Grounded Q&A)
                </div>
                <p style={{ margin: "0 0 10px", fontSize: "11px", color: "var(--muted)" }}>
                  Answers are derived strictly from the indexed tender text and cited to source sections.
                </p>
                <div className="rag-prompt-pills">
                  {samplePrompts.map((p) => (
                    <button
                      key={p}
                      type="button"
                      className="rag-pill"
                      onClick={() => {
                        setQuestion(p);
                        askQuestion(p);
                      }}
                    >
                      {p}
                    </button>
                  ))}
                </div>
                <div className="rag-input-row">
                  <input
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        askQuestion(question);
                      }
                    }}
                    placeholder="Ask about required licenses, bid security, delivery time…"
                  />
                  <button
                    className="button button-primary"
                    type="button"
                    disabled={ragLoading || !question.trim()}
                    onClick={() => askQuestion(question)}
                  >
                    {ragLoading ? "Checking…" : "Ask AI"}
                  </button>
                </div>
                {ragResult && (
                  <div className="rag-answer-box">
                    <strong style={{ display: "block", marginBottom: "6px", color: ragResult.is_grounded ? "var(--green-dark)" : "var(--amber)" }}>
                      {ragResult.is_grounded ? "✓ Verified in Tender Text" : "⚠ Not Explicitly Stated"}
                    </strong>
                    <div style={{ whiteSpace: "pre-line" }}>{ragResult.answer}</div>
                    {ragResult.citations.length > 0 && (
                      <div style={{ marginTop: "10px" }}>
                        <small style={{ display: "block", color: "var(--muted)", marginBottom: "4px" }}>Citations & References:</small>
                        {ragResult.citations.map((c, idx) => (
                          <span key={idx} className="citation-badge">📌 {c}</span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </section>

              <section className="justification-box">
                <div className="justification-heading">
                  <span className="spark-icon">✳</span>
                  <div>
                    <p className="eyebrow">GEMINI ANALYSIS</p>
                    <h3>Why this match</h3>
                  </div>
                </div>
                <p>
                  {typeof breakdown.ai_justification === "string"
                    ? breakdown.ai_justification
                    : detail.ai_justification || "No AI justification is available for this match."}
                </p>
              </section>

              <section className="drawer-section compliance-section">
                <div className="drawer-section-title">
                  <h3>FPPA compliance audit</h3>
                  {compliance && (
                    <span className={`audit-decision ${compliance.bid_decision.toLowerCase()}`}>
                      {compliance.bid_decision}
                    </span>
                  )}
                </div>
                {compliance ? (
                  <>
                    <p className="compliance-intro">{compliance.executive_justification}</p>
                    <div className="checklist">
                      {compliance.preliminary_checklist?.map((item, index) => (
                        <div className="check-row" key={`${item.requirement_name}-${index}`}>
                          <span className={`check-status ${item.status.toLowerCase()}`}>
                            {item.status === "PASS" ? "✓" : item.status === "FAIL" ? "×" : "!"}
                          </span>
                          <div>
                            <strong>{item.requirement_name}</strong>
                            <p>{item.evidence_or_gap}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                    {compliance.critical_disqualification_risks?.length > 0 && (
                      <div className="risk-note">
                        <strong>Critical risks under Ethiopian Procurement Rules</strong>
                        {compliance.critical_disqualification_risks.map((risk) => <p key={risk}>{risk}</p>)}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="compliance-unavailable">Compliance audit could not be loaded.</div>
                )}
              </section>
            </>
          )}
        </div>
        <div className="drawer-footer">
          <button
            className="button button-outline"
            onClick={onSave}
          >
            {isSaved ? "✓ In Pipeline" : "＋ Save to Pipeline"}
          </button>
          <button
            className="button button-outline"
            onClick={() => void load(true)}
            disabled={refreshing || loading}
          >
            <span aria-hidden="true">↻</span>{refreshing ? "Refreshing…" : "Force AI refresh"}
          </button>
          <button className="button button-primary" onClick={onClose}>Done</button>
        </div>
      </aside>
    </div>
  );
}

function CompareModal({ data, onClose }: { data: TenderComparison[]; onClose: () => void }) {
  return (
    <div className="compare-modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="compare-modal" role="dialog" aria-modal="true">
        <div className="compare-modal-header">
          <div>
            <p className="eyebrow">OPPORTUNITY BENCHMARK</p>
            <h2 style={{ margin: 0 }}>Side-by-Side Tender Comparison</h2>
          </div>
          <button className="icon-button" onClick={onClose}>×</button>
        </div>
        <table className="compare-table">
          <thead>
            <tr>
              <th>Evaluation Parameter</th>
              {data.map((t) => <td key={t.id}><strong>{t.title}</strong></td>)}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th>Procuring Entity</th>
              {data.map((t) => <td key={t.id}>{t.procuring_entity}</td>)}
            </tr>
            <tr>
              <th>Sector & Region</th>
              {data.map((t) => <td key={t.id}>{t.sector} · {t.region}</td>)}
            </tr>
            <tr>
              <th>Closing Deadline</th>
              {data.map((t) => <td key={t.id}>{formatDate(t.deadline)}</td>)}
            </tr>
            <tr>
              <th>Estimated Budget</th>
              {data.map((t) => <td key={t.id}>{formatBudget(t.budget)}</td>)}
            </tr>
            <tr>
              <th>Status</th>
              {data.map((t) => <td key={t.id}>{t.status}</td>)}
            </tr>
            <tr>
              <th>Mandatory Requirements</th>
              {data.map((t) => (
                <td key={t.id}>
                  {t.requirements.length > 0 ? (
                    <ul style={{ margin: 0, paddingLeft: "16px", fontSize: "11px" }}>
                      {t.requirements.map((r, i) => <li key={i}>{r}</li>)}
                    </ul>
                  ) : (
                    <span style={{ color: "var(--muted)" }}>None specified</span>
                  )}
                </td>
              ))}
            </tr>
            <tr>
              <th>Scope & Summary</th>
              {data.map((t) => <td key={t.id} style={{ fontSize: "11px", color: "#44554b" }}>{t.ai_summary || "No summary"}</td>)}
            </tr>
          </tbody>
        </table>
        <div style={{ marginTop: "20px", textAlign: "right" }}>
          <button className="button button-primary" onClick={onClose}>Close Comparison</button>
        </div>
      </div>
    </div>
  );
}

function PipelinePage() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const stages = ["Discovered", "Interested", "Analyzing", "Preparing", "Submitted", "Awarded"];

  async function loadOpportunities() {
    setLoading(true);
    try {
      const data = await apiRequest<Opportunity[]>("/api/opportunities");
      setOpportunities(data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadOpportunities();
  }, []);

  async function updateStatus(id: string, newStatus: string, currentNotes?: string | null) {
    try {
      await apiRequest(`/api/opportunities/${id}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus, notes: currentNotes }),
      });
      setOpportunities((prev) =>
        prev.map((o) => (o.id === id ? { ...o, status: newStatus } : o))
      );
    } catch (err) {
      alert(getErrorMessage(err));
    }
  }

  async function updateNotes(id: string, currentStatus: string, notes: string) {
    try {
      await apiRequest(`/api/opportunities/${id}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: currentStatus, notes }),
      });
      setOpportunities((prev) =>
        prev.map((o) => (o.id === id ? { ...o, notes } : o))
      );
    } catch (err) {
      alert(getErrorMessage(err));
    }
  }

  return (
    <AppShell view="pipeline">
      <AIInsightBanner />
      <PageHeading
        eyebrow="TENDER OPPORTUNITY PIPELINE"
        title="Opportunity Tracking"
        description="Track your active bids from discovery through technical preparation to submission and award."
        action={
          <button className="button button-outline" onClick={loadOpportunities}>
            ↻ Refresh Pipeline
          </button>
        }
      />

      {loading && (
        <div style={{ textAlign: "center", padding: "40px", color: "var(--muted)" }}>
          Loading your active bid pipeline…
        </div>
      )}

      {error && <div className="state-panel error-panel">{error}</div>}

      {!loading && !error && opportunities.length === 0 && (
        <div className="state-panel empty-panel">
          <span className="state-icon">★</span>
          <div>
            <h3>No opportunities tracked yet</h3>
            <p>Save interesting tenders from the Ranked Opportunities radar to track them through your submission workflow.</p>
          </div>
          <Link className="button button-primary" href="/">Go to Opportunity Radar ↗</Link>
        </div>
      )}

      {!loading && !error && opportunities.length > 0 && (
        <div className="pipeline-board">
          {stages.map((stage) => {
            const inStage = opportunities.filter((o) =>
              stage === "Submitted" ? o.status === "Submitted" || o.status === "Awarded" || o.status === "Not Awarded" : o.status === stage
            );
            return (
              <div key={stage} className="pipeline-column">
                <div className="pipeline-col-header">
                  <span>{stage}</span>
                  <span className="count-badge">{inStage.length}</span>
                </div>
                {inStage.length === 0 ? (
                  <p style={{ fontSize: "11px", color: "#8a968f", textAlign: "center", marginTop: "30px" }}>
                    No tenders in {stage}
                  </p>
                ) : (
                  inStage.map((opp) => (
                    <article key={opp.id} className="pipeline-card">
                      <h4>{opp.tender_title}</h4>
                      <p>{opp.procuring_entity}</p>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "#54645a", marginBottom: "6px" }}>
                        <span>Due {formatDate(opp.deadline)}</span>
                        {opp.match_score !== null && <strong>{Math.round(opp.match_score)}% match</strong>}
                      </div>
                      {opp.notes && <div className="notes-preview">📝 {opp.notes}</div>}
                      <div className="pipeline-actions">
                        <select
                          className="pipeline-select"
                          value={opp.status}
                          onChange={(e) => updateStatus(opp.id, e.target.value, opp.notes)}
                        >
                          <option value="Discovered">Discovered</option>
                          <option value="Interested">Interested</option>
                          <option value="Analyzing">Analyzing</option>
                          <option value="Preparing">Preparing</option>
                          <option value="Submitted">Submitted</option>
                          <option value="Awarded">Awarded</option>
                          <option value="Not Awarded">Not Awarded</option>
                        </select>
                        <button
                          type="button"
                          className="button button-outline"
                          style={{ fontSize: "9px", padding: "2px 6px" }}
                          onClick={() => {
                            const newNote = prompt("Add / update stage notes:", opp.notes || "");
                            if (newNote !== null) updateNotes(opp.id, opp.status, newNote);
                          }}
                        >
                          {opp.notes ? "Edit Note" : "＋ Note"}
                        </button>
                      </div>
                    </article>
                  ))
                )}
              </div>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}

function IngestPage() {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tender, setTender] = useState<Tender | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setTender(null);
    if (!file && !text.trim()) { setError("Choose a .pdf or .txt file, or paste the tender notice text."); return; }
    const formData = new FormData();
    if (file) formData.append("file", file);
    if (text.trim()) formData.append("text", text.trim());
    setLoading(true);
    try {
      const result = await apiRequest<Tender>("/api/tenders/upload", { method: "POST", body: formData });
      setTender(result);
      setFile(null);
      setText("");
      const input = document.getElementById("tender-file") as HTMLInputElement | null;
      if (input) input.value = "";
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell view="ingest">
      <AIInsightBanner />
      <PageHeading eyebrow="TENDER INTAKE" title="Bring an opportunity in" description="Upload a notice or paste its text. ETIOMS will structure it and add it to your ranked pipeline." />
      <div className="ingest-layout">
        <form className="form-panel ingest-form" onSubmit={submit}>
          <div className="panel-heading"><div><span className="step-number">01</span><div><h2>Source document</h2><p>Upload a file or paste the procurement notice.</p></div></div></div>
          <label className="upload-dropzone" htmlFor="tender-file">
            <span className="upload-icon">↑</span>
            <strong>{file ? file.name : "Choose a tender file"}</strong>
            <small>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · Ready to parse` : "PDF or plain text · 20 MB max"}</small>
            <span className="button button-outline">Browse files</span>
            <input id="tender-file" type="file" accept=".pdf,.txt,application/pdf,text/plain" onChange={(event) => { const selected = event.target.files?.[0] ?? null; setFile(selected); setError(""); }} />
          </label>
          <div className="or-divider"><span>OR PASTE NOTICE TEXT</span></div>
          <label className="field-label" htmlFor="notice-text">Procurement notice</label>
          <textarea id="notice-text" className="text-area notice-area" value={text} onChange={(event) => { setText(event.target.value); setError(""); }} placeholder="Paste the complete procurement notice here…" rows={10} />
          {error && <p className="form-error">{error}</p>}
          <button className="button button-primary submit-button" type="submit" disabled={loading}>
            {loading ? <><span className="button-spinner" />Parsing with Gemini…</> : <>Extract tender details <span>↗</span></>}
          </button>
        </form>
        <aside className="ingest-aside">
          <div className="aside-orbit"><span className="orbit-core">E</span><span className="orbit-tag">AI</span></div>
          <p className="eyebrow">FROM NOTICE TO OPPORTUNITY</p>
          <h2>One document.<br />A clearer next move.</h2>
          <p>ETIOMS extracts key facts and requirements, then scores the opportunity against your company profile.</p>
          <div className="process-list">
            <div><span>01</span><p>Upload or paste a notice</p></div>
            <div><span>02</span><p>AI extracts the essentials</p></div>
            <div><span>03</span><p>Review your match score</p></div>
          </div>
        </aside>
      </div>
      {loading && <div className="parse-result loading-result" aria-live="polite"><div className="skeleton-line short" /><div className="skeleton-line wide" /><div className="skeleton-line medium" /><div className="skeleton-line wide" /></div>}
      {tender && (
        <section className="parse-result">
          <div className="result-header">
            <div><p className="eyebrow">NOTICE PARSED SUCCESSFULLY</p><h2>{tender.title}</h2></div>
            <span className="result-check">✓</span>
          </div>
          <div className="result-grid">
            <ResultField label="Procuring entity" value={tender.procuring_entity} />
            <ResultField label="Budget" value={formatBudget(tender.budget)} />
            <ResultField label="Deadline" value={formatDate(tender.deadline)} />
            <ResultField label="Sector · Region" value={`${tender.sector} · ${tender.region}`} />
          </div>
          {tender.requirements.length > 0 && (
            <div className="requirements-list">
              <strong>Extracted requirements</strong>
              <div>{tender.requirements.map((requirement) => <span key={requirement}>{requirement}</span>)}</div>
            </div>
          )}
          <Link className="button button-primary" href="/">See ranked opportunities <span>↗</span></Link>
        </section>
      )}
    </AppShell>
  );
}

function ResultField({ label, value }: { label: string; value: string }) {
  return <div className="result-field"><small>{label}</small><strong>{value || "Not specified"}</strong></div>;
}

function ProfilePage() {
  const [profile, setProfile] = useState<OrganizationProfile>(emptyProfile);
  const [sectorInput, setSectorInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteError, setInviteError] = useState("");

  useEffect(() => {
    let mounted = true;
    apiRequest<OrganizationProfile>("/api/profile/")
      .then((data) => { if (mounted) setProfile({ ...emptyProfile, ...data }); })
      .catch((reason: unknown) => {
        const message = getErrorMessage(reason);
        if (mounted && !message.toLowerCase().includes("no organization profile")) setError(message);
      })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, []);

  function update<K extends keyof OrganizationProfile>(key: K, value: OrganizationProfile[K]) {
    setProfile((current) => ({ ...current, [key]: value }));
    setSaved(false);
  }

  function toggleValue(key: "operating_regions" | "certifications", value: string) {
    const selected = profile[key];
    update(key, (selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value]) as OrganizationProfile[typeof key]);
  }

  function addSector() {
    const additions = sectorInput.split(",").map((item) => item.trim()).filter((item) => item && !profile.sectors.includes(item));
    if (additions.length) update("sectors", [...profile.sectors, ...additions]);
    setSectorInput("");
  }

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSaved(false);
    setSaving(true);
    try {
      const result = await apiRequest<OrganizationProfile>("/api/profile/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(profile) });
      setProfile({ ...emptyProfile, ...result });
      setSaved(true);
    } catch (reason) {
      setError(getErrorMessage(reason));
    } finally {
      setSaving(false);
    }
  }

  async function createInvite() {
    setInviteLoading(true);
    setInviteError("");
    setInviteCode("");
    try {
      const result = await apiRequest<{ invitation_code: string }>("/api/auth/invitations", { method: "POST" });
      setInviteCode(result.invitation_code);
    } catch (reason) {
      setInviteError(getErrorMessage(reason));
    } finally {
      setInviteLoading(false);
    }
  }

  return (
    <AppShell view="profile">
      <PageHeading eyebrow="COMPANY READINESS" title="Your company profile" description="Keep your capabilities current. ETIOMS uses this information to qualify and rank tenders." action={<span className="profile-status"><i /> Profile settings</span>} />
      {loading ? <div className="profile-loading"><div className="skeleton-line short" /><div className="skeleton-line wide" /><div className="skeleton-line medium" /><div className="skeleton-line wide" /></div> : (
        <form className="profile-form" onSubmit={saveProfile}>
          <section className="form-panel">
            <div className="panel-heading"><div><span className="step-number">01</span><div><h2>Company details</h2><p>Basic information about your organization.</p></div></div><span className="panel-index">IDENTITY</span></div>
            <div className="form-grid">
              <label className="form-control full-width"><span>Company name</span><input required value={profile.company_name} onChange={(event) => update("company_name", event.target.value)} placeholder="Your registered business name" /></label>
              <div className="form-control"><span>Years of experience</span><div className="number-input"><input min="0" type="number" value={profile.years_experience} onChange={(event) => update("years_experience", Math.max(0, Number(event.target.value)))} /><small>years</small></div></div>
            </div>
          </section>
          <section className="form-panel">
            <div className="panel-heading"><div><span className="step-number">02</span><div><h2>Areas of work</h2><p>Choose sectors and regions where you operate.</p></div></div><span className="panel-index">COVERAGE</span></div>
            <div className="tag-entry">
              <label className="field-label" htmlFor="sector-entry">Sectors</label>
              <div className="tag-input">
                <div className="selected-tags">{profile.sectors.map((item) => <button type="button" className="selected-tag" key={item} onClick={() => update("sectors", profile.sectors.filter((sectorName) => sectorName !== item))}>{item}<span aria-label={`Remove ${item}`}>×</span></button>)}<input id="sector-entry" value={sectorInput} onChange={(event) => setSectorInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); addSector(); } }} placeholder="Add a sector, use commas for several" /></div>
                <button type="button" className="button button-outline add-tag-button" onClick={addSector}>Add</button>
              </div>
            </div>
            <div className="field-label region-label">Operating regions</div>
            <div className="pill-options">{regions.map((region) => <button className={profile.operating_regions.includes(region) ? "option-pill selected" : "option-pill"} type="button" key={region} onClick={() => toggleValue("operating_regions", region)}><span>{profile.operating_regions.includes(region) ? "✓" : "+"}</span>{region}</button>)}</div>
          </section>
          <section className="form-panel">
            <div className="panel-heading"><div><span className="step-number">03</span><div><h2>Certifications & track record</h2><p>Credentials and experience that support your bids.</p></div></div><span className="panel-index">QUALIFICATIONS</span></div>
            <div className="certification-grid">{certifications.map((certification) => <label className="check-option" key={certification}><input type="checkbox" checked={profile.certifications.includes(certification)} onChange={() => toggleValue("certifications", certification)} /><span className="custom-checkbox">✓</span>{certification}</label>)}</div>
            <label className="form-control project-field"><span>Past projects summary</span><textarea className="text-area" rows={5} value={profile.past_projects_summary ?? ""} onChange={(event) => update("past_projects_summary", event.target.value)} placeholder="Describe relevant projects, clients, outcomes, and technical capabilities…" /></label>
          </section>
          {error && <p className="form-error">{error}</p>}
          <div className="profile-actions">
            <span>{saved ? <span className="saved-message">✓ Profile saved successfully</span> : "Changes are saved to your ETIOMS profile."}</span>
            <button className="button button-primary" type="submit" disabled={saving}>
              {saving ? <><span className="button-spinner" />Saving profile…</> : <>Save company profile <span>↗</span></>}
            </button>
          </div>
        </form>
      )}
      <section className="form-panel invite-panel">
        <div className="panel-heading"><div><span className="step-number">＋</span><div><h2>Invite a company member</h2><p>Anyone in your company can create a single-use invitation, valid for 24 hours.</p></div></div></div>
        <button className="button button-outline" type="button" onClick={() => void createInvite()} disabled={inviteLoading}>
          {inviteLoading ? "Creating invitation…" : "Create invitation code"}
        </button>
        {inviteError && <p className="form-error" role="alert">{inviteError}</p>}
        {inviteCode && <p className="invite-code" aria-live="polite">Share this one-time code: <code>{inviteCode}</code></p>}
      </section>
    </AppShell>
  );
}

type AdminStats = {
  organization: {
    name: string;
    id: string;
    team_size: number;
    total_system_users: number;
  };
  tenders: {
    total_ingested: number;
    open_tenders: number;
    sectors_breakdown: Record<string, number>;
  };
  pipeline: {
    total_tracked: number;
    by_stage: Record<string, number>;
    submitted: number;
    awarded: number;
  };
  system_health: {
    api_status: string;
    database_engine: string;
    ai_engine: string;
    auth_security: string;
  };
};

function AdminPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [members, setMembers] = useState<UserMe[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [inviteLoading, setInviteLoading] = useState(false);
  const [inviteError, setInviteError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      apiRequest<AdminStats>("/api/admin/stats"),
      apiRequest<UserMe[]>("/api/auth/members"),
    ])
      .then(([s, m]) => {
        if (mounted) {
          setStats(s);
          setMembers(m);
        }
      })
      .catch((err) => {
        if (mounted) setError(getErrorMessage(err));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  async function createInvite() {
    setInviteLoading(true);
    setInviteError("");
    setInviteCode("");
    setCopied(false);
    try {
      const res = await apiRequest<{ invitation_code: string }>("/api/auth/invitations", { method: "POST" });
      setInviteCode(res.invitation_code);
    } catch (err) {
      setInviteError(getErrorMessage(err));
    } finally {
      setInviteLoading(false);
    }
  }

  function copyCode() {
    if (!inviteCode) return;
    navigator.clipboard.writeText(inviteCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const stages = ["Discovered", "Interested", "Analyzing", "Preparing", "Submitted", "Awarded", "Not Awarded"];

  return (
    <AppShell view="admin">
      <PageHeading
        eyebrow="SYSTEM ADMINISTRATION & GOVERNANCE"
        title="Admin Command Center"
        description="Comprehensive monitoring of organizational operations, team access, tender repository metrics, and AI engine diagnostics."
        action={<span className="profile-status"><i /> Organization Administrator</span>}
      />

      {loading ? (
        <div className="profile-loading">
          <div className="skeleton-line short" />
          <div className="skeleton-line wide" />
          <div className="skeleton-line medium" />
        </div>
      ) : error ? (
        <div className="empty-panel" role="alert">
          <h3>Administrative Access Notice</h3>
          <p>{error}</p>
        </div>
      ) : (
        <>
          {/* Top KPI Metrics */}
          <div className="metrics-grid">
            <div className="metric-card metric-green">
              <div className="metric-top">
                <span>TEAM MEMBERS</span>
                <span className="metric-symbol">👥</span>
              </div>
              <strong>{stats?.organization.team_size ?? 1}</strong>
              <small>{stats?.organization.name} ({stats?.organization.total_system_users} platform users)</small>
            </div>

            <div className="metric-card">
              <div className="metric-top">
                <span>INGESTED TENDERS</span>
                <span className="metric-symbol">📑</span>
              </div>
              <strong>{stats?.tenders.total_ingested ?? 0}</strong>
              <small>{stats?.tenders.open_tenders ?? 0} currently open & active</small>
            </div>

            <div className="metric-card metric-gold">
              <div className="metric-top">
                <span>PIPELINE VELOCITY</span>
                <span className="metric-symbol">🚀</span>
              </div>
              <strong>{stats?.pipeline.total_tracked ?? 0}</strong>
              <small>{stats?.pipeline.submitted ?? 0} submitted · {stats?.pipeline.awarded ?? 0} awarded</small>
            </div>

            <div className="metric-card">
              <div className="metric-top">
                <span>AI ENGINE HEALTH</span>
                <span className="metric-symbol">⚡</span>
              </div>
              <strong style={{ fontSize: "22px", color: "var(--green-dark)", marginTop: "14px" }}>Active</strong>
              <small>Gemini 3.6 Flash + Grounding</small>
            </div>
          </div>

          <div className="admin-section">
            {/* Team & Role Management */}
            <div className="admin-card">
              <div className="admin-card-header">
                <div>
                  <h3>Team & Access Control (RBAC)</h3>
                  <small style={{ color: "var(--muted)" }}>Manage active organization members and issue single-use secure invite codes</small>
                </div>
                <button
                  type="button"
                  className="button button-outline"
                  onClick={() => void createInvite()}
                  disabled={inviteLoading}
                >
                  {inviteLoading ? "Generating..." : "+ Issue 24h Invite Code"}
                </button>
              </div>

              {inviteError && <p className="form-error">{inviteError}</p>}

              {inviteCode && (
                <div style={{ marginBottom: "18px", padding: "12px 16px", background: "#f0f8f3", border: "1px solid #c2e2ce", borderRadius: "5px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <span style={{ fontSize: "11px", fontWeight: "700", color: "var(--green-dark)" }}>NEW 24-HOUR INVITATION CODE:</span>
                    <code style={{ display: "block", fontSize: "13px", fontWeight: "600", color: "#17251f", marginTop: "3px" }}>{inviteCode}</code>
                  </div>
                  <button type="button" className="button button-primary" onClick={copyCode} style={{ padding: "6px 14px", fontSize: "11px" }}>
                    {copied ? "✓ Copied" : "Copy Code"}
                  </button>
                </div>
              )}

              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Member</th>
                    <th>Email Address</th>
                    <th>System Role</th>
                    <th>Account Status</th>
                  </tr>
                </thead>
                <tbody>
                  {members.map((m) => (
                    <tr key={m.id}>
                      <td>
                        <strong>{m.user_name}</strong>
                      </td>
                      <td>{m.email}</td>
                      <td>
                        <span className={`role-badge ${m.role.includes("Admin") ? "admin" : "member"}`}>
                          {m.role}
                        </span>
                      </td>
                      <td>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: "6px", color: "var(--green-dark)", fontWeight: "600", fontSize: "11px" }}>
                          <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#3ca978" }} />
                          Active
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Ingestion & Sector Distribution */}
            <div className="admin-card">
              <div className="admin-card-header">
                <div>
                  <h3>Tender Ingestion & Sector Allocation</h3>
                  <small style={{ color: "var(--muted)" }}>Breakdown of indexed Ethiopian procurement opportunities by category</small>
                </div>
                <Link href="/ingest" className="button button-outline" style={{ fontSize: "11px" }}>
                  Upload New Tender Notice ↗
                </Link>
              </div>

              <div className="sector-badge-list">
                {Object.entries(stats?.tenders.sectors_breakdown ?? {}).map(([sec, count]) => (
                  <div key={sec} className="sector-badge">
                    <span>{sec}</span>
                    <strong style={{ background: "var(--green-soft)", color: "var(--green-dark)", padding: "2px 6px", borderRadius: "3px" }}>
                      {count} {count === 1 ? "tender" : "tenders"}
                    </strong>
                  </div>
                ))}
              </div>
            </div>

            {/* Pipeline Stage Distribution */}
            <div className="admin-card">
              <div className="admin-card-header">
                <div>
                  <h3>Pipeline Stage Distribution</h3>
                  <small style={{ color: "var(--muted)" }}>Current opportunities progressed across the 7-stage bidding workflow</small>
                </div>
                <Link href="/opportunities" className="button button-outline" style={{ fontSize: "11px" }}>
                  Open Kanban Board ↗
                </Link>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "10px" }}>
                {stages.map((st) => {
                  const count = stats?.pipeline.by_stage[st] ?? 0;
                  return (
                    <div key={st} style={{ padding: "12px", background: "#f9fcf9", border: "1px solid #e2ebe4", borderRadius: "5px", textAlign: "center" }}>
                      <span style={{ fontSize: "11px", color: "#61746a", display: "block", marginBottom: "4px" }}>{st}</span>
                      <strong style={{ fontSize: "20px", color: count > 0 ? "var(--green-dark)" : "#9aa69f" }}>{count}</strong>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* System Architecture & Diagnostics */}
            <div className="admin-card">
              <div className="admin-card-header">
                <div>
                  <h3>System Architecture & Operational Diagnostics</h3>
                  <small style={{ color: "var(--muted)" }}>Runtime environment verification and compliance configuration</small>
                </div>
                <span className="live-indicator"><i /> Systems Healthy</span>
              </div>

              <div className="system-stat-grid">
                <div className="system-stat-box">
                  <label>API Architecture</label>
                  <span>FastAPI (Python 3.12 Asynchronous)</span>
                </div>
                <div className="system-stat-box">
                  <label>Database Engine</label>
                  <span>{stats?.system_health.database_engine ?? "SQLite / SQLAlchemy"}</span>
                </div>
                <div className="system-stat-box">
                  <label>AI & RAG Engine</label>
                  <span>{stats?.system_health.ai_engine ?? "Google Gemini 3.6 Flash"}</span>
                </div>
                <div className="system-stat-box">
                  <label>Security & Governance</label>
                  <span>{stats?.system_health.auth_security ?? "JWT + bcrypt"} (FR-12 Disclaimed)</span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
}

function subscribeToAuth(onChange: () => void) {
  window.addEventListener("etioms:auth-changed", onChange);
  window.addEventListener("etioms:unauthorized", onChange);
  return () => {
    window.removeEventListener("etioms:auth-changed", onChange);
    window.removeEventListener("etioms:unauthorized", onChange);
  };
}

function getAuthSnapshot() {
  return Boolean(window.sessionStorage.getItem("access_token"));
}

export default function EtiomsApp({ view }: { view: View }) {
  const authenticated = useSyncExternalStore(subscribeToAuth, getAuthSnapshot, () => false);
  if (!authenticated) return <AuthPage />;
  if (view === "admin") return <AdminPage />;
  if (view === "pipeline") return <PipelinePage />;
  if (view === "ingest") return <IngestPage />;
  if (view === "profile") return <ProfilePage />;
  return <Dashboard />;
}