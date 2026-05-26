/* Spark service worker — Web Push receiver */
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let data = { title: "Spark", body: "You have a new notification", url: "/", tag: "spark" };
  try {
    if (event.data) {
      data = { ...data, ...event.data.json() };
    }
  } catch (e) {
    data.body = event.data ? event.data.text() : data.body;
  }
  const options = {
    body: data.body,
    icon: "/spark-icon-192.png",
    badge: "/spark-badge-72.png",
    tag: data.tag || "spark",
    data: { url: data.url || "/" },
    vibrate: [120, 60, 120],
    requireInteraction: false,
  };
  event.waitUntil(self.registration.showNotification(data.title || "Spark", options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientsArr) => {
      for (const client of clientsArr) {
        try {
          const url = new URL(client.url);
          if (url.origin === self.location.origin) {
            client.focus();
            client.postMessage({ type: "navigate", url: targetUrl });
            return;
          }
        } catch (e) {}
      }
      return self.clients.openWindow(targetUrl);
    })
  );
});
