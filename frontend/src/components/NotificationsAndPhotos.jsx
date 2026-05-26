import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Bell, Camera, Trash2, Loader2, Upload, Check } from "lucide-react";
import { isPushSupported, getPushStatus, subscribeToPush, unsubscribeFromPush, sendTestPush } from "../lib/push";

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

// ==================== PUSH NOTIFICATIONS SETTINGS ====================

export const NotificationsPage = () => {
  const token = useToken();
  const [status, setStatus] = useState({ supported: false, permission: "default", subscribed: false });
  const [busy, setBusy] = useState(false);

  const refresh = async () => setStatus(await getPushStatus());
  useEffect(() => { refresh(); }, []);

  const enable = async () => {
    setBusy(true);
    try {
      await subscribeToPush(token);
      toast.success("Push notifications enabled");
    } catch (e) { toast.error(e.message || "Couldn't enable push"); }
    await refresh();
    setBusy(false);
  };

  const disable = async () => {
    setBusy(true);
    try {
      await unsubscribeFromPush(token);
      toast.success("Push notifications disabled");
    } catch (e) { toast.error("Couldn't disable"); }
    await refresh();
    setBusy(false);
  };

  const test = async () => {
    try {
      const res = await sendTestPush(token);
      toast.success(`Test push sent to ${res.sent} device(s)`);
    } catch { toast.error("Test push failed"); }
  };

  return (
    <PageShell title="Notifications" subtitle="New matches, messages, safety alerts" icon={Bell} testid="notifications-page">
      <div className="border-4 border-black p-5 shadow-[6px_6px_0_rgba(0,0,0,1)]" data-testid="push-status-card">
        {!status.supported && (
          <p className="text-sm" data-testid="push-unsupported">Push notifications aren't supported on this browser. Try Chrome, Firefox, or Edge on desktop / Android.</p>
        )}
        {status.supported && status.permission === "denied" && (
          <div data-testid="push-blocked">
            <p className="font-black text-lg">Permission blocked</p>
            <p className="text-sm mt-1">You've blocked notifications. Open your browser site settings for Spark and switch Notifications to Allow.</p>
          </div>
        )}
        {status.supported && status.permission !== "denied" && !status.subscribed && (
          <div data-testid="push-disabled">
            <p className="font-black text-lg">Get notified for what matters</p>
            <p className="text-sm mt-1 text-gray-600">New matches, new messages, weekly Spark Challenges, and post-date safety reminders.</p>
            <button onClick={enable} disabled={busy} className="mt-4 w-full py-3 bg-[#FF2E63] text-white font-black border-4 border-black shadow-[4px_4px_0_rgba(0,0,0,1)] disabled:opacity-50" data-testid="enable-push-btn">
              {busy ? "Enabling…" : "Enable notifications"}
            </button>
          </div>
        )}
        {status.subscribed && (
          <div data-testid="push-enabled">
            <p className="font-black text-lg flex items-center gap-2"><Check className="w-5 h-5 text-green-600"/> Notifications on</p>
            <p className="text-sm mt-1 text-gray-600">You'll get pushes for new matches, messages, weekly challenges, and safety check-ins.</p>
            <div className="flex gap-2 mt-4">
              <button onClick={test} className="flex-1 py-3 bg-black text-white font-black border-4 border-black" data-testid="test-push-btn">Send test</button>
              <button onClick={disable} disabled={busy} className="flex-1 py-3 bg-white border-4 border-black font-black disabled:opacity-50" data-testid="disable-push-btn">
                {busy ? "Disabling…" : "Turn off"}
              </button>
            </div>
          </div>
        )}
      </div>
      <p className="text-xs text-gray-500 mt-4" data-testid="push-privacy-note">Notifications are sent securely via Web Push. We don't share your device endpoint with anyone.</p>
    </PageShell>
  );
};

// ==================== PHOTO UPLOAD MANAGER ====================

export const PhotoManagerPage = () => {
  const token = useToken();
  const [photos, setPhotos] = useState([]);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const load = async () => {
    try {
      const me = await api("get", "/auth/me", null, token);
      setPhotos(me.photos || []);
    } catch { toast.error("Failed to load photos"); }
  };
  useEffect(() => { if (token) load(); }, [token]);

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      toast.error("Use JPEG, PNG, or WebP");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Max 5MB");
      return;
    }
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await axios.post(`${API}/profile/photo/upload`, form, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setPhotos(res.data.photos || []);
      toast.success("Photo uploaded");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload failed");
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const remove = async (url) => {
    try {
      const res = await api("delete", "/profile/photo", { url }, token);
      setPhotos(res.photos || []);
      toast.success("Photo removed");
    } catch { toast.error("Failed to remove"); }
  };

  const resolveSrc = (url) => {
    if (!url) return "";
    if (url.startsWith("http://") || url.startsWith("https://")) return url;
    if (url.startsWith("/api/files/")) return `${BACKEND_URL}${url}?auth=${encodeURIComponent(token || "")}`;
    return url;
  };

  return (
    <PageShell title="Your Photos" subtitle="JPEG / PNG / WebP up to 5MB each" icon={Camera} testid="photo-manager-page">
      <div className="border-4 border-black p-5 shadow-[6px_6px_0_rgba(0,0,0,1)] mb-4" data-testid="upload-card">
        <p className="font-black text-lg">Add a photo</p>
        <p className="text-xs text-gray-600 mt-1">Stored privately on Spark — only visible to matches and people you appear to in discovery.</p>
        <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" onChange={handleFile} className="hidden" data-testid="file-input" />
        <button onClick={() => fileRef.current?.click()} disabled={uploading} className="mt-4 w-full py-3 bg-[#FF2E63] text-white font-black border-4 border-black shadow-[4px_4px_0_rgba(0,0,0,1)] disabled:opacity-50 flex items-center justify-center gap-2" data-testid="upload-btn">
          {uploading ? <><Loader2 className="w-5 h-5 animate-spin"/> Uploading…</> : <><Upload className="w-5 h-5"/> Choose photo</>}
        </button>
      </div>
      <p className="font-black text-lg mb-3">Your photos ({photos.length})</p>
      {photos.length === 0 ? (
        <p className="text-gray-500" data-testid="no-photos">No photos yet — add at least one to start matching.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3" data-testid="photo-grid">
          {photos.map((url, i) => (
            <div key={i} className="relative border-4 border-black overflow-hidden" data-testid={`photo-${i}`}>
              <img src={resolveSrc(url)} alt={`Photo ${i + 1}`} className="w-full h-48 object-cover" />
              {i === 0 && <span className="absolute top-1 left-1 text-xs font-black bg-yellow-300 px-2 py-0.5 border-2 border-black" data-testid={`primary-badge-${i}`}>MAIN</span>}
              <button onClick={() => remove(url)} className="absolute top-1 right-1 p-1 bg-white border-2 border-black hover:bg-red-200" data-testid={`remove-${i}`}>
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
};
