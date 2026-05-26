import React, { useState, useEffect } from "react";
import axios from "axios";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Brain, Shield, MapPin, Camera, FileCheck, Check, AlertCircle, Loader2 } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const api = async (method, endpoint, data = null, token = null) => {
  const config = { method, url: `${API}${endpoint}`, headers: token ? { Authorization: `Bearer ${token}` } : {} };
  if (data) config.data = data;
  const res = await axios(config);
  return res.data;
};

const useToken = () => {
  const [token, setToken] = useState(localStorage.getItem("spark_token"));
  useEffect(() => { setToken(localStorage.getItem("spark_token")); }, []);
  return token;
};

const PageShell = ({ title, subtitle, icon: Icon, children, testid }) => {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-white pb-16" data-testid={testid}>
      <div className="bg-[#FF2E63] text-white border-b-4 border-black sticky top-0 z-30">
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

// ==================== b1. PERSONALITY DNA ====================

export const PersonalityDNAPage = () => {
  const token = useToken();
  const navigate = useNavigate();
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [step, setStep] = useState(0);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [q, me] = await Promise.all([
          api("get", "/personality/questions"),
          token ? api("get", "/auth/me", null, token) : Promise.resolve({}),
        ]);
        setQuestions(q.questions);
        if (me.personality_complete) {
          setResult({ personality_dna: me.personality_dna, archetype: me.personality_archetype });
        }
      } catch { toast.error("Failed to load Personality DNA"); }
      setLoading(false);
    })();
  }, [token]);

  const pick = (qid, cid) => {
    setAnswers(prev => ({ ...prev, [qid]: cid }));
    if (step < questions.length - 1) setTimeout(() => setStep(step + 1), 200);
  };

  const submit = async () => {
    setSaving(true);
    try {
      const payload = { answers: questions.map(q => ({ question_id: q.id, choice_id: answers[q.id] })) };
      const res = await api("put", "/personality/dna", payload, token);
      setResult(res);
      toast.success(`Mapped! You're ${res.archetype}`);
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to save"); }
    setSaving(false);
  };

  if (loading) return <PageShell title="Personality DNA" icon={Brain} testid="personality-dna-loading"><div className="text-center py-12"><Loader2 className="w-8 h-8 mx-auto animate-spin text-[#FF2E63]"/></div></PageShell>;

  if (result) {
    const dna = result.personality_dna || {};
    const traits = [
      { key: "openness", label: "Openness", hint: "Curiosity & novelty-seeking" },
      { key: "conscientiousness", label: "Conscientiousness", hint: "Planning & reliability" },
      { key: "extraversion", label: "Extraversion", hint: "Social energy" },
      { key: "agreeableness", label: "Agreeableness", hint: "Warmth & cooperation" },
      { key: "neuroticism", label: "Neuroticism", hint: "Emotional reactivity" },
    ];
    return (
      <PageShell title="Your Personality DNA" subtitle="Affects 40% of your match score" icon={Brain} testid="personality-dna-result">
        <div className="bg-yellow-300 border-4 border-black p-6 shadow-[6px_6px_0_rgba(0,0,0,1)] mb-6" data-testid="archetype-card">
          <p className="text-xs font-bold uppercase tracking-wider">Your archetype</p>
          <p className="text-3xl font-black mt-1">{result.archetype}</p>
        </div>
        <div className="space-y-4">
          {traits.map(t => (
            <div key={t.key} className="border-4 border-black p-4" data-testid={`trait-${t.key}`}>
              <div className="flex items-baseline justify-between">
                <div>
                  <p className="font-black">{t.label}</p>
                  <p className="text-xs text-gray-600">{t.hint}</p>
                </div>
                <p className="text-2xl font-black text-[#FF2E63]" data-testid={`trait-${t.key}-score`}>{dna[t.key] ?? 50}</p>
              </div>
              <div className="mt-2 h-3 bg-gray-200 border-2 border-black">
                <div className="h-full bg-[#FF2E63]" style={{ width: `${dna[t.key] ?? 50}%` }} />
              </div>
            </div>
          ))}
        </div>
        <button onClick={() => { setResult(null); setStep(0); setAnswers({}); }} className="mt-6 w-full py-3 border-4 border-black font-black bg-white hover:bg-gray-100" data-testid="retake-personality-btn">
          Retake the test
        </button>
        <button onClick={() => navigate("/discover")} className="mt-3 w-full py-3 bg-[#FF2E63] text-white font-black border-4 border-black shadow-[6px_6px_0_rgba(0,0,0,1)]" data-testid="continue-from-dna-btn">
          Find smarter matches →
        </button>
      </PageShell>
    );
  }

  const q = questions[step];
  const all = Object.keys(answers).length === questions.length;
  return (
    <PageShell title="Personality DNA" subtitle={`Question ${step + 1} of ${questions.length}`} icon={Brain} testid="personality-dna-quiz">
      <div className="h-2 bg-gray-200 border-2 border-black mb-6">
        <div className="h-full bg-[#FF2E63] transition-all" style={{ width: `${((step + 1) / questions.length) * 100}%` }} data-testid="progress-bar" />
      </div>
      {q && (
        <div className="space-y-4">
          <p className="text-2xl font-black leading-tight" data-testid="question-text">{q.text}</p>
          {q.choices.map(c => (
            <button
              key={c.id}
              onClick={() => pick(q.id, c.id)}
              className={`w-full p-4 text-left border-4 border-black font-bold transition shadow-[4px_4px_0_rgba(0,0,0,1)] ${answers[q.id] === c.id ? "bg-[#FF2E63] text-white" : "bg-white hover:bg-gray-100"}`}
              data-testid={`choice-${q.id}-${c.id}`}
            >
              {c.text}
            </button>
          ))}
        </div>
      )}
      <div className="flex gap-2 mt-6">
        <button onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0} className="flex-1 py-3 border-4 border-black font-black bg-white disabled:opacity-50" data-testid="prev-question-btn">
          Back
        </button>
        {step < questions.length - 1 ? (
          <button onClick={() => setStep(Math.min(questions.length - 1, step + 1))} disabled={!answers[q?.id]} className="flex-1 py-3 bg-[#FF2E63] text-white font-black border-4 border-black shadow-[4px_4px_0_rgba(0,0,0,1)] disabled:opacity-50" data-testid="next-question-btn">
            Next
          </button>
        ) : (
          <button onClick={submit} disabled={!all || saving} className="flex-1 py-3 bg-black text-white font-black border-4 border-black shadow-[4px_4px_0_rgba(0,0,0,1)] disabled:opacity-50" data-testid="submit-personality-btn">
            {saving ? "Mapping..." : "Map my DNA"}
          </button>
        )}
      </div>
    </PageShell>
  );
};

// ==================== b2. POST-DATE CHECK-IN ====================

export const PostDateCheckinPage = () => {
  const token = useToken();
  const [checkins, setCheckins] = useState([]);
  const [matches, setMatches] = useState([]);
  const [form, setForm] = useState({ match_id: "", location: "", scheduled_time: "", grace_minutes: 120, notes: "" });
  const [me, setMe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const [list, m, meRes] = await Promise.all([
        api("get", "/safety/post-date-checkins", null, token),
        api("get", "/matches", null, token),
        api("get", "/auth/me", null, token),
      ]);
      setCheckins(list.checkins || []);
      setMatches(m.matches || []);
      setMe(meRes);
    } catch { toast.error("Failed to load check-ins"); }
    setLoading(false);
  };
  useEffect(() => { if (token) load(); }, [token]);

  const create = async () => {
    if (!form.match_id || !form.scheduled_time) { toast.error("Pick a match and time"); return; }
    setSaving(true);
    try {
      await api("post", "/safety/post-date-checkin", {
        match_id: form.match_id,
        location: form.location || null,
        scheduled_time: new Date(form.scheduled_time).toISOString(),
        grace_minutes: Number(form.grace_minutes) || 120,
        notes: form.notes || null,
      }, token);
      toast.success("Check-in scheduled. We'll alert your emergency contact if you don't confirm.");
      setForm({ match_id: "", location: "", scheduled_time: "", grace_minutes: 120, notes: "" });
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to schedule"); }
    setSaving(false);
  };

  const confirm = async (id) => {
    try { await api("post", `/safety/post-date-checkin/${id}/confirm`, null, token); toast.success("Glad you're safe 💛"); load(); }
    catch { toast.error("Couldn't confirm"); }
  };

  const snooze = async (id) => {
    try { await api("post", `/safety/post-date-checkin/${id}/snooze`, null, token); toast.success("+30 minutes"); load(); }
    catch { toast.error("Couldn't snooze"); }
  };

  const hasContact = me && (me.emergency_contact_email || me.emergency_contact_phone);

  return (
    <PageShell title="Post-Date Check-in" subtitle="Auto-alerts your trusted contact" icon={Shield} testid="post-date-checkin-page">
      {!hasContact && (
        <div className="bg-yellow-300 border-4 border-black p-4 mb-6 flex gap-3" data-testid="no-contact-warning">
          <AlertCircle className="w-6 h-6 shrink-0" />
          <div>
            <p className="font-black">Add an emergency contact first</p>
            <p className="text-sm">Go to <a href="/safety" className="underline font-bold">Safety Settings</a> to add their email or phone.</p>
          </div>
        </div>
      )}

      <div className="border-4 border-black p-5 mb-6 shadow-[6px_6px_0_rgba(0,0,0,1)] bg-white" data-testid="schedule-form">
        <p className="font-black text-lg mb-4">Schedule a check-in</p>
        <label className="block text-xs font-bold mb-1">Match</label>
        <select value={form.match_id} onChange={e => setForm({ ...form, match_id: e.target.value })} className="w-full p-3 border-4 border-black font-bold mb-3" data-testid="match-select">
          <option value="">Choose a match…</option>
          {matches.map(m => (<option key={m.match_id} value={m.match_id}>{m.profile?.name || "Match"}</option>))}
        </select>
        <label className="block text-xs font-bold mb-1">Date & time</label>
        <input type="datetime-local" value={form.scheduled_time} onChange={e => setForm({ ...form, scheduled_time: e.target.value })} className="w-full p-3 border-4 border-black font-bold mb-3" data-testid="datetime-input" />
        <label className="block text-xs font-bold mb-1">Location (optional)</label>
        <input type="text" placeholder="Coffee at Central Park" value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} className="w-full p-3 border-4 border-black mb-3" data-testid="location-input" />
        <label className="block text-xs font-bold mb-1">Grace period (minutes after end time)</label>
        <input type="number" min="15" max="720" value={form.grace_minutes} onChange={e => setForm({ ...form, grace_minutes: e.target.value })} className="w-full p-3 border-4 border-black mb-3" data-testid="grace-input" />
        <label className="block text-xs font-bold mb-1">Notes (optional)</label>
        <textarea rows="2" placeholder="Their first name and any details for your contact" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} className="w-full p-3 border-4 border-black mb-3" data-testid="notes-input" />
        <button onClick={create} disabled={saving || !hasContact} className="w-full py-3 bg-[#FF2E63] text-white font-black border-4 border-black shadow-[4px_4px_0_rgba(0,0,0,1)] disabled:opacity-50" data-testid="create-checkin-btn">
          {saving ? "Scheduling..." : "Schedule check-in"}
        </button>
      </div>

      <p className="font-black text-lg mb-3">Your check-ins</p>
      {loading ? <Loader2 className="w-6 h-6 animate-spin"/> : checkins.length === 0 ? (
        <p className="text-gray-500" data-testid="no-checkins">No check-ins yet.</p>
      ) : (
        <div className="space-y-3">
          {checkins.map(c => (
            <div key={c.id} className="border-4 border-black p-4" data-testid={`checkin-${c.id}`}>
              <div className="flex justify-between items-start">
                <div>
                  <p className="font-black">{c.location || "Date check-in"}</p>
                  <p className="text-xs text-gray-600">Scheduled: {new Date(c.scheduled_time).toLocaleString()}</p>
                  <p className="text-xs text-gray-600">Auto-alert at: {new Date(c.auto_notify_at).toLocaleString()}</p>
                </div>
                <span className={`text-xs font-black px-2 py-1 border-2 border-black ${c.status === "confirmed_safe" ? "bg-green-300" : c.status === "alerted" ? "bg-red-300" : "bg-yellow-300"}`}>{c.status}</span>
              </div>
              {c.status === "scheduled" && (
                <div className="flex gap-2 mt-3">
                  <button onClick={() => confirm(c.id)} className="flex-1 py-2 bg-green-400 border-2 border-black font-bold" data-testid={`confirm-${c.id}`}>I'm safe ✓</button>
                  <button onClick={() => snooze(c.id)} className="flex-1 py-2 bg-white border-2 border-black font-bold" data-testid={`snooze-${c.id}`}>+30 min</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
};

// ==================== b3. SAFE MEETING ZONES ====================

export const SafeZonesPage = () => {
  const token = useToken();
  const [zones, setZones] = useState([]);
  const [guidance, setGuidance] = useState([]);
  const [city, setCity] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async (cityParam = "") => {
    setLoading(true);
    try {
      const res = await api("get", `/safety/zones${cityParam ? `?city=${encodeURIComponent(cityParam)}` : ""}`, null, token);
      setZones(res.zones || []);
      setGuidance(res.guidance || []);
    } catch { toast.error("Failed to load safe zones"); }
    setLoading(false);
  };
  useEffect(() => { if (token) load(); }, [token]);

  return (
    <PageShell title="Safe Meeting Zones" subtitle="Verified public spots for first dates" icon={MapPin} testid="safe-zones-page">
      <div className="bg-yellow-300 border-4 border-black p-4 mb-6" data-testid="safety-guidance">
        <p className="font-black mb-2">First-date safety guidance</p>
        <ul className="text-sm space-y-1 list-disc list-inside">
          {guidance.map((g, i) => <li key={i}>{g}</li>)}
        </ul>
      </div>
      <div className="flex gap-2 mb-4">
        <input type="text" placeholder="Your city (e.g. Austin)" value={city} onChange={e => setCity(e.target.value)} className="flex-1 p-3 border-4 border-black" data-testid="city-input" />
        <button onClick={() => load(city)} className="px-4 py-3 bg-[#FF2E63] text-white font-black border-4 border-black" data-testid="find-zones-btn">Find</button>
      </div>
      {loading ? <Loader2 className="w-6 h-6 animate-spin"/> : (
        <div className="space-y-3" data-testid="zones-list">
          {zones.map(z => (
            <div key={z.id} className="border-4 border-black p-4" data-testid={`zone-${z.id}`}>
              <div className="flex justify-between">
                <p className="font-black">{z.name}{z.city ? ` · ${z.city}` : ""}</p>
                <span className="text-xs font-bold bg-green-300 px-2 py-0.5 border-2 border-black">★ {z.safety_rating}/5</span>
              </div>
              <p className="text-xs text-gray-600 mt-1 capitalize">{z.category}</p>
              <p className="text-sm mt-2">{z.tips}</p>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
};

export const LiveLocationSharePage = () => {
  const token = useToken();
  const { matchId } = useParams();
  const [sharing, setSharing] = useState(false);
  const [partnerShare, setPartnerShare] = useState(null);
  const [duration, setDuration] = useState(60);
  const [loading, setLoading] = useState(false);
  const [watchId, setWatchId] = useState(null);

  const pollPartner = async () => {
    try {
      const res = await api("get", `/safety/share-location/${matchId}`, null, token);
      setPartnerShare(res.sharing ? res : null);
    } catch {}
  };
  useEffect(() => { if (token && matchId) { pollPartner(); const i = setInterval(pollPartner, 15000); return () => clearInterval(i); } }, [token, matchId]);

  const startSharing = () => {
    if (!navigator.geolocation) { toast.error("Geolocation not supported"); return; }
    setLoading(true);
    const id = navigator.geolocation.watchPosition(async (pos) => {
      try {
        await api("post", "/safety/share-location", {
          match_id: matchId,
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          duration_minutes: Number(duration),
        }, token);
        setSharing(true);
        setLoading(false);
      } catch { toast.error("Failed to share location"); setLoading(false); }
    }, () => { toast.error("Couldn't get location"); setLoading(false); });
    setWatchId(id);
  };

  const stopSharing = async () => {
    if (watchId !== null) navigator.geolocation.clearWatch(watchId);
    setWatchId(null);
    try { await api("delete", `/safety/share-location/${matchId}`, null, token); setSharing(false); toast.success("Stopped sharing"); }
    catch { toast.error("Failed to stop"); }
  };

  return (
    <PageShell title="Live Location" subtitle="Share with this match for safety" icon={MapPin} testid="live-location-page">
      <div className="border-4 border-black p-5 mb-4 shadow-[6px_6px_0_rgba(0,0,0,1)]" data-testid="my-sharing-card">
        <p className="font-black text-lg mb-2">Your location</p>
        {sharing ? (
          <>
            <p className="text-sm text-green-700 font-bold">● Sharing live ({duration} min)</p>
            <button onClick={stopSharing} className="mt-3 w-full py-2 bg-red-400 border-4 border-black font-black" data-testid="stop-sharing-btn">Stop sharing</button>
          </>
        ) : (
          <>
            <label className="block text-xs font-bold mb-1">Share for (minutes)</label>
            <input type="number" min="15" max="240" value={duration} onChange={e => setDuration(e.target.value)} className="w-full p-2 border-4 border-black mb-3" data-testid="duration-input" />
            <button onClick={startSharing} disabled={loading} className="w-full py-3 bg-[#FF2E63] text-white font-black border-4 border-black shadow-[4px_4px_0_rgba(0,0,0,1)] disabled:opacity-50" data-testid="start-sharing-btn">
              {loading ? "Starting…" : "Start sharing my location"}
            </button>
          </>
        )}
      </div>
      <div className="border-4 border-black p-5" data-testid="partner-sharing-card">
        <p className="font-black text-lg mb-2">Match's location</p>
        {partnerShare ? (
          <div>
            <p className="text-sm">📍 {partnerShare.latitude?.toFixed(5)}, {partnerShare.longitude?.toFixed(5)}</p>
            <p className="text-xs text-gray-600">Until {new Date(partnerShare.expires_at).toLocaleTimeString()}</p>
            <a href={`https://www.google.com/maps/search/?api=1&query=${partnerShare.latitude},${partnerShare.longitude}`} target="_blank" rel="noreferrer" className="mt-2 inline-block underline font-bold text-[#FF2E63]" data-testid="open-map-link">Open in Maps</a>
          </div>
        ) : (
          <p className="text-sm text-gray-500" data-testid="partner-not-sharing">Not sharing right now.</p>
        )}
      </div>
    </PageShell>
  );
};

// ==================== b4. VERIFIED PHOTO BADGE (SELFIE) ====================

export const SelfieVerifyPage = () => {
  const token = useToken();
  const navigate = useNavigate();
  const [stream, setStream] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const videoRef = React.useRef(null);

  const start = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } });
      setStream(s);
      if (videoRef.current) { videoRef.current.srcObject = s; }
    } catch { toast.error("Camera permission denied"); }
  };

  const capture = () => {
    const v = videoRef.current;
    if (!v) return;
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth || 480;
    canvas.height = v.videoHeight || 480;
    canvas.getContext("2d").drawImage(v, 0, 0, canvas.width, canvas.height);
    const data = canvas.toDataURL("image/jpeg", 0.7);
    setSnapshot(data);
    if (stream) { stream.getTracks().forEach(t => t.stop()); setStream(null); }
  };

  const submit = async () => {
    if (!snapshot) return;
    setSubmitting(true);
    try {
      const res = await api("post", "/profile/selfie-verify", { selfie_data_url: snapshot }, token);
      setResult(res);
      if (res.verified) toast.success("Photo Verified ✓");
      else toast.error("We couldn't verify — try a clearer, well-lit selfie");
    } catch (e) { toast.error(e?.response?.data?.detail || "Verification failed"); }
    setSubmitting(false);
  };

  return (
    <PageShell title="Verified Photo Badge" subtitle="Quick selfie match for trust" icon={Camera} testid="selfie-verify-page">
      <div className="border-4 border-black p-5 shadow-[6px_6px_0_rgba(0,0,0,1)]">
        {!snapshot && !stream && (
          <>
            <p className="font-black mb-2">How it works</p>
            <ol className="text-sm list-decimal list-inside mb-4 space-y-1">
              <li>Snap a quick selfie (front camera)</li>
              <li>We compare it with your primary profile photo</li>
              <li>If they match, you earn the <b>Photo Verified ✓</b> badge</li>
            </ol>
            <button onClick={start} className="w-full py-3 bg-[#FF2E63] text-white font-black border-4 border-black shadow-[4px_4px_0_rgba(0,0,0,1)]" data-testid="start-camera-btn">
              Start camera
            </button>
          </>
        )}
        {stream && !snapshot && (
          <div>
            <video ref={videoRef} autoPlay playsInline className="w-full border-4 border-black mb-3" data-testid="selfie-video" />
            <button onClick={capture} className="w-full py-3 bg-black text-white font-black border-4 border-black" data-testid="capture-selfie-btn">Capture selfie</button>
          </div>
        )}
        {snapshot && !result && (
          <div>
            <img src={snapshot} alt="Selfie preview" className="w-full border-4 border-black mb-3" data-testid="selfie-preview" />
            <div className="flex gap-2">
              <button onClick={() => { setSnapshot(null); start(); }} className="flex-1 py-3 border-4 border-black font-black bg-white" data-testid="retake-selfie-btn">Retake</button>
              <button onClick={submit} disabled={submitting} className="flex-1 py-3 bg-[#FF2E63] text-white font-black border-4 border-black disabled:opacity-50" data-testid="submit-selfie-btn">
                {submitting ? "Verifying…" : "Verify"}
              </button>
            </div>
          </div>
        )}
        {result && (
          <div className="text-center" data-testid="verify-result">
            {result.verified ? (
              <>
                <Check className="w-16 h-16 mx-auto text-green-600 mb-2" />
                <p className="font-black text-2xl">Photo Verified ✓</p>
                <p className="text-sm text-gray-600">Confidence: {result.confidence}%</p>
              </>
            ) : (
              <>
                <AlertCircle className="w-16 h-16 mx-auto text-red-500 mb-2" />
                <p className="font-black text-xl">Not verified</p>
                <p className="text-sm text-gray-600">{result.reason}</p>
                <button onClick={() => { setResult(null); setSnapshot(null); start(); }} className="mt-3 px-4 py-2 border-4 border-black font-black" data-testid="try-again-btn">Try again</button>
              </>
            )}
            <button onClick={() => navigate("/profile")} className="mt-4 w-full py-3 bg-black text-white font-black border-4 border-black" data-testid="done-verify-btn">Done</button>
          </div>
        )}
      </div>
    </PageShell>
  );
};

// ==================== b5. BACKGROUND LITE CHECK ====================

export const BackgroundLitePage = () => {
  const token = useToken();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [form, setForm] = useState({ full_legal_name: "", date_of_birth: "", country: "US", id_last4: "" });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { (async () => { try { setMe(await api("get", "/auth/me", null, token)); } catch {} })(); }, [token]);

  const submit = async () => {
    if (!form.full_legal_name || !form.date_of_birth || !form.country) { toast.error("Fill required fields"); return; }
    setSubmitting(true);
    try {
      await api("post", "/profile/background-lite", form, token);
      toast.success("Background Lite ✓ unlocked");
      const fresh = await api("get", "/auth/me", null, token);
      setMe(fresh);
    } catch (e) { toast.error(e?.response?.data?.detail || "Verification failed"); }
    setSubmitting(false);
  };

  const verified = me?.background_lite_verified;

  return (
    <PageShell title="Background Lite Check" subtitle="Show daters you're who you say you are" icon={FileCheck} testid="background-lite-page">
      {verified ? (
        <div className="border-4 border-black p-6 bg-green-300 shadow-[6px_6px_0_rgba(0,0,0,1)]" data-testid="bg-verified-state">
          <Check className="w-12 h-12 mx-auto mb-2" />
          <p className="font-black text-2xl text-center">Background Lite ✓</p>
          <p className="text-sm text-center mt-1">Verified on {new Date(me.background_lite_verified_at).toLocaleDateString()}</p>
          <p className="text-xs text-center mt-3">Your name and DOB were attested. We store only a one-way hash — never plaintext.</p>
          <button onClick={() => navigate("/profile")} className="mt-4 w-full py-3 bg-black text-white font-black border-4 border-black" data-testid="bg-done-btn">Done</button>
        </div>
      ) : (
        <div className="border-4 border-black p-5 shadow-[6px_6px_0_rgba(0,0,0,1)]" data-testid="bg-form">
          <p className="font-black text-lg mb-1">Lite identity attestation</p>
          <p className="text-xs text-gray-600 mb-4">We store a one-way hash of your details — never plaintext. Earn a "Background Lite ✓" badge on your profile.</p>
          <label className="block text-xs font-bold mb-1">Full legal name</label>
          <input type="text" value={form.full_legal_name} onChange={e => setForm({ ...form, full_legal_name: e.target.value })} className="w-full p-3 border-4 border-black mb-3" data-testid="legal-name-input" />
          <label className="block text-xs font-bold mb-1">Date of birth</label>
          <input type="date" value={form.date_of_birth} onChange={e => setForm({ ...form, date_of_birth: e.target.value })} className="w-full p-3 border-4 border-black mb-3" data-testid="dob-input" />
          <label className="block text-xs font-bold mb-1">Country (2-letter code)</label>
          <input type="text" maxLength="2" value={form.country} onChange={e => setForm({ ...form, country: e.target.value.toUpperCase() })} className="w-full p-3 border-4 border-black mb-3" data-testid="country-input" />
          <label className="block text-xs font-bold mb-1">Last 4 of any government ID (optional)</label>
          <input type="text" maxLength="4" value={form.id_last4} onChange={e => setForm({ ...form, id_last4: e.target.value })} className="w-full p-3 border-4 border-black mb-3" data-testid="id-last4-input" />
          <button onClick={submit} disabled={submitting} className="w-full py-3 bg-[#FF2E63] text-white font-black border-4 border-black shadow-[4px_4px_0_rgba(0,0,0,1)] disabled:opacity-50" data-testid="submit-bg-btn">
            {submitting ? "Verifying…" : "Attest & verify"}
          </button>
        </div>
      )}
    </PageShell>
  );
};
