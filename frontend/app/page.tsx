"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Activity,
  Bell,
  Boxes,
  Check,
  ChevronDown,
  CircleCheck,
  CircleDot,
  Clock3,
  Command,
  Database,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  LogOut,
  MoreHorizontal,
  Moon,
  Mail,
  Play,
  Plus,
  Search,
  Server,
  ShieldCheck,
  Settings,
  TerminalSquare,
  Sun,
  UserRound,
  Users,
  UserPlus,
  Workflow,
  X,
  Zap,
} from "lucide-react";
import {
  Background,
  Controls,
  Edge,
  Handle,
  MarkerType,
  Node,
  Position,
  ReactFlow,
} from "@xyflow/react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "@xyflow/react/dist/style.css";
import "./manage.css";

type View = "overview" | "workflows" | "runs" | "workers" | "team" | "settings";
type DashboardSnapshot = {
  running_workflows: number;
  success_rate: number;
  average_execution_seconds: number;
  queue: { pending: number; running: number; retrying: number; dead_letter: number };
  workers: Array<{ id: string; status: string; runtime: string; seen_at: string }>;
};
type ApiRun = { id: string; workflow_id: string; status: string; created_at: string };

const workspaces = [
  { name: "Acme systems", environment: "Production", initials: "AS" },
  { name: "RelayFlow labs", environment: "Development", initials: "RL" },
  { name: "Personal sandbox", environment: "Staging", initials: "PS" },
];

const teamMembers = [
  { name: "Shaambhavi Sharma", email: "shaambhavi03@gmail.com", role: "Admin", initials: "SS", status: "Active" },
  { name: "Aarav Mehta", email: "aarav@acme.dev", role: "Developer", initials: "AM", status: "Active" },
  { name: "Riya Kapoor", email: "riya@acme.dev", role: "Developer", initials: "RK", status: "Active" },
  { name: "Kabir Singh", email: "kabir@acme.dev", role: "Viewer", initials: "KS", status: "Invited" },
];

const metrics = [
  { label: "Running workflows", value: "18", delta: "+4", icon: Play, tone: "blue" },
  { label: "Queued jobs", value: "41", delta: "-12%", icon: ListChecks, tone: "amber" },
  { label: "Workers online", value: "8", delta: "8 / 9", icon: Server, tone: "violet" },
  { label: "Success rate", value: "99.2%", delta: "+0.4%", icon: CircleCheck, tone: "green" },
];

const chartData = [
  { time: "00:00", runs: 92 }, { time: "04:00", runs: 61 },
  { time: "08:00", runs: 142 }, { time: "12:00", runs: 124 },
  { time: "16:00", runs: 188 }, { time: "20:00", runs: 164 },
  { time: "Now", runs: 214 },
];

const recentRuns = [
  { id: "#RF-5241", workflow: "Order fulfillment", status: "Running", duration: "38s", tasks: "4 / 6", worker: "worker-04", time: "Just now" },
  { id: "#RF-5240", workflow: "Customer data sync", status: "Completed", duration: "14s", tasks: "5 / 5", worker: "worker-02", time: "2m ago" },
  { id: "#RF-5239", workflow: "Invoice processor", status: "Retrying", duration: "1m 42s", tasks: "2 / 4", worker: "worker-07", time: "4m ago" },
  { id: "#RF-5238", workflow: "Daily analytics", status: "Completed", duration: "51s", tasks: "8 / 8", worker: "worker-01", time: "8m ago" },
  { id: "#RF-5237", workflow: "Webhook delivery", status: "Failed", duration: "9s", tasks: "1 / 3", worker: "worker-06", time: "11m ago" },
];

const workflowList = [
  { name: "Order fulfillment", description: "Validate, reserve stock, charge and notify", tasks: 6, runs: 1284, success: "99.6%", active: true },
  { name: "Customer data sync", description: "Sync CRM contacts with the data warehouse", tasks: 5, runs: 864, success: "98.9%", active: true },
  { name: "Invoice processor", description: "Parse invoices, validate totals and archive", tasks: 4, runs: 429, success: "97.2%", active: true },
  { name: "Daily analytics", description: "Aggregate product metrics and publish reports", tasks: 8, runs: 92, success: "100%", active: false },
];

const workers = [
  { name: "worker-01", status: "Healthy", jobs: 12, cpu: 34, heartbeat: "2s ago" },
  { name: "worker-02", status: "Healthy", jobs: 9, cpu: 41, heartbeat: "1s ago" },
  { name: "worker-03", status: "Busy", jobs: 18, cpu: 86, heartbeat: "1s ago" },
  { name: "worker-04", status: "Healthy", jobs: 14, cpu: 52, heartbeat: "3s ago" },
  { name: "worker-09", status: "Offline", jobs: 0, cpu: 0, heartbeat: "18m ago" },
];

function TaskNode({ data }: { data: { label: string; type: string; status: string } }) {
  return (
    <div className={`flow-node ${data.status}`}>
      <Handle type="target" position={Position.Left} />
      <div className="node-icon"><Zap size={14} /></div>
      <div><strong>{data.label}</strong><span>{data.type}</span></div>
      <CircleCheck className="node-check" size={16} />
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const nodeTypes = { task: TaskNode };
const graphNodes: Node[] = [
  { id: "1", type: "task", position: { x: 0, y: 75 }, data: { label: "Validate order", type: "Transform", status: "done" } },
  { id: "2", type: "task", position: { x: 240, y: 10 }, data: { label: "Reserve stock", type: "API call", status: "done" } },
  { id: "3", type: "task", position: { x: 240, y: 140 }, data: { label: "Process payment", type: "API call", status: "running" } },
  { id: "4", type: "task", position: { x: 480, y: 75 }, data: { label: "Send confirmation", type: "Email", status: "waiting" } },
];
const graphEdges: Edge[] = [
  { id: "e12", source: "1", target: "2" }, { id: "e13", source: "1", target: "3" },
  { id: "e24", source: "2", target: "4" }, { id: "e34", source: "3", target: "4" },
].map((edge) => ({ ...edge, animated: edge.id === "e34", style: { stroke: "#6175f7", strokeWidth: 2 }, markerEnd: { type: MarkerType.ArrowClosed, color: "#6175f7" } }));

function Status({ value }: { value: string }) {
  return <span className={`status status-${value.toLowerCase()}`}><i />{value}</span>;
}

function ShellTitle({ view }: { view: View }) {
  const copy = {
    overview: ["Control center", "Monitor your distributed workflows in real time."],
    workflows: ["Workflows", "Define, version and operate durable task graphs."],
    runs: ["Execution history", "Inspect every run, retry and worker assignment."],
    workers: ["Worker fleet", "Health and capacity across your execution nodes."],
    team: ["Team", "Manage workspace members, invitations and access roles."],
    settings: ["Settings", "Configure your workspace, execution and security preferences."],
  }[view];
  return <div><h1>{copy[0]}</h1><p>{copy[1]}</p></div>;
}

export default function Home() {
  const [view, setView] = useState<View>("overview");
  const [builderOpen, setBuilderOpen] = useState(false);
  const [selectedRun, setSelectedRun] = useState<(typeof recentRuns)[number] | null>(null);
  const [dashboard, setDashboard] = useState<DashboardSnapshot | null>(null);
  const [apiRuns, setApiRuns] = useState<ApiRun[]>([]);
  const [apiConnected, setApiConnected] = useState(false);
  const [search, setSearch] = useState("");
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [activeWorkspace, setActiveWorkspace] = useState(workspaces[0]);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [saved, setSaved] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [profileModal, setProfileModal] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const [loginEmail, setLoginEmail] = useState("admin@relayflow.local");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [displayName, setDisplayName] = useState("Shaambhavi");
  const [settings, setSettings] = useState({ workspaceName: "Acme systems", retention: "30", maxRetries: "3", alerts: true, failedRunAlerts: true });
  const [workflowName, setWorkflowName] = useState("Data import pipeline");
  const [workflowDescription, setWorkflowDescription] = useState("Import, validate and publish customer records.");
  const [tasks, setTasks] = useState([
    { name: "Import orders", dependency: "None", action: "API call" },
    { name: "Validate rows", dependency: "Import orders", action: "Transform" },
  ]);
  useEffect(() => {
    setAuthenticated(Boolean(sessionStorage.getItem("relayflow-token")));
    setAuthChecked(true);
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    const api = process.env.NEXT_PUBLIC_RELAYFLOW_API_URL || "http://localhost:8000";
    let active = true;
    const refresh = async () => {
      try {
        const token = sessionStorage.getItem("relayflow-token");
        if (!token) throw new Error("Missing session");
        const headers = { Authorization: `Bearer ${token}` };
        const [dashboardResponse, runsResponse] = await Promise.all([
          fetch(`${api}/api/v1/dashboard`, { headers }),
          fetch(`${api}/api/v1/runs?limit=20`, { headers }),
        ]);
        if (!dashboardResponse.ok || !runsResponse.ok) throw new Error("API unavailable");
        if (active) {
          setDashboard(await dashboardResponse.json());
          setApiRuns(await runsResponse.json());
          setApiConnected(true);
        }
      } catch {
        if (active) {
          sessionStorage.removeItem("relayflow-token");
          setApiConnected(false);
          setAuthenticated(false);
          setLoginError("Your session expired. Please sign in again.");
        }
      }
    };
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, [authenticated]);

  const login = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const api = process.env.NEXT_PUBLIC_RELAYFLOW_API_URL || "http://localhost:8000";
    setLoginLoading(true);
    setLoginError("");
    try {
      const response = await fetch(`${api}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: loginEmail.trim(), password: loginPassword }),
      });
      if (!response.ok) {
        throw new Error(response.status === 401 ? "Invalid email or password." : "Unable to sign in right now.");
      }
      const payload = await response.json();
      sessionStorage.setItem("relayflow-token", payload.access_token);
      setAuthenticated(true);
      setLoginPassword("");
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : "Unable to sign in.");
    } finally {
      setLoginLoading(false);
    }
  };

  const logout = () => {
    sessionStorage.removeItem("relayflow-token");
    setApiConnected(false);
    setDashboard(null);
    setApiRuns([]);
    setAuthenticated(false);
    setProfileOpen(false);
  };

  const displayRuns = apiConnected && apiRuns.length ? apiRuns.map((run) => ({
    id: `#${run.id.slice(0, 8)}`, workflow: run.workflow_id.slice(0, 12),
    status: run.status.charAt(0).toUpperCase() + run.status.slice(1), duration: "Live",
    tasks: "API", worker: "distributed", time: new Date(run.created_at).toLocaleTimeString(),
  })) : recentRuns;
  const visibleRuns = useMemo(() => displayRuns.filter((run) => `${run.id} ${run.workflow}`.toLowerCase().includes(search.toLowerCase())), [search, displayRuns]);
  const displayMetrics = dashboard ? [
    { ...metrics[0], value: String(dashboard.running_workflows), delta: "Live" },
    { ...metrics[1], value: String(dashboard.queue.pending), delta: `${dashboard.queue.retrying} retrying` },
    { ...metrics[2], value: String(dashboard.workers.length), delta: "Redis" },
    { ...metrics[3], value: `${dashboard.success_rate}%`, delta: `${dashboard.average_execution_seconds}s avg` },
  ] : metrics;
  const displayWorkers = dashboard?.workers.length ? dashboard.workers.map((worker) => ({
    name: worker.id, status: worker.status === "healthy" ? "Healthy" : worker.status,
    jobs: 0, cpu: 0, heartbeat: new Date(worker.seen_at).toLocaleTimeString(),
  })) : workers;

  const createWorkflow = async () => {
    const api = process.env.NEXT_PUBLIC_RELAYFLOW_API_URL || "http://localhost:8000";
    const token = sessionStorage.getItem("relayflow-token");
    if (!token) return;
    const normalize = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    const response = await fetch(`${api}/api/v1/workflows`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        name: workflowName, description: workflowDescription,
        tasks: tasks.map((task, index) => ({
          key: normalize(task.name) || `task_${index + 1}`,
          type: task.action === "Delay" ? "delay" : task.action === "Transform" ? "transform" : "http",
          depends_on: task.dependency === "None" ? [] : [normalize(task.dependency)],
          config: task.action === "Delay" ? { seconds: 1 } : task.action === "Transform" ? { value: task.name } : { url: "https://httpbin.org/post", method: "POST" },
          retry: { max_attempts: Number(settings.maxRetries), backoff_seconds: 2 },
        })),
      }),
    });
    if (response.ok) { setBuilderOpen(false); setView("workflows"); setSaved(true); }
  };

  const nav = [
    { id: "overview" as View, label: "Overview", icon: LayoutDashboard },
    { id: "workflows" as View, label: "Workflows", icon: Workflow },
    { id: "runs" as View, label: "Executions", icon: ListChecks },
    { id: "workers" as View, label: "Workers", icon: Server },
  ];

  if (!authChecked) return null;

  if (!authenticated) return (
    <main className="signed-out">
      <section>
        <div className="brand-mark"><Command /></div>
        <h1>Sign in to RelayFlow</h1>
        <p>Use your RelayFlow account to access the control center.</p>
        <form onSubmit={login} style={{ display: "grid", gap: 14, width: "min(360px, 100%)", marginTop: 24 }}>
          <label style={{ display: "grid", gap: 7, textAlign: "left", fontSize: 13 }}>
            Email address
            <input
              type="email"
              autoComplete="username"
              value={loginEmail}
              onChange={(event) => setLoginEmail(event.target.value)}
              required
              style={{ minHeight: 44, border: "1px solid #dfe2ec", borderRadius: 9, padding: "0 12px" }}
            />
          </label>
          <label style={{ display: "grid", gap: 7, textAlign: "left", fontSize: 13 }}>
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={loginPassword}
              onChange={(event) => setLoginPassword(event.target.value)}
              required
              style={{ minHeight: 44, border: "1px solid #dfe2ec", borderRadius: 9, padding: "0 12px" }}
            />
          </label>
          {loginError && <p role="alert" style={{ color: "#c53030", margin: 0, fontSize: 13 }}>{loginError}</p>}
          <button className="primary" type="submit" disabled={loginLoading}>
            {loginLoading ? "Signing inâ€¦" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );

  return (
    <main className={`app-shell ${darkMode ? "theme-dark" : ""}`}>
      <aside className="sidebar">
        <div className="brand"><div className="brand-mark"><Command /></div><span>RelayFlow</span><em>cloud</em></div>
        <div className="workspace-wrap">
          <button className={`workspace ${workspaceOpen ? "open" : ""}`} onClick={() => setWorkspaceOpen(!workspaceOpen)} aria-expanded={workspaceOpen}>
            <span className="avatar">{activeWorkspace.initials}</span><div><strong>{activeWorkspace.name}</strong><small>{activeWorkspace.environment}</small></div><ChevronDown size={15} />
          </button>
          {workspaceOpen && <div className="workspace-menu"><small>Switch workspace</small>{workspaces.map((workspace) => <button key={workspace.name} onClick={() => { setActiveWorkspace(workspace); setSettings({...settings, workspaceName: workspace.name}); setWorkspaceOpen(false); }}><span>{workspace.initials}</span><div><strong>{workspace.name}</strong><em>{workspace.environment}</em></div>{workspace.name === activeWorkspace.name && <Check size={14}/>}</button>)}</div>}
        </div>
        <nav>
          <p>Workspace</p>
          {nav.map((item) => <button key={item.id} onClick={() => setView(item.id)} className={view === item.id ? "active" : ""}><item.icon size={17} />{item.label}{item.id === "runs" && <b>18</b>}</button>)}
          <p>Manage</p>
          <button onClick={() => setView("team")} className={view === "team" ? "active" : ""}><Users size={17} />Team</button><button onClick={() => setView("settings")} className={view === "settings" ? "active" : ""}><Settings size={17} />Settings</button>
        </nav>
        <div className="system-card"><div><span className="pulse" /><strong>All systems operational</strong></div><small>Last checked 8s ago</small></div>
        <div className="profile-wrap"><div className="profile"><span className="profile-avatar">SS</span><div><strong>{displayName}</strong><small>Administrator</small></div><button className="profile-menu-button" onClick={() => setProfileOpen(!profileOpen)} aria-label="Open profile menu" aria-expanded={profileOpen}><MoreHorizontal size={18}/></button></div>
          {profileOpen && <div className="profile-menu"><div className="profile-menu-head"><span className="profile-avatar">SS</span><div><strong>{displayName} Sharma</strong><small>shaambhavi03@gmail.com</small></div></div><button onClick={() => { setProfileModal(true); setProfileOpen(false); }}><UserRound size={15}/><span>View profile</span></button><button onClick={() => { setView("settings"); setProfileOpen(false); }}><Settings size={15}/><span>Account settings</span></button><button onClick={() => setDarkMode(!darkMode)}>{darkMode ? <Sun size={15}/> : <Moon size={15}/>}<span>{darkMode ? "Use light theme" : "Use dark theme"}</span><em>{darkMode ? "Light" : "Dark"}</em></button><hr/><button className="sign-out" onClick={logout}><LogOut size={15}/><span>Sign out</span></button></div>}
        </div>
      </aside>

      <section className="content">
        <header>
          <div className="global-search"><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search runs, workflows..." /><kbd>âŒ˜ K</kbd></div>
          <button className="icon-button" aria-label="Notifications"><Bell size={19} /><i /></button>
          <button className="primary" onClick={() => setBuilderOpen(true)}><Plus size={17} />New workflow</button>
        </header>

        <div className="page">
          <div className="page-title"><ShellTitle view={view} /><div className="live"><span />{apiConnected ? "Backend connected" : "Demo fallback"}</div></div>

          {view === "overview" && <>
            <div className="metrics">{displayMetrics.map((metric) => <article className="metric" key={metric.label}><div className={`metric-icon ${metric.tone}`}><metric.icon size={19} /></div><div><p>{metric.label}</p><strong>{metric.value}</strong></div><span className={metric.delta.startsWith("-") ? "negative" : ""}>{metric.delta}</span></article>)}</div>
            <div className="overview-grid">
              <article className="panel throughput"><div className="panel-head"><div><h2>Workflow throughput</h2><p>Successful runs over the last 24 hours</p></div><button>Last 24 hours <ChevronDown size={14} /></button></div><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData}><defs><linearGradient id="relayFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#6677f4" stopOpacity={0.28}/><stop offset="100%" stopColor="#6677f4" stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e8eaf2"/><XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fill: "#8a8fa5", fontSize: 11 }}/><YAxis axisLine={false} tickLine={false} tick={{ fill: "#8a8fa5", fontSize: 11 }}/><Tooltip contentStyle={{ borderRadius: 10, border: "1px solid #e7e9f1", boxShadow: "0 10px 28px rgba(24,29,55,.12)" }}/><Area type="monotone" dataKey="runs" stroke="#6677f4" strokeWidth={2.5} fill="url(#relayFill)"/></AreaChart></ResponsiveContainer></div></article>
              <article className="panel queue"><div className="panel-head"><div><h2>Queue health</h2><p>Current task distribution</p></div><Activity size={18}/></div><div className="queue-ring"><div><strong>{dashboard ? Object.values(dashboard.queue).reduce((sum, value) => sum + value, 0) : 54}</strong><span>Total jobs</span></div></div><div className="queue-legend"><p><i className="queued"/>Queued <b>{dashboard?.queue.pending ?? 41}</b></p><p><i className="running"/>Running <b>{dashboard?.queue.running ?? 6}</b></p><p><i className="retry"/>Retrying <b>{dashboard?.queue.retrying ?? 5}</b></p><p><i className="dead"/>Dead letter <b>{dashboard?.queue.dead_letter ?? 2}</b></p></div></article>
            </div>
            <article className="panel graph-panel"><div className="panel-head"><div><h2>Live execution <span>#RF-5241</span></h2><p>Order fulfillment Â· started 38 seconds ago</p></div><button onClick={() => setView("runs")}>View details</button></div><div className="graph"><ReactFlow nodes={graphNodes} edges={graphEdges} nodeTypes={nodeTypes} fitView proOptions={{ hideAttribution: true }} nodesDraggable={false} nodesConnectable={false}><Background color="#dfe2ec" gap={18}/><Controls showInteractive={false}/></ReactFlow></div></article>
            <RunTable runs={visibleRuns} onSelect={setSelectedRun} />
          </>}

          {view === "workflows" && <div className="workflow-grid">{workflowList.map((workflow) => <article className="workflow-card" key={workflow.name}><div className="workflow-top"><span><GitBranch size={20}/></span><Status value={workflow.active ? "Active" : "Paused"}/><button><MoreHorizontal size={18}/></button></div><h2>{workflow.name}</h2><p>{workflow.description}</p><div className="workflow-stats"><span><b>{workflow.tasks}</b> tasks</span><span><b>{workflow.runs.toLocaleString()}</b> runs</span><span><b>{workflow.success}</b> success</span></div><button className="secondary" onClick={() => setBuilderOpen(true)}>Open workflow</button></article>)}</div>}
          {view === "runs" && <><div className="run-summary"><div><Clock3/><span><b>14.8s</b>Avg. duration</span></div><div><Boxes/><span><b>1,284</b>Runs today</span></div><div><CircleDot/><span><b>7</b>Retries</span></div><div><TerminalSquare/><span><b>2</b>Failed</span></div></div><RunTable runs={visibleRuns} onSelect={setSelectedRun}/></>}
          {view === "workers" && <article className="panel worker-table"><div className="panel-head"><div><h2>Execution nodes</h2><p>Heartbeats update every five seconds</p></div><button>Auto refresh</button></div>{displayWorkers.map((worker) => <div className="worker-row" key={worker.name}><div className="worker-name"><span className={`worker-dot ${worker.status.toLowerCase()}`}/><div><strong>{worker.name}</strong><small>distributed Â· python-3.12</small></div></div><Status value={worker.status}/><span><b>{worker.jobs}</b> jobs</span><div className="cpu"><span><i style={{width: `${worker.cpu}%`}}/></span>{worker.cpu}% CPU</div><small>{worker.heartbeat}</small><MoreHorizontal size={18}/></div>)}</article>}
          {view === "team" && <section className="team-view">
            <div className="team-summary"><article><Users/><div><strong>4</strong><span>Total members</span></div></article><article><ShieldCheck/><div><strong>1</strong><span>Administrator</span></div></article><article><Mail/><div><strong>1</strong><span>Pending invite</span></div></article><button className="primary" onClick={() => setInviteOpen(true)}><UserPlus size={17}/>Invite member</button></div>
            <article className="panel members-panel"><div className="panel-head"><div><h2>Workspace members</h2><p>People with access to {activeWorkspace.name}</p></div><div className="member-search"><Search size={15}/><input placeholder="Search members..."/></div></div><div className="member-row member-header"><span>Member</span><span>Role</span><span>Status</span><span>Last active</span><span/></div>{teamMembers.map((member, index) => <div className="member-row" key={member.email}><div className={`member-avatar avatar-${index}`}>{member.initials}</div><div className="member-identity"><strong>{member.name}</strong><small>{member.email}</small></div><select defaultValue={member.role} aria-label={`${member.name} role`}><option>Admin</option><option>Developer</option><option>Viewer</option></select><Status value={member.status}/><span>{member.status === "Invited" ? "â€”" : index === 0 ? "Now" : `${index * 3}h ago`}</span><button aria-label={`More options for ${member.name}`}><MoreHorizontal size={17}/></button></div>)}</article>
          </section>}
          {view === "settings" && <section className="settings-view">
            {saved && <div className="save-banner"><CircleCheck size={17}/>Settings saved successfully.<button onClick={() => setSaved(false)}><X size={15}/></button></div>}
            <article className="settings-card"><div className="settings-card-title"><div><Settings/><span><strong>General</strong><small>Workspace name and environment</small></span></div></div><div className="settings-fields"><label>Workspace name<input value={settings.workspaceName} onChange={(e) => setSettings({...settings, workspaceName: e.target.value})}/></label><label>Default environment<select defaultValue={activeWorkspace.environment}><option>Production</option><option>Staging</option><option>Development</option></select></label></div></article>
            <article className="settings-card"><div className="settings-card-title"><div><Database/><span><strong>Execution</strong><small>Workflow retention and retry defaults</small></span></div></div><div className="settings-fields"><label>Run history retention<select value={settings.retention} onChange={(e) => setSettings({...settings, retention: e.target.value})}><option value="7">7 days</option><option value="30">30 days</option><option value="90">90 days</option></select></label><label>Default maximum retries<input type="number" min="0" max="10" value={settings.maxRetries} onChange={(e) => setSettings({...settings, maxRetries: e.target.value})}/></label></div></article>
            <article className="settings-card"><div className="settings-card-title"><div><Bell/><span><strong>Notifications</strong><small>Choose which operational events notify your team</small></span></div></div><div className="toggle-row"><div><strong>System alerts</strong><span>Worker health and queue capacity warnings</span></div><button className={`toggle ${settings.alerts ? "on" : ""}`} onClick={() => setSettings({...settings, alerts: !settings.alerts})} aria-pressed={settings.alerts}><i/></button></div><div className="toggle-row"><div><strong>Failed workflow alerts</strong><span>Notify administrators when a run permanently fails</span></div><button className={`toggle ${settings.failedRunAlerts ? "on" : ""}`} onClick={() => setSettings({...settings, failedRunAlerts: !settings.failedRunAlerts})} aria-pressed={settings.failedRunAlerts}><i/></button></div></article>
            <div className="settings-actions"><button className="secondary" onClick={() => { setSettings({workspaceName: activeWorkspace.name, retention: "30", maxRetries: "3", alerts: true, failedRunAlerts: true}); setSaved(false); }}>Reset changes</button><button className="primary" onClick={() => { setActiveWorkspace({...activeWorkspace, name: settings.workspaceName}); setSaved(true); }}><CircleCheck size={17}/>Save settings</button></div>
          </section>}
        </div>
      </section>

      {builderOpen && <div className="modal-backdrop" onMouseDown={() => setBuilderOpen(false)}><section className="builder" onMouseDown={(e) => e.stopPropagation()}><div className="builder-head"><div><span className="builder-icon"><Workflow/></span><div><h2>Create workflow</h2><p>Build a durable task dependency graph</p></div></div><button onClick={() => setBuilderOpen(false)}><X/></button></div><label>Workflow name<input value={workflowName} onChange={(event) => setWorkflowName(event.target.value)} /></label><label>Description<textarea value={workflowDescription} onChange={(event) => setWorkflowDescription(event.target.value)} /></label><div className="task-label"><span>Tasks</span><button onClick={() => setTasks([...tasks, { name: "Notify team", dependency: tasks.at(-1)?.name || "None", action: "Webhook" }])}><Plus size={15}/>Add task</button></div><div className="task-list">{tasks.map((task, index) => <div className="task-item" key={`${task.name}-${index}`}><span className="step">{index + 1}</span><label>Name<input value={task.name} onChange={(e) => setTasks(tasks.map((t, i) => i === index ? {...t, name: e.target.value} : t))}/></label><label>Depends on<select value={task.dependency} onChange={(e) => setTasks(tasks.map((t, i) => i === index ? {...t, dependency: e.target.value} : t))}><option>None</option>{tasks.slice(0,index).map((t)=><option key={t.name}>{t.name}</option>)}</select></label><label>Action<select value={task.action} onChange={(e) => setTasks(tasks.map((t, i) => i === index ? {...t, action: e.target.value} : t))}><option>API call</option><option>Transform</option><option>Delay</option><option>Email</option><option>Webhook</option></select></label></div>)}</div><div className="builder-actions"><button className="secondary" onClick={() => setBuilderOpen(false)}>Cancel</button><button className="primary" onClick={createWorkflow}><CircleCheck size={17}/>Create workflow</button></div></section></div>}

      {selectedRun && <div className="drawer-backdrop" onClick={() => setSelectedRun(null)}><aside className="run-drawer" onClick={(e) => e.stopPropagation()}><div className="drawer-head"><div><small>Execution</small><h2>{selectedRun.id}</h2></div><button onClick={() => setSelectedRun(null)}><X/></button></div><div className="drawer-workflow"><Workflow/><div><strong>{selectedRun.workflow}</strong><span>Triggered by API Â· {selectedRun.time}</span></div><Status value={selectedRun.status}/></div><div className="detail-grid"><span>Duration<b>{selectedRun.duration}</b></span><span>Tasks<b>{selectedRun.tasks}</b></span><span>Worker<b>{selectedRun.worker}</b></span><span>Retries<b>{selectedRun.status === "Retrying" ? "1" : "0"}</b></span></div><h3>Live logs</h3><div className="logs"><p><time>10:02:01</time><span className="info">INFO</span>Run accepted by scheduler</p><p><time>10:02:02</time><span className="info">INFO</span>Task validate_order started</p><p><time>10:02:03</time><span className="good">DONE</span>Schema validation completed</p><p><time>10:02:04</time><span className="info">INFO</span>Inventory reservation started</p><p><time>10:02:08</time><span className="good">DONE</span>12 units reserved</p><p><time>10:02:09</time><span className="wait">WAIT</span>Processing payment...</p><span className="log-cursor"/></div></aside></div>}
      {inviteOpen && <div className="center-modal-backdrop" onMouseDown={() => setInviteOpen(false)}><section className="invite-modal" onMouseDown={(e) => e.stopPropagation()}><div className="builder-head"><div><span className="builder-icon"><UserPlus/></span><div><h2>Invite team member</h2><p>Add someone to {activeWorkspace.name}</p></div></div><button onClick={() => setInviteOpen(false)}><X/></button></div><label>Email address<input type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="teammate@company.com"/></label><label>Role<select defaultValue="Developer"><option>Admin</option><option>Developer</option><option>Viewer</option></select></label><div className="builder-actions"><button className="secondary" onClick={() => setInviteOpen(false)}>Cancel</button><button className="primary" disabled={!inviteEmail.includes("@")} onClick={() => { setInviteEmail(""); setInviteOpen(false); }}><Mail size={16}/>Send invitation</button></div></section></div>}
      {profileModal && <div className="center-modal-backdrop" onMouseDown={() => setProfileModal(false)}><section className="invite-modal profile-modal" onMouseDown={(e) => e.stopPropagation()}><div className="builder-head"><div><span className="profile-avatar large">SS</span><div><h2>Your profile</h2><p>Personal details shown across RelayFlow</p></div></div><button onClick={() => setProfileModal(false)}><X/></button></div><label>Display name<input value={displayName} onChange={(e) => setDisplayName(e.target.value)}/></label><label>Email address<input value="shaambhavi03@gmail.com" disabled/></label><label>Role<input value="Administrator" disabled/></label><div className="builder-actions"><button className="secondary" onClick={() => setProfileModal(false)}>Cancel</button><button className="primary" onClick={() => setProfileModal(false)}><CircleCheck size={16}/>Save profile</button></div></section></div>}
    </main>
  );
}

function RunTable({ runs, onSelect }: { runs: typeof recentRuns; onSelect: (run: (typeof recentRuns)[number]) => void }) {
  return <article className="panel runs"><div className="panel-head"><div><h2>Recent executions</h2><p>Latest workflow runs across your workspace</p></div><button>View all</button></div><div className="table"><div className="table-row table-header"><span>Run</span><span>Workflow</span><span>Status</span><span>Progress</span><span>Duration</span><span>Worker</span><span/></div>{runs.map((run) => <button className="table-row" key={run.id} onClick={() => onSelect(run)}><span><b>{run.id}</b><small>{run.time}</small></span><span>{run.workflow}</span><Status value={run.status}/><span>{run.tasks}</span><span>{run.duration}</span><span><code>{run.worker}</code></span><ChevronDown size={16}/></button>)}</div></article>;
}