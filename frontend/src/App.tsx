import { NavLink, Route, Routes } from "react-router-dom";
import clsx from "clsx";
import Dashboard from "@/pages/Dashboard";
import DigitalTwin from "@/pages/DigitalTwin";
import ScenarioRun from "@/pages/ScenarioRun";
import Sourcing from "@/pages/Sourcing";
import SPR from "@/pages/SPR";

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
}

const NAV: NavItem[] = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/twin", label: "Digital Twin" },
  { to: "/scenarios/hormuz-closure", label: "Scenarios" },
  { to: "/sourcing", label: "Sourcing" },
  { to: "/spr", label: "Strategic Reserves" },
];

function Sidebar() {
  return (
    <aside className="w-60 shrink-0 border-r border-border-soft bg-panel">
      <div className="px-5 py-5 border-b border-border-soft">
        <div className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
          ET AI Hackathon
        </div>
        <div className="mt-1 text-sm font-semibold text-slate-100">PS2 Console</div>
      </div>
      <nav className="px-2 py-3 flex flex-col gap-0.5">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              clsx(
                "px-3 py-2 rounded-md text-sm transition-colors",
                isActive
                  ? "bg-panel-2 text-slate-100 ring-1 ring-border-soft"
                  : "text-slate-400 hover:text-slate-200 hover:bg-panel-2/60",
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto px-5 py-4 text-[11px] text-slate-500">
        Build 0.1.0 - 2026
      </div>
    </aside>
  );
}

function Header() {
  return (
    <header className="h-14 shrink-0 flex items-center justify-between px-6 border-b border-border-soft bg-panel/80 backdrop-blur">
      <div className="flex items-center gap-3">
        <div className="h-6 w-6 rounded bg-accent/15 ring-1 ring-accent/40 grid place-items-center">
          <div className="h-2 w-2 rounded-sm bg-accent" />
        </div>
        <h1 className="text-sm font-semibold tracking-wide text-slate-100">
          Energy Supply Chain Resilience
        </h1>
      </div>
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full rounded-full bg-good opacity-60 animate-ping" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-good" />
        </span>
        <span>live</span>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <div className="min-h-screen flex bg-canvas text-slate-100">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-auto p-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/twin" element={<DigitalTwin />} />
            <Route path="/scenarios/:name" element={<ScenarioRun />} />
            <Route path="/sourcing" element={<Sourcing />} />
            <Route path="/spr" element={<SPR />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
