"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type View = "dashboard" | "ingest" | "profile";

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
      // Keep the HTTP status message when the response is not JSON.
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

function AppShell({ view, children }: { view: View; children: React.ReactNode }) {
  const router = useRouter();
  const links: { href: string; label: string; view: View }[] = [
    { href: "/", label: "Ranked opportunities", view: "dashboard" },
    { href: "/ingest", label: "Upload tender", view: "ingest" },
    { href: "/profile", label: "Company profile", view: "profile" },
  ];

  return (
    <div className="app-frame">
      <header className="topbar">
        <Link className="brand" href="/" aria-label="ETIOMS home"><BrandMark /><span>ETIOMS<small>PROCUREMENT INTELLIGENCE</small></span></Link>
        <nav className="main-nav" aria-label="Main navigation">
          {links.map((link) => <Link key={link.href} href={link.href} className={view === link.view ? "nav-link active" : "nav-link"}>{link.label}</Link>)}
        </nav>
        <div className="account-actions"><Link className="company-chip" href="/profile"><span className="company-avatar">A</span><span>Company profile</span><span className="chip-arrow">↗</span></Link><button className="button button-outline sign-out-button" onClick={() => { window.sessionStorage.removeItem("access_token"); window.dispatchEvent(new Event("etioms:auth-changed")); router.replace("/"); }}>Sign out</button></div>
      </header>
      <main className="page-main">{children}</main>
      <footer className="app-footer"><span>ETIOMS <span className="footer-dot">/</span> Ethiopian Tender Intelligence</span><span>Built for better bids</span></footer>
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

  return <div className="auth-page">
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
  </div>;
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

  useEffect(() => {
    let mounted = true;
    apiRequest<Match[]>("/api/profile/matches")
      .then((data) => { if (mounted) setMatches(data); })
      .catch((reason: unknown) => { if (mounted) setError(getErrorMessage(reason)); })
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, []);

  const sectorOptions = useMemo(() => ["All sectors", ...Array.from(new Set(matches.map((match) => match.sector).filter(Boolean))).sort()], [matches]);
  const filtered = useMemo(() => matches.filter((match) =>
    match.procuring_entity.toLowerCase().includes(search.trim().toLowerCase()) &&
    (sector === "All sectors" || match.sector === sector) && match.total_score >= minScore
  ), [matches, search, sector, minScore]);
  const qualified = matches.filter((match) => match.is_qualified).length;
  const averageScore = matches.length ? Math.round(matches.reduce((sum, match) => sum + match.total_score, 0) / matches.length) : 0;

  return <AppShell view="dashboard">
    <PageHeading eyebrow="OPPORTUNITY RADAR · ADDIS ABABA" title="Ranked opportunities" description="A clear view of where your company can compete and win." action={<span className="live-indicator"><i /> Live intelligence</span>} />
    <section className="metrics-grid" aria-label="Opportunity metrics">
      <Metric label="Total opportunities" value={matches.length} detail="Open tenders assessed" tone="ink" symbol="↗" />
      <Metric label="Qualified bids" value={qualified} detail="Match score of 60 or above" tone="green" symbol="✓" />
      <Metric label="Disqualified bids" value={matches.length - qualified} detail="Below qualification threshold" tone="red" symbol="×" />
      <Metric label="Average match score" value={`${averageScore}%`} detail="Across current opportunities" tone="gold" symbol="◎" />
    </section>

    <section className="opportunities-section">
      <div className="section-heading"><div><p className="eyebrow">YOUR PIPELINE</p><h2>Recommended tenders <span className="count-badge">{filtered.length}</span></h2></div><span className="sort-note">Sorted by strongest match <span aria-hidden="true">↓</span></span></div>
      <div className="filter-bar">
        <label className="search-field"><span aria-hidden="true">⌕</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search procuring entity" aria-label="Search procuring entity" /></label>
        <label className="select-field"><span>Sector</span><select value={sector} onChange={(event) => setSector(event.target.value)}>{sectorOptions.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label className="score-filter"><span>Minimum score <b>{minScore}%</b></span><input type="range" min="0" max="100" step="5" value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} aria-label="Minimum match score" /></label>
      </div>

      {loading && <div className="tender-list" aria-label="Loading opportunities">{[0, 1, 2].map((item) => <div className="tender-skeleton" key={item}><div className="skeleton-line short" /><div className="skeleton-line wide" /><div className="skeleton-line medium" /></div>)}</div>}
      {!loading && error && <div className="state-panel error-panel"><span className="state-icon">!</span><div><h3>Couldn’t load opportunities</h3><p>{error}</p>{error.toLowerCase().includes("profile") && <Link className="button button-primary" href="/profile">Set up company profile <span>↗</span></Link>}</div><button className="button button-outline" onClick={() => window.location.reload()}>Try again</button></div>}
      {!loading && !error && filtered.length === 0 && <div className="state-panel empty-panel"><span className="state-icon">⌕</span><div><h3>{matches.length ? "No tenders match these filters" : "Your opportunity list is clear"}</h3><p>{matches.length ? "Adjust your search or lower the minimum score." : "Once a company profile is saved and tenders are available, ranked matches will appear here."}</p></div>{!matches.length && <Link className="button button-primary" href="/ingest">Add a tender <span>↗</span></Link>}</div>}
      {!loading && !error && filtered.length > 0 && <div className="tender-list">{filtered.map((match) => <TenderCard key={match.tender_id} match={match} onOpen={() => setActiveMatch(match)} />)}</div>}
    </section>
    {activeMatch && <MatchDrawer match={activeMatch} onClose={() => setActiveMatch(null)} />}
  </AppShell>;
}

function Metric({ label, value, detail, tone, symbol }: { label: string; value: string | number; detail: string; tone: string; symbol: string }) {
  return <article className={`metric-card metric-${tone}`}><div className="metric-top"><span>{label}</span><span className="metric-symbol" aria-hidden="true">{symbol}</span></div><strong>{value}</strong><small>{detail}</small></article>;
}

function TenderCard({ match, onOpen }: { match: Match; onOpen: () => void }) {
  const score = Math.max(0, Math.min(100, match.total_score));
  return <article className="tender-card">
    <div className="tender-main">
      <div className="tender-tags"><span className={match.is_qualified ? "decision-badge bid" : "decision-badge no-bid"}><i />{match.compliance_decision || (match.is_qualified ? "BID" : "NO-BID")}</span>{match.cached && <span className="cached-badge"><span aria-hidden="true">ϟ</span> Cached</span>}<span className="sector-tag">{match.sector}</span></div>
      <h3>{match.tender_title}</h3>
      <div className="tender-meta"><span><span className="meta-icon">▤</span>{match.procuring_entity}</span><span><span className="meta-icon">◷</span>Due {formatDate(match.deadline)}</span><span><span className="meta-icon">⌖</span>{match.region}</span></div>
    </div>
    <div className="tender-score"><div className="score-label"><span>Match score</span><strong>{Math.round(score)}<small>%</small></strong></div><div className="score-track"><span style={{ width: `${score}%` }} /></div><small className="score-caption">{score >= 80 ? "Excellent fit" : score >= 60 ? "Good potential" : "Needs review"}</small></div>
    <button className="button button-outline detail-button" onClick={onOpen}>View details <span aria-hidden="true">↗</span></button>
  </article>;
}

function MatchDrawer({ match, onClose }: { match: Match; onClose: () => void }) {
  const [detail, setDetail] = useState<Match>(match);
  const [compliance, setCompliance] = useState<Compliance | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

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

  return <div className="drawer-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className="detail-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
      <div className="drawer-header"><div><p className="eyebrow">TENDER INTELLIGENCE</p><span className={detail.is_qualified ? "decision-badge bid" : "decision-badge no-bid"}><i />{detail.compliance_decision || (detail.is_qualified ? "BID" : "NO-BID")}</span></div><button className="icon-button" onClick={onClose} aria-label="Close details">×</button></div>
      <h2 id="drawer-title">{detail.tender_title}</h2><p className="drawer-entity">{detail.procuring_entity} <span>·</span> {detail.sector}</p>
      <div className="drawer-scroll">
        {error && <div className="inline-error">{error}</div>}
        {loading ? <div className="drawer-loading"><div className="skeleton-line short" /><div className="skeleton-line wide" /><div className="skeleton-line wide" /></div> : <>
          <section className="drawer-score-panel"><div><span className="eyebrow">TOTAL MATCH SCORE</span><strong>{Math.round(detail.total_score)}<small>%</small></strong></div><div className="drawer-score-track"><span style={{ width: `${Math.max(0, Math.min(100, detail.total_score))}%` }} /></div><div className="drawer-tender-facts"><span><small>Deadline</small>{formatDate(detail.deadline)}</span><span><small>Estimated budget</small>{formatBudget(detail.budget)}</span></div></section>
          <section className="drawer-section"><div className="drawer-section-title"><h3>Score breakdown</h3><span>100 pts possible</span></div><div className="breakdown-list">{scoreRows.map(([label, value, max]) => <div className="breakdown-row" key={label}><div><span>{label}</span><b>{value}<small> / {max}</small></b></div><div className="breakdown-track"><span style={{ width: `${Math.max(0, Math.min(100, value / max * 100))}%` }} /></div></div>)}</div></section>
          <section className="justification-box"><div className="justification-heading"><span className="spark-icon">✳</span><div><p className="eyebrow">GEMINI ANALYSIS</p><h3>Why this match</h3></div></div><p>{typeof breakdown.ai_justification === "string" ? breakdown.ai_justification : detail.ai_justification || "No AI justification is available for this match."}</p></section>
          <section className="drawer-section compliance-section"><div className="drawer-section-title"><h3>FPPA compliance</h3>{compliance && <span className={`audit-decision ${compliance.bid_decision.toLowerCase()}`}>{compliance.bid_decision}</span>}</div>{compliance ? <><p className="compliance-intro">{compliance.executive_justification}</p><div className="checklist">{compliance.preliminary_checklist?.map((item, index) => <div className="check-row" key={`${item.requirement_name}-${index}`}><span className={`check-status ${item.status.toLowerCase()}`}>{item.status === "PASS" ? "✓" : item.status === "FAIL" ? "×" : "!"}</span><div><strong>{item.requirement_name}</strong><p>{item.evidence_or_gap}</p></div></div>)}</div>{compliance.critical_disqualification_risks?.length > 0 && <div className="risk-note"><strong>Critical risks</strong>{compliance.critical_disqualification_risks.map((risk) => <p key={risk}>{risk}</p>)}</div>}</> : <div className="compliance-unavailable">Compliance audit could not be loaded. The match score is still available.</div>}</section>
        </>}
      </div>
      <div className="drawer-footer"><button className="button button-outline" onClick={() => void load(true)} disabled={refreshing || loading}><span aria-hidden="true">↻</span>{refreshing ? "Refreshing with AI…" : "Force AI refresh"}</button><button className="button button-primary" onClick={onClose}>Done</button></div>
    </aside>
  </div>;
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

  return <AppShell view="ingest">
    <PageHeading eyebrow="TENDER INTAKE" title="Bring an opportunity in" description="Upload a notice or paste its text. ETIOMS will structure it and add it to your ranked pipeline." />
    <div className="ingest-layout"><form className="form-panel ingest-form" onSubmit={submit}>
      <div className="panel-heading"><div><span className="step-number">01</span><div><h2>Source document</h2><p>Upload a file or paste the procurement notice.</p></div></div></div>
      <label className="upload-dropzone" htmlFor="tender-file"><span className="upload-icon">↑</span><strong>{file ? file.name : "Choose a tender file"}</strong><small>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · Ready to parse` : "PDF or plain text · 20 MB max"}</small><span className="button button-outline">Browse files</span><input id="tender-file" type="file" accept=".pdf,.txt,application/pdf,text/plain" onChange={(event) => { const selected = event.target.files?.[0] ?? null; setFile(selected); setError(""); }} /></label>
      <div className="or-divider"><span>OR PASTE NOTICE TEXT</span></div>
      <label className="field-label" htmlFor="notice-text">Procurement notice</label><textarea id="notice-text" className="text-area notice-area" value={text} onChange={(event) => { setText(event.target.value); setError(""); }} placeholder="Paste the complete procurement notice here…" rows={10} />
      {error && <p className="form-error">{error}</p>}
      <button className="button button-primary submit-button" type="submit" disabled={loading}>{loading ? <><span className="button-spinner" />Parsing with Gemini…</> : <>Extract tender details <span>↗</span></>}</button>
    </form>
    <aside className="ingest-aside"><div className="aside-orbit"><span className="orbit-core">E</span><span className="orbit-tag">AI</span></div><p className="eyebrow">FROM NOTICE TO OPPORTUNITY</p><h2>One document.<br />A clearer next move.</h2><p>ETIOMS extracts key facts and requirements, then scores the opportunity against your company profile.</p><div className="process-list"><div><span>01</span><p>Upload or paste a notice</p></div><div><span>02</span><p>AI extracts the essentials</p></div><div><span>03</span><p>Review your match score</p></div></div></aside></div>
    {loading && <div className="parse-result loading-result" aria-live="polite"><div className="skeleton-line short" /><div className="skeleton-line wide" /><div className="skeleton-line medium" /><div className="skeleton-line wide" /></div>}
    {tender && <section className="parse-result"><div className="result-header"><div><p className="eyebrow">NOTICE PARSED SUCCESSFULLY</p><h2>{tender.title}</h2></div><span className="result-check">✓</span></div><div className="result-grid"><ResultField label="Procuring entity" value={tender.procuring_entity} /><ResultField label="Budget" value={formatBudget(tender.budget)} /><ResultField label="Deadline" value={formatDate(tender.deadline)} /><ResultField label="Sector · Region" value={`${tender.sector} · ${tender.region}`} /></div>{tender.requirements.length > 0 && <div className="requirements-list"><strong>Extracted requirements</strong><div>{tender.requirements.map((requirement) => <span key={requirement}>{requirement}</span>)}</div></div>}<Link className="button button-primary" href="/">See ranked opportunities <span>↗</span></Link></section>}
  </AppShell>;
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

  return <AppShell view="profile">
    <PageHeading eyebrow="COMPANY READINESS" title="Your company profile" description="Keep your capabilities current. ETIOMS uses this information to qualify and rank tenders." action={<span className="profile-status"><i /> Profile settings</span>} />
    {loading ? <div className="profile-loading"><div className="skeleton-line short" /><div className="skeleton-line wide" /><div className="skeleton-line medium" /><div className="skeleton-line wide" /></div> : <form className="profile-form" onSubmit={saveProfile}>
      <section className="form-panel"><div className="panel-heading"><div><span className="step-number">01</span><div><h2>Company details</h2><p>Basic information about your organization.</p></div></div><span className="panel-index">IDENTITY</span></div><div className="form-grid"><label className="form-control full-width"><span>Company name</span><input required value={profile.company_name} onChange={(event) => update("company_name", event.target.value)} placeholder="Your registered business name" /></label><div className="form-control"><span>Years of experience</span><div className="number-input"><input min="0" type="number" value={profile.years_experience} onChange={(event) => update("years_experience", Math.max(0, Number(event.target.value)))} /><small>years</small></div></div></div></section>
      <section className="form-panel"><div className="panel-heading"><div><span className="step-number">02</span><div><h2>Areas of work</h2><p>Choose sectors and regions where you operate.</p></div></div><span className="panel-index">COVERAGE</span></div><div className="tag-entry"><label className="field-label" htmlFor="sector-entry">Sectors</label><div className="tag-input"><div className="selected-tags">{profile.sectors.map((item) => <button type="button" className="selected-tag" key={item} onClick={() => update("sectors", profile.sectors.filter((sectorName) => sectorName !== item))}>{item}<span aria-label={`Remove ${item}`}>×</span></button>)}<input id="sector-entry" value={sectorInput} onChange={(event) => setSectorInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); addSector(); } }} placeholder="Add a sector, use commas for several" /></div><button type="button" className="button button-outline add-tag-button" onClick={addSector}>Add</button></div></div><div className="field-label region-label">Operating regions</div><div className="pill-options">{regions.map((region) => <button className={profile.operating_regions.includes(region) ? "option-pill selected" : "option-pill"} type="button" key={region} onClick={() => toggleValue("operating_regions", region)}><span>{profile.operating_regions.includes(region) ? "✓" : "+"}</span>{region}</button>)}</div></section>
      <section className="form-panel"><div className="panel-heading"><div><span className="step-number">03</span><div><h2>Certifications & track record</h2><p>Credentials and experience that support your bids.</p></div></div><span className="panel-index">QUALIFICATIONS</span></div><div className="certification-grid">{certifications.map((certification) => <label className="check-option" key={certification}><input type="checkbox" checked={profile.certifications.includes(certification)} onChange={() => toggleValue("certifications", certification)} /><span className="custom-checkbox">✓</span>{certification}</label>)}</div><label className="form-control project-field"><span>Past projects summary</span><textarea className="text-area" rows={5} value={profile.past_projects_summary ?? ""} onChange={(event) => update("past_projects_summary", event.target.value)} placeholder="Describe relevant projects, clients, outcomes, and technical capabilities…" /></label></section>
      {error && <p className="form-error">{error}</p>}
      <div className="profile-actions"><span>{saved ? <span className="saved-message">✓ Profile saved successfully</span> : "Changes are saved to your ETIOMS profile."}</span><button className="button button-primary" type="submit" disabled={saving}>{saving ? <><span className="button-spinner" />Saving profile…</> : <>Save company profile <span>↗</span></>}</button></div>
    </form>}
    <section className="form-panel invite-panel"><div className="panel-heading"><div><span className="step-number">＋</span><div><h2>Invite a company member</h2><p>Anyone in your company can create a single-use invitation, valid for 24 hours.</p></div></div></div><button className="button button-outline" type="button" onClick={() => void createInvite()} disabled={inviteLoading}>{inviteLoading ? "Creating invitation…" : "Create invitation code"}</button>{inviteError && <p className="form-error" role="alert">{inviteError}</p>}{inviteCode && <p className="invite-code" aria-live="polite">Share this one-time code: <code>{inviteCode}</code></p>}</section>
  </AppShell>;
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
  if (view === "ingest") return <IngestPage />;
  if (view === "profile") return <ProfilePage />;
  return <Dashboard />;
}