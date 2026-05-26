import React, { useState, useEffect } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Sliders, Crown, Lock, Check, X, Loader2 } from "lucide-react";

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

const ToggleChip = ({ label, active, onClick, disabled, testid }) => (
  <button
    onClick={onClick}
    disabled={disabled}
    className={`px-3 py-1.5 border-2 border-black text-sm font-bold transition disabled:opacity-50 ${active ? "bg-[#FF2E63] text-white" : "bg-white text-black hover:bg-gray-100"}`}
    data-testid={testid}
  >
    {label}
  </button>
);

const MultiSelect = ({ title, options, values, onChange, locked, testidPrefix }) => (
  <div className="mb-5" data-testid={`section-${testidPrefix}`}>
    <p className="font-black mb-2 flex items-center gap-2">
      {title}
      {locked && <Lock className="w-3 h-3 text-gray-400" />}
    </p>
    <div className="flex flex-wrap gap-2">
      {(options || []).map((o) => {
        const isOn = (values || []).includes(o.value);
        return (
          <ToggleChip
            key={o.value}
            label={o.label}
            active={isOn}
            disabled={locked}
            onClick={() => onChange(isOn ? values.filter((v) => v !== o.value) : [...(values || []), o.value])}
            testid={`${testidPrefix}-${o.value}`}
          />
        );
      })}
    </div>
  </div>
);

const NumRange = ({ title, minVal, maxVal, onMinChange, onMaxChange, min = 0, max = 100, step = 1, suffix = "", locked, testidPrefix }) => (
  <div className="mb-5" data-testid={`section-${testidPrefix}`}>
    <p className="font-black mb-2 flex items-center gap-2">
      {title}
      {locked && <Lock className="w-3 h-3 text-gray-400" />}
    </p>
    <div className="flex items-center gap-3">
      <input
        type="number"
        value={minVal ?? ""}
        onChange={(e) => onMinChange(e.target.value === "" ? null : Math.max(min, Math.min(max, Number(e.target.value))))}
        min={min}
        max={max}
        step={step}
        disabled={locked}
        placeholder="min"
        className="flex-1 p-2 border-4 border-black font-bold disabled:opacity-50"
        data-testid={`${testidPrefix}-min`}
      />
      <span className="font-bold">to</span>
      <input
        type="number"
        value={maxVal ?? ""}
        onChange={(e) => onMaxChange(e.target.value === "" ? null : Math.max(min, Math.min(max, Number(e.target.value))))}
        min={min}
        max={max}
        step={step}
        disabled={locked}
        placeholder="max"
        className="flex-1 p-2 border-4 border-black font-bold disabled:opacity-50"
        data-testid={`${testidPrefix}-max`}
      />
      {suffix && <span className="text-sm text-gray-600 font-bold">{suffix}</span>}
    </div>
  </div>
);

export const FiltersPage = () => {
  const token = useToken();
  const navigate = useNavigate();
  const [filters, setFilters] = useState({});
  const [options, setOptions] = useState({});
  const [isPremium, setIsPremium] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [distanceUnit, setDistanceUnit] = useState("mi");

  useEffect(() => {
    (async () => {
      try {
        const [opts, mine, me] = await Promise.all([
          api("get", "/options/profile-fields"),
          api("get", "/me/filters", null, token),
          api("get", "/auth/me", null, token),
        ]);
        setOptions(opts.filter_options || {});
        setFilters(mine.filters || {});
        setIsPremium(mine.is_premium);
        setDistanceUnit(me.distance_unit || "mi");
      } catch (e) {
        toast.error("Failed to load filters");
      }
      setLoading(false);
    })();
  }, [token]);

  const update = (key, value) => setFilters((p) => ({ ...p, [key]: value }));

  const save = async () => {
    setSaving(true);
    try {
      // Strip nulls and empty arrays before sending
      const payload = {};
      Object.entries(filters).forEach(([k, v]) => {
        if (v === null || v === undefined) return;
        if (Array.isArray(v) && v.length === 0) return;
        payload[k] = v;
      });
      const res = await api("put", "/me/filters", payload, token);
      setFilters(res.filters);
      toast.success("Filters saved");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Couldn't save filters");
    }
    setSaving(false);
  };

  const clearAll = async () => {
    try {
      await api("delete", "/me/filters", null, token);
      setFilters({});
      toast.success("Filters cleared");
    } catch {
      toast.error("Couldn't clear filters");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-white" data-testid="filters-loading">
        <div className="max-w-2xl mx-auto px-4 py-12 text-center">
          <Loader2 className="w-8 h-8 animate-spin text-[#FF2E63] mx-auto" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white pb-24" data-testid="filters-page">
      <div className="bg-[#FF2E63] text-white border-b-4 border-black sticky top-0 z-30">
        <div className="max-w-2xl mx-auto px-4 py-4 flex items-center gap-3">
          <button onClick={() => navigate(-1)} className="p-1 hover:bg-white/10 rounded" data-testid="back-btn">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <Sliders className="w-6 h-6" />
          <div className="flex-1">
            <h1 className="font-black text-xl tracking-tight">Advanced Filters</h1>
            <p className="text-xs opacity-90">{isPremium ? "All filters unlocked ⚡" : "Basic filters — upgrade for advanced"}</p>
          </div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-6">
        {/* Basics */}
        <div className="border-4 border-black p-4 mb-6 shadow-[6px_6px_0_rgba(0,0,0,1)]" data-testid="basics-card">
          <p className="font-black text-lg mb-3">Basics — free</p>
          <NumRange
            title="Age range"
            minVal={filters.age_min}
            maxVal={filters.age_max}
            onMinChange={(v) => update("age_min", v)}
            onMaxChange={(v) => update("age_max", v)}
            min={18}
            max={120}
            testidPrefix="age"
          />
          <NumRange
            title={`Max distance (${distanceUnit})`}
            minVal={null}
            maxVal={filters.distance_max}
            onMinChange={() => {}}
            onMaxChange={(v) => update("distance_max", v)}
            min={1}
            max={500}
            testidPrefix="distance"
          />
          <div className="flex items-center gap-2 mt-2">
            <input
              type="checkbox"
              id="recently-active"
              checked={!!filters.recently_active_only}
              onChange={(e) => update("recently_active_only", e.target.checked)}
              className="w-5 h-5 border-2 border-black"
              data-testid="recently-active-toggle"
            />
            <label htmlFor="recently-active" className="font-bold cursor-pointer">Only show profiles active in last 24h</label>
          </div>
        </div>

        {/* Premium gate banner */}
        {!isPremium && (
          <div className="border-4 border-black p-4 mb-6 bg-yellow-300" data-testid="premium-gate">
            <p className="font-black flex items-center gap-2"><Crown className="w-5 h-5"/> Unlock advanced filters</p>
            <p className="text-sm mt-1">Height, education, drinking, religion, kids and more — fine-tune to who you actually want to meet.</p>
            <button onClick={() => navigate("/subscription")} className="mt-3 w-full py-2 bg-black text-white font-black border-4 border-black" data-testid="upgrade-from-filters-btn">
              See Premium
            </button>
          </div>
        )}

        {/* Premium filters */}
        <div className={`border-4 border-black p-4 mb-6 shadow-[6px_6px_0_rgba(0,0,0,1)] ${!isPremium ? "opacity-60" : ""}`} data-testid="advanced-card">
          <p className="font-black text-lg mb-3 flex items-center gap-2">
            Advanced
            {!isPremium && <span className="text-xs font-bold bg-yellow-300 px-2 py-0.5 border-2 border-black">PREMIUM</span>}
          </p>

          <NumRange
            title="Height (cm)"
            minVal={filters.height_cm_min}
            maxVal={filters.height_cm_max}
            onMinChange={(v) => update("height_cm_min", v)}
            onMaxChange={(v) => update("height_cm_max", v)}
            min={120}
            max={230}
            locked={!isPremium}
            testidPrefix="height"
          />

          <MultiSelect title="Education" options={options.education} values={filters.education} onChange={(v) => update("education", v)} locked={!isPremium} testidPrefix="education" />
          <MultiSelect title="Body type" options={options.body_type} values={filters.body_type} onChange={(v) => update("body_type", v)} locked={!isPremium} testidPrefix="body-type" />
          <MultiSelect title="Drinking" options={options.drinking} values={filters.drinking} onChange={(v) => update("drinking", v)} locked={!isPremium} testidPrefix="drinking" />
          <MultiSelect title="Smoking" options={options.smoking} values={filters.smoking} onChange={(v) => update("smoking", v)} locked={!isPremium} testidPrefix="smoking" />
          <MultiSelect title="Cannabis" options={options.cannabis} values={filters.cannabis} onChange={(v) => update("cannabis", v)} locked={!isPremium} testidPrefix="cannabis" />
          <MultiSelect title="Religion" options={options.religion} values={filters.religion} onChange={(v) => update("religion", v)} locked={!isPremium} testidPrefix="religion" />
          <MultiSelect title="Politics" options={options.politics} values={filters.politics} onChange={(v) => update("politics", v)} locked={!isPremium} testidPrefix="politics" />
          <MultiSelect title="Has kids" options={options.has_kids} values={filters.has_kids} onChange={(v) => update("has_kids", v)} locked={!isPremium} testidPrefix="has-kids" />
          <MultiSelect title="Wants kids" options={options.wants_kids} values={filters.wants_kids} onChange={(v) => update("wants_kids", v)} locked={!isPremium} testidPrefix="wants-kids" />
          <MultiSelect title="Exercise" options={options.exercise} values={filters.exercise} onChange={(v) => update("exercise", v)} locked={!isPremium} testidPrefix="exercise" />
          <MultiSelect title="Pets" options={options.pets} values={filters.pets} onChange={(v) => update("pets", v)} locked={!isPremium} testidPrefix="pets" />

          <div className="flex items-center gap-2 mt-3">
            <input
              type="checkbox"
              id="must-verified"
              checked={!!filters.must_be_verified}
              disabled={!isPremium}
              onChange={(e) => update("must_be_verified", e.target.checked)}
              className="w-5 h-5 border-2 border-black disabled:opacity-50"
              data-testid="must-verified-toggle"
            />
            <label htmlFor="must-verified" className={`font-bold cursor-pointer ${!isPremium ? "opacity-50" : ""}`}>Verified photos only</label>
          </div>
          <div className="flex items-center gap-2 mt-2">
            <input
              type="checkbox"
              id="must-dna"
              checked={!!filters.must_have_personality_dna}
              disabled={!isPremium}
              onChange={(e) => update("must_have_personality_dna", e.target.checked)}
              className="w-5 h-5 border-2 border-black disabled:opacity-50"
              data-testid="must-dna-toggle"
            />
            <label htmlFor="must-dna" className={`font-bold cursor-pointer ${!isPremium ? "opacity-50" : ""}`}>Has Personality DNA mapped</label>
          </div>
        </div>
      </div>

      {/* Sticky action bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t-4 border-black p-3 z-40">
        <div className="max-w-2xl mx-auto flex gap-2">
          <button onClick={clearAll} className="flex-1 py-3 border-4 border-black font-black bg-white" data-testid="clear-filters-btn">
            <X className="w-4 h-4 inline mr-1" /> Clear
          </button>
          <button onClick={save} disabled={saving} className="flex-1 py-3 bg-[#FF2E63] text-white font-black border-4 border-black shadow-[4px_4px_0_rgba(0,0,0,1)] disabled:opacity-50" data-testid="save-filters-btn">
            <Check className="w-4 h-4 inline mr-1" />
            {saving ? "Saving…" : "Save & apply"}
          </button>
        </div>
      </div>
    </div>
  );
};
