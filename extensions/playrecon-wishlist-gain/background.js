/* Фоновый воркер: тянет текущее число вишлистов у Gamalytic.

   Content script не может сам ходить на чужой домен — запрос должен идти
   отсюда, из воркера с объявленным host_permissions. Публичный эндпоинт
   gamalytic.com/api/game-details/<appid> не требует ключа. */

const cache = new Map();

async function wishlists(appid) {
  if (cache.has(appid)) return cache.get(appid);
  const out = { appid, wishlists: null, topWish: null };
  try {
    const resp = await fetch(`https://gamalytic.com/api/game-details/${appid}`);
    if (resp.ok) {
      const data = (await resp.json()).data || {};
      out.wishlists = data.wishlists ?? null;
      out.topWish = data.topWish ?? null;
      out.name = data.name ?? null;
    }
  } catch (err) {
    out.error = String(err);
  }
  cache.set(appid, out);
  return out;
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || msg.type !== "gamalytic-wishlists" || !msg.appid) return false;
  wishlists(msg.appid).then(sendResponse);
  return true; // ответ асинхронный
});
