import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const urlBase64ToUint8Array = (base64String) => {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; ++i) arr[i] = raw.charCodeAt(i);
  return arr;
};

export const isPushSupported = () =>
  typeof window !== "undefined" &&
  "serviceWorker" in navigator &&
  "PushManager" in window &&
  "Notification" in window;

export const getPushStatus = async () => {
  if (!isPushSupported()) return { supported: false, permission: "denied", subscribed: false };
  const permission = Notification.permission;
  let subscribed = false;
  try {
    const reg = await navigator.serviceWorker.getRegistration("/sw.js");
    if (reg) {
      const sub = await reg.pushManager.getSubscription();
      subscribed = !!sub;
    }
  } catch (e) {}
  return { supported: true, permission, subscribed };
};

export const subscribeToPush = async (token) => {
  if (!isPushSupported()) throw new Error("Push not supported on this device/browser");
  let reg = await navigator.serviceWorker.getRegistration("/sw.js");
  if (!reg) reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Permission denied");
  const { data } = await axios.get(`${API}/push/vapid-public-key`);
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(data.public_key),
  });
  const json = sub.toJSON();
  await axios.post(
    `${API}/push/subscribe`,
    {
      endpoint: json.endpoint,
      keys: json.keys,
      user_agent: navigator.userAgent,
    },
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return true;
};

export const unsubscribeFromPush = async (token) => {
  const reg = await navigator.serviceWorker.getRegistration("/sw.js");
  if (!reg) return false;
  const sub = await reg.pushManager.getSubscription();
  if (!sub) return false;
  const endpoint = sub.endpoint;
  await sub.unsubscribe();
  try {
    await axios.post(
      `${API}/push/unsubscribe`,
      { endpoint },
      { headers: { Authorization: `Bearer ${token}` } }
    );
  } catch (e) {}
  return true;
};

export const sendTestPush = async (token) => {
  const { data } = await axios.post(`${API}/push/test`, null, { headers: { Authorization: `Bearer ${token}` } });
  return data;
};
