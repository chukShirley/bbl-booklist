const state = {
  books: [],
  overrides: new Map(),
  query: "",
  installPrompt: null,
  scannerStream: null,
  scannerFrame: null,
};

if ("scrollRestoration" in history) history.scrollRestoration = "manual";

const $ = selector => document.querySelector(selector);
const normalize = value => (value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
  .toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const normalizeIsbn = value => (value || "").toUpperCase().replace(/[^0-9X]/g, "");
const isOwned = book => state.overrides.has(book.k) ? state.overrides.get(book.k) : book.o;

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("book-scout", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("ownership", { keyPath: "key" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function loadOverrides() {
  const db = await openDatabase();
  const rows = await new Promise((resolve, reject) => {
    const request = db.transaction("ownership").objectStore("ownership").getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  state.overrides = new Map(rows.map(row => [row.key, row.owned]));
  db.close();
}

async function setOwned(book, owned) {
  state.overrides.set(book.k, owned);
  const db = await openDatabase();
  await new Promise((resolve, reject) => {
    const request = db.transaction("ownership", "readwrite").objectStore("ownership").put({ key: book.k, owned });
    request.onsuccess = resolve;
    request.onerror = () => reject(request.error);
  });
  db.close();
  renderResults();
}

function searchBooks(rawQuery) {
  const normalized = normalize(rawQuery);
  const isbn = normalizeIsbn(rawQuery);
  if ((isbn.length === 10 || isbn.length === 13) && /^\d{9}[\dX]$|^\d{13}$/.test(isbn)) {
    return state.books.filter(book => book.i === isbn).slice(0, 100);
  }
  const terms = [...new Set(normalized.split(" ").filter(Boolean))];
  if (!terms.length) return state.books.filter(book => book.l.length).slice(0, 30);
  return state.books
    .filter(book => terms.every(term => book.s.includes(term)))
    .map(book => {
      const title = normalize(book.t);
      const author = normalize(book.a);
      let score = title === normalized ? 1000 : title.startsWith(normalized) ? 500 : 0;
      for (const term of terms) score += title.includes(term) ? 20 : author.includes(term) ? 10 : 2;
      return [book, score];
    })
    .sort((a, b) => b[1] - a[1] || a[0].t.localeCompare(b[0].t))
    .slice(0, 100)
    .map(([book]) => book);
}

function bookCard(book) {
  const card = $("#book-template").content.firstElementChild.cloneNode(true);
  card.querySelector(".book-title").textContent = book.t;
  card.querySelector(".book-author").textContent = book.a || "Author unknown";
  const owned = isOwned(book);
  const badge = card.querySelector(".owned-badge");
  badge.textContent = owned ? "OWNED" : "ON LIST";
  badge.classList.toggle("is-owned", owned);
  const lists = card.querySelector(".book-lists");
  for (const name of book.l) {
    const item = document.createElement("li");
    item.textContent = `• ${name}`;
    lists.append(item);
  }
  card.querySelector(".book-isbn").textContent = book.i ? `ISBN ${book.i}` : "";
  const toggle = card.querySelector(".owned-button");
  toggle.textContent = owned ? "Mark as not owned" : "We bought this";
  toggle.addEventListener("click", () => setOwned(book, !owned));
  return card;
}

function renderResults() {
  const results = searchBooks(state.query);
  const container = $("#results");
  container.replaceChildren();
  const searched = Boolean(normalize(state.query));
  $("#results-title").textContent = searched
    ? `${results.length}${results.length === 100 ? "+" : ""} ${results.length === 1 ? "match" : "matches"}`
    : "Books to look for";
  $("#catalog-count").textContent = `${state.books.length.toLocaleString()} books offline`;
  if (!results.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = `<h3>Not found</h3><p>“${escapeHtml(state.query)}” isn’t in the downloaded catalog. Check the spelling or try fewer words.</p>`;
    container.append(empty);
  } else {
    container.append(...results.map(bookCard));
  }
  $("#results-section").setAttribute("aria-busy", "false");
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

async function loadCatalog() {
  const response = await fetch("./catalog.json");
  if (!response.ok) throw new Error(`Catalog download failed (${response.status})`);
  const catalog = await response.json();
  state.books = catalog.books;
  renderResults();
  requestAnimationFrame(() => window.scrollTo(0, 0));
  loadOverrides().then(renderResults).catch(error => console.warn("Ownership overrides unavailable", error));
}

function submitSearch(value) {
  state.query = value.trim();
  $("#search-input").value = state.query;
  $("#search-input").blur();
  renderResults();
  window.scrollTo({ top: $("#results-section").offsetTop - 12, behavior: "smooth" });
}

async function startScanner() {
  const dialog = $("#scanner-dialog");
  dialog.showModal();
  if (!("BarcodeDetector" in window)) {
    $("#scanner-message").textContent = "This browser does not provide barcode scanning. Enter the ISBN in search instead.";
    return;
  }
  try {
    const formats = await BarcodeDetector.getSupportedFormats();
    const wanted = formats.includes("ean_13") ? ["ean_13"] : formats;
    const detector = new BarcodeDetector({ formats: wanted });
    state.scannerStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false,
    });
    const video = $("#scanner-video");
    video.srcObject = state.scannerStream;
    await video.play();
    $("#scanner-message").textContent = "Hold the ISBN barcode inside the box.";
    const detect = async () => {
      if (!state.scannerStream) return;
      try {
        const codes = await detector.detect(video);
        const isbn = codes.map(code => normalizeIsbn(code.rawValue)).find(value => value.length === 13 && /^(978|979)/.test(value));
        if (isbn) {
          stopScanner();
          submitSearch(isbn);
          return;
        }
      } catch (_) { /* A frame may be unavailable while the camera starts. */ }
      state.scannerFrame = requestAnimationFrame(detect);
    };
    detect();
  } catch (error) {
    $("#scanner-message").textContent = `Camera unavailable: ${error.message}`;
  }
}

function stopScanner() {
  if (state.scannerFrame) cancelAnimationFrame(state.scannerFrame);
  state.scannerFrame = null;
  state.scannerStream?.getTracks().forEach(track => track.stop());
  state.scannerStream = null;
  $("#scanner-video").srcObject = null;
  $("#scanner-dialog").close();
}

function updateConnection() {
  $("#connection").textContent = navigator.onLine ? "OFFLINE READY" : "OFFLINE";
}

$("#search-form").addEventListener("submit", event => {
  event.preventDefault();
  submitSearch($("#search-input").value);
});
$("#scan-button").addEventListener("click", startScanner);
$("#close-scanner").addEventListener("click", stopScanner);
$("#scanner-dialog").addEventListener("cancel", event => { event.preventDefault(); stopScanner(); });
window.addEventListener("online", updateConnection);
window.addEventListener("offline", updateConnection);
window.addEventListener("beforeinstallprompt", event => {
  event.preventDefault();
  state.installPrompt = event;
  $("#install-button").hidden = false;
});
$("#install-button").addEventListener("click", async () => {
  if (!state.installPrompt) return;
  await state.installPrompt.prompt();
  state.installPrompt = null;
  $("#install-button").hidden = true;
});

if ("serviceWorker" in navigator) navigator.serviceWorker.register("./service-worker.js");
updateConnection();
loadCatalog().catch(error => {
  $("#results-section").setAttribute("aria-busy", "false");
  $("#results-title").textContent = "Catalog unavailable";
  $("#results").innerHTML = `<div class="empty-state"><h3>Couldn’t load books</h3><p>${escapeHtml(error.message)}. Connect once and reload to finish offline setup.</p></div>`;
});
