import React, { useState, useEffect } from "react";
import axios from "axios";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, TrendingUp, MessageSquare, Trophy, Lock, Loader2, Check, Star, Flame, Sparkles } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const api = async (method, endpoint, data = null, token = null) => {
  const config = { method, url: `${API}${endpoint}`, headers: token ? { Authorization: `Bearer ${token}` } : {} };
  if (data) config.data = data;
  const res = await axios(config);
  return res.data;
};

const useToken = () => {
  const [token] = useState(() => localStorage.getItem("spark_token"));
  return token;
};

const PageShell = ({ title, subtitle, icon: Icon, children, testid, accent = "#FF2E63" }) => {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-white pb-16" data-testid={testid}>
      <div className="text-white border-b-4 border-black sticky top-0 z-30" style={{ background: accent }}>
        <div className="max-w-2xl mx-auto px-4 py-4 flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="p-1 hover:bg-white/10 rounded" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          {Icon && <Icon className="w-6 h-6" />}
          <div>
            <h1 className="font-black text-xl tracking-tight">{title}</h1>
            {subtitle && <p className="text-xs opacity-90">{subtitle}</p>}
          </div>
        </div>
      </div>
      <div className="max-w-2xl mx-auto px-4 py-6">{children}</div>
    </div>
  );
};

// ==================== c1. COMPATIBILITY TIMELINE ====================

const confidenceColor = (c) => c === "high" ? "bg-green-300" : c === "low" ? "bg-red-300" : "bg-yellow-300";

export const CompatibilityTimelinePage = () => {
  const token = useToken();
  const { matchId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try { setData(await api("get", `/match/${matchId}/timeline`, null, token)); }
      catch (e) { toast.error(e?.response?.data?.detail || "Couldn't load timeline"); }
      setLoading(false);
    })();
  }, [matchId, token]);

  if (loading) return <PageShell title="Compatibility Timeline" icon={TrendingUp} testid="timeline-loading"><Loader2 className="w-8 h-8 animate-spin text-[#FF2E63] mx-auto mt-12"/></PageShell>;
  if (!data) return <PageShell title="Compatibility Timeline" icon={TrendingUp} testid="timeline-empty"><p>No timeline yet.</p></PageShell>;

  return (
    <PageShell title="Compatibility Timeline" subtitle="Predicted milestones based on your DNA" icon={TrendingUp} testid="timeline-page">
      <p className="text-xs text-gray-500 mb-4" data-testid="timeline-disclaimer">
        AI prediction based on both profiles + Personality DNA. Every couple moves at their own pace — this is just a vibes guide.
      </p>
      <div className="relative pl-6 border-l-4 border-black" data-testid="milestone-list">
        {(data.milestones || []).map((m, i) => (
          <div key={i} className="relative mb-6" data-testid={`milestone-${i}`}>
            <div className="absolute -left-[34px] top-1 w-6 h-6 rounded-full border-4 border-black bg-[#FF2E63] flex items-center justify-center text-white text-xs font-black">
              {i + 1}
            </div>
            <div className="border-4 border-black p-4 shadow-[4px_4px_0_rgba(0,0,0,1)] bg-white">
              <div className="flex justify-between items-start gap-2">
                <p className="font-black text-lg leading-tight">{m.title}</p>
                <span className={`text-xs font-bold border-2 border-black px-2 py-0.5 ${confidenceColor(m.confidence)}`}>
                  {m.confidence}
                </span>
              </div>
              <p className="text-sm font-bold text-[#FF2E63] mt-1">{m.estimated_window}</p>
              <p className="text-sm text-gray-700 mt-2">{m.why}</p>
            </div>
          </div>
        ))}
      </div>
      {data.cached && <p className="text-xs text-gray-400 text-center" data-testid="cached-badge">Cached prediction (refreshes weekly)</p>}
    </PageShell>
  );
};

// ==================== c2. FIRST DATE SCRIPT ====================

export const FirstDateScriptPage = () => {
  const token = useToken();
  const { matchId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try { setData(await api("get", `/chat/${matchId}/first-date-script`, null, token)); }
      catch (e) { toast.error(e?.response?.data?.detail || "Couldn't load script"); }
      setLoading(false);
    })();
  }, [matchId, token]);

  if (loading) return <PageShell title="First Date Script" icon={MessageSquare} testid="script-loading"><Loader2 className="w-8 h-8 animate-spin text-[#FF2E63] mx-auto mt-12"/></PageShell>;

  if (!data?.unlocked) {
    return (
      <PageShell title="First Date Script" subtitle="AI conversation guide" icon={Lock} testid="script-locked">
        <div className="border-4 border-black p-6 bg-yellow-200 shadow-[6px_6px_0_rgba(0,0,0,1)] text-center" data-testid="locked-card">
          <Lock className="w-12 h-12 mx-auto mb-3" />
          <p className="font-black text-xl">Unlocks at 10 messages</p>
          <p className="text-sm mt-2">
            You've exchanged <b>{data?.messages_so_far ?? 0}</b> message{data?.messages_so_far === 1 ? "" : "s"} so far.
            <br />
            Send <b>{data?.messages_needed ?? 10}</b> more to unlock your personalised first-date guide.
          </p>
        </div>
      </PageShell>
    );
  }

  const s = data.script || {};
  const Section = ({ title, items, testid, render }) => (
    <div className="border-4 border-black p-4 mb-4 shadow-[4px_4px_0_rgba(0,0,0,1)]" data-testid={testid}>
      <p className="font-black mb-2">{title}</p>
      <ul className="space-y-2">
        {(items || []).map((it, i) => <li key={i} className="text-sm">{render ? render(it) : `• ${it}`}</li>)}
      </ul>
    </div>
  );

  return (
    <PageShell title="First Date Script" subtitle="Tailored to your conversation" icon={MessageSquare} testid="script-page">
      <div className="border-4 border-black p-4 mb-4 bg-[#FF2E63] text-white shadow-[4px_4px_0_rgba(0,0,0,1)]" data-testid="tone-card">
        <p className="text-xs font-bold uppercase tracking-wider">Tone</p>
        <p className="text-base font-bold mt-1">{s.tone}</p>
      </div>
      <Section title="Openers" items={s.openers} testid="openers-section" />
      <Section title="Go deeper" items={s.deeper_questions} testid="deeper-section" />
      <Section title="Topics to avoid (for now)" items={s.topics_to_avoid} testid="avoid-section" />
      <Section
        title="Where to go"
        items={s.venue_suggestions}
        testid="venues-section"
        render={(v) => (
          <div>
            <p className="font-bold">{v.name}</p>
            <p className="text-xs text-gray-600">{v.why}</p>
          </div>
        )}
      />
      {data.cached && <p className="text-xs text-gray-400 text-center mt-2" data-testid="cached-badge">Cached for 24h</p>}
    </PageShell>
  );
};

// ==================== c3. WEEKLY SPARK CHALLENGE ====================

const VERB_ROUTES = {
  open: "/matches",
  reignite: "/matches",
  verify_photo: "/verify/selfie",
  personality_dna: "/personality-dna",
  schedule_date: "/safety/post-date-checkin",
  icebreakers: "/extras",
  pledge: "/extras",
  wellness: "/wellness",
  growth_goals: "/extras",
  background_lite: "/verify/background",
  promise: "/promise",
  compliment: "/matches",
};

export const WeeklyChallengePage = () => {
  const token = useToken();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [board, setBoard] = useState(null);
  const [history, setHistory] = useState([]);
  const [tab, setTab] = useState("challenge");
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    try {
      const [w, b, h] = await Promise.all([
        api("get", "/challenges/weekly", null, token),
        api("get", "/challenges/leaderboard", null, token),
        api("get", "/challenges/history", null, token),
      ]);
      setData(w); setBoard(b); setHistory(h.completions || []);
    } catch { toast.error("Failed to load challenges"); }
  };
  useEffect(() => { if (token) load(); }, [token]);

  const completeNow = async () => {
    if (!data) return;
    setSubmitting(true);
    try {
      const res = await api("post", `/challenges/${data.challenge.id}/complete`, null, token);
      if (res.already_completed) toast.info("Already completed this week");
      else {
        toast.success(`+${res.xp_awarded} XP! ${(res.new_badges || []).length ? "🏆 " + res.new_badges.join(", ") : ""}`);
      }
      load();
    } catch { toast.error("Couldn't complete"); }
    setSubmitting(false);
  };

  const startChallenge = () => {
    if (!data) return;
    const dest = VERB_ROUTES[data.challenge.verb] || "/discover";
    navigate(dest);
  };

  if (!data) return <PageShell title="Spark Challenge" icon={Trophy} testid="challenge-loading"><Loader2 className="w-8 h-8 animate-spin text-[#FF2E63] mx-auto mt-12"/></PageShell>;

  const lvl = data.level_info || {};
  return (
    <PageShell title="Weekly Spark Challenge" subtitle="Earn XP, badges & climb the leaderboard" icon={Trophy} testid="challenge-page" accent="#7C3AED">
      {/* Tabs */}
      <div className="flex gap-2 mb-4" data-testid="tabs">
        {[
          { id: "challenge", label: "This Week" },
          { id: "leaderboard", label: "Leaderboard" },
          { id: "history", label: "History" },
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} className={`flex-1 py-2 border-4 border-black font-black text-sm ${tab === t.id ? "bg-black text-white" : "bg-white"}`} data-testid={`tab-${t.id}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* XP HUD always shown */}
      <div className="border-4 border-black p-4 mb-4 bg-yellow-300 shadow-[6px_6px_0_rgba(0,0,0,1)]" data-testid="xp-hud">
        <div className="flex items-baseline justify-between">
          <div>
            <p className="text-xs font-bold">LEVEL {lvl.level ?? 0}</p>
            <p className="text-2xl font-black">{data.xp ?? 0} XP</p>
          </div>
          <div className="text-right">
            <p className="text-xs font-bold flex items-center gap-1 justify-end"><Flame className="w-4 h-4"/>STREAK</p>
            <p className="text-2xl font-black">{data.streak_weeks ?? 0}w</p>
          </div>
        </div>
        <div className="mt-3 h-3 bg-white border-2 border-black">
          <div className="h-full bg-[#FF2E63]" style={{ width: `${Math.min(100, ((lvl.xp_in_level ?? 0) / Math.max(1, (lvl.xp_for_next ?? 100) - (lvl.xp_current - (lvl.xp_in_level ?? 0)))) * 100)}%` }} />
        </div>
        <p className="text-xs mt-1 font-bold">{lvl.xp_needed_for_next} XP to next level</p>
      </div>

      {tab === "challenge" && (
        <div className="border-4 border-black p-5 shadow-[6px_6px_0_rgba(0,0,0,1)] bg-white" data-testid="challenge-card">
          <p className="text-xs font-bold uppercase tracking-wider text-[#FF2E63]" data-testid="week-key">{data.week_key}</p>
          <p className="text-2xl font-black mt-1" data-testid="challenge-title">{data.challenge.title}</p>
          <p className="text-sm text-gray-700 mt-2" data-testid="challenge-desc">{data.challenge.description}</p>
          <div className="flex items-center gap-2 mt-3">
            <span className="text-xs font-black bg-[#FF2E63] text-white px-2 py-1 border-2 border-black" data-testid="xp-badge">+{data.challenge.xp} XP</span>
            {data.completed && <span className="text-xs font-black bg-green-300 px-2 py-1 border-2 border-black" data-testid="done-badge"><Check className="w-3 h-3 inline"/> Done</span>}
          </div>
          <div className="flex gap-2 mt-4">
            {!data.completed && (
              <>
                <button onClick={startChallenge} className="flex-1 py-3 bg-[#FF2E63] text-white font-black border-4 border-black shadow-[4px_4px_0_rgba(0,0,0,1)]" data-testid="start-challenge-btn">
                  {data.challenge.cta || "Start"}
                </button>
                <button onClick={completeNow} disabled={submitting} className="flex-1 py-3 bg-black text-white font-black border-4 border-black disabled:opacity-50" data-testid="complete-challenge-btn">
                  {submitting ? "..." : "I did it"}
                </button>
              </>
            )}
            {data.completed && (
              <p className="text-sm text-gray-600 text-center w-full" data-testid="completed-msg">Completed {new Date(data.completed_at).toLocaleDateString()}. New challenge unlocks Monday.</p>
            )}
          </div>
          {(data.badges || []).length > 0 && (
            <div className="mt-5 pt-4 border-t-2 border-black" data-testid="my-badges">
              <p className="font-black text-sm mb-2">Your badges</p>
              <div className="flex flex-wrap gap-2">
                {data.badges.map(b => (
                  <span key={b} className="text-xs font-bold border-2 border-black bg-yellow-200 px-2 py-1" data-testid={`badge-${b}`}>
                    <Star className="w-3 h-3 inline"/> {b}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "leaderboard" && board && (
        <div data-testid="leaderboard">
          {board.my_rank && (
            <div className="mb-3 p-3 border-4 border-black bg-[#FF2E63] text-white font-black flex justify-between" data-testid="my-rank">
              <span>Your rank</span>
              <span>#{board.my_rank} · {board.my_xp} XP</span>
            </div>
          )}
          <div className="space-y-2">
            {(board.leaderboard || []).length === 0 && <p className="text-center text-gray-500" data-testid="empty-board">Be the first to earn XP!</p>}
            {(board.leaderboard || []).map((u, i) => (
              <div key={u.id} className="border-4 border-black p-3 flex items-center gap-3" data-testid={`board-row-${i}`}>
                <p className="text-xl font-black w-8">#{i + 1}</p>
                {u.photo ? <img src={u.photo} alt="" className="w-10 h-10 border-2 border-black object-cover"/> : <div className="w-10 h-10 border-2 border-black bg-gray-200"/>}
                <div className="flex-1">
                  <p className="font-black text-sm">{u.name}</p>
                  <p className="text-xs text-gray-500">{u.streak_weeks}w streak · {u.badges_count} badges</p>
                </div>
                <p className="font-black text-[#FF2E63]">{u.xp} XP</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "history" && (
        <div className="space-y-2" data-testid="history-list">
          {history.length === 0 && <p className="text-center text-gray-500" data-testid="no-history">No challenges completed yet.</p>}
          {history.map(h => (
            <div key={h.id} className="border-4 border-black p-3 flex justify-between items-center" data-testid={`history-${h.id}`}>
              <div>
                <p className="font-black text-sm">{h.title || h.challenge_id}</p>
                <p className="text-xs text-gray-500">{new Date(h.completed_at).toLocaleDateString()} · {h.week_key}</p>
              </div>
              <span className="text-xs font-black bg-[#FF2E63] text-white px-2 py-1 border-2 border-black">+{h.xp_awarded} XP</span>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
};
