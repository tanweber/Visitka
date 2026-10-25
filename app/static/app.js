// Inline-обработчики запрещены CSP, поэтому всё поведение страниц — здесь.

// ===== язык: исходные строки русские, английский — словарь EN (как i18n_en.py) =====
const LANG = document.documentElement.lang === "en" ? "en" : "ru";
const EN = {
  "Не удалось скопировать — выделите текст вручную.": "Couldn't copy — select the text manually.",
  "Скопировано": "Copied",
  "Пароли не совпадают": "Passwords don't match",
  "Обрезка фото": "Crop photo",
  "Отмена": "Cancel",
  "Фото": "Photo",
  "Готово": "Done",
  "Масштаб": "Zoom",
  "Перетащите фото и приблизьте ползунком, колёсиком или двумя пальцами": "Drag the photo; zoom with the slider, mouse wheel or two fingers",
  "Браузер не смог показать это фото — оно будет обрезано по центру.": "The browser can't display this photo — it will be cropped to the center.",
  "Нажмите, чтобы изменить обрезку": "Click to adjust the crop",
  "МБ": "MB",
  "КБ": "KB",
  "Минутку…": "Just a moment…",
  "Загружаю файл…": "Uploading file…",
  "Сохраняю контакты…": "Saving contacts…",
  "{done} из {total}": "{done} of {total}",
  "Связь прервалась. Импорт продолжается на сервере — обновите список чуть позже.": "Connection lost. The import continues on the server — refresh the list a bit later.",
  "Читаю файл…": "Reading file…",
  "Файл слишком большой для сервера.": "The file is too large for the server.",
  "Не удалось импортировать (ошибка {status}).": "Import failed (error {status}).",
  "Импортирую контакты…": "Importing contacts…",
  "Готовлю файл…": "Preparing file…",
  "Сохранено: {name} · {size}": "Saved: {name} · {size}",
  "Не удалось скачать файл.": "Download failed.",
  "Найдено {n} из {total}": "Found {n} of {total}",
  "Организация": "Organization",
  "Все организации": "All organizations",
};
const EN_PLURAL = { "контакт": ["contact", "contacts"] };

function t(text, values = {}) {
  const template = LANG === "en" ? (EN[text] || text) : text;
  return template.replace(/\{(\w+)\}/g, (match, key) => (key in values ? values[key] : match));
}

// подтверждение опасных действий
document.addEventListener("submit", (event) => {
  const message = event.target.dataset && event.target.dataset.confirm;
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});

document.addEventListener("click", (event) => {
  // смена темы без перезагрузки; ссылка /theme/<name> остаётся запасным путём
  const option = event.target.closest("[data-theme-set]");
  if (option) {
    event.preventDefault();
    const theme = option.dataset.themeSet;
    const secure = location.protocol === "https:" ? "; secure" : "";
    document.cookie = `theme=${theme}; max-age=31536000; path=/; samesite=lax${secure}`;
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll("[data-theme-set]").forEach((el) => {
      if (el === option) el.setAttribute("aria-current", "true");
      else el.removeAttribute("aria-current");
    });
    option.closest("details")?.removeAttribute("open");
    return;
  }

  // копирование пароля устройства, адреса сервера, имени пользователя
  const copy = event.target.closest("[data-copy]");
  if (copy) {
    const source = document.querySelector(copy.dataset.copy);
    if (source) {
      copyText(source.textContent.trim(), source).then((ok) => {
        if (!ok) return toast(t("Не удалось скопировать — выделите текст вручную."), { timeout: 3000 });
        if (copy.classList.contains("copy-icon")) {
          copy.classList.add("is-copied");
          setTimeout(() => copy.classList.remove("is-copied"), 1600);
          toast(t("Скопировано"), { timeout: 1600 });
        } else {
          const label = copy.textContent;
          copy.textContent = t("Скопировано");
          setTimeout(() => { copy.textContent = label; }, 1600);
        }
      });
    }
    return;
  }

  // клик мимо открытого меню закрывает его
  document.querySelectorAll("details.menu[open]").forEach((menu) => {
    if (!menu.contains(event.target)) menu.removeAttribute("open");
  });
});

// буфер обмена: Clipboard API есть только на https; иначе — старый способ через выделение
async function copyText(text, source) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (err) { /* пробуем запасной путь */ }
  const range = document.createRange();
  range.selectNodeContents(source);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
  selection.removeAllRanges();
  return ok;
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.querySelectorAll("details.menu[open]").forEach((menu) => menu.removeAttribute("open"));
  }
});

// повтор пароля: браузер не даст отправить форму, пока пароли не совпадут
document.addEventListener("input", (event) => {
  const form = event.target.form;
  const repeat = form && form.querySelector("input[data-match]");
  if (!repeat) return;
  const original = form.elements[repeat.dataset.match];
  const mismatch = repeat.value !== "" && repeat.value !== original.value;
  repeat.setCustomValidity(mismatch ? t("Пароли не совпадают") : "");
  repeat.classList.toggle("is-mismatch", mismatch);
});

// ===== фото: обрезка и масштаб перед сохранением =====
// Файл уходит на сервер целиком, а выбранный квадрат — полем photo_crop
// («x,y,s» в долях); режет сервер, так что результат не зависит от браузера.

const MAX_ZOOM = 5;

function openCropper(url, saved, onDone) {
  const box = document.createElement("div");
  box.className = "cropper";
  box.setAttribute("role", "dialog");
  box.setAttribute("aria-modal", "true");
  box.setAttribute("aria-label", t("Обрезка фото"));
  box.innerHTML =
    '<div class="cropper-box">' +
    `<div class="cropper-head"><button type="button" class="text-button" data-crop-cancel>${t("Отмена")}</button>` +
    `<strong>${t("Фото")}</strong><button type="button" class="text-button strong" data-crop-done>${t("Готово")}</button></div>` +
    '<div class="cropper-stage"><img alt="" draggable="false"><div class="cropper-ring"></div></div>' +
    '<div class="cropper-zoom">' +
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/></svg>' +
    `<input type="range" min="1" max="${MAX_ZOOM}" step="0.01" value="1" aria-label="${t("Масштаб")}">` +
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/></svg></div>' +
    `<p class="hint">${t("Перетащите фото и приблизьте ползунком, колёсиком или двумя пальцами")}</p>` +
    "</div>";
  const stage = box.querySelector(".cropper-stage");
  const img = box.querySelector("img");
  const range = box.querySelector("input[type=range]");
  // x, y — левый верхний угол картинки относительно рамки; zoom ≥ 1 — «заполнить рамку»
  const st = { w: 0, h: 0, view: 0, zoom: 1, x: 0, y: 0 };
  const scale = () => (st.view / Math.min(st.w, st.h)) * st.zoom;

  const render = () => {
    const k = scale();
    st.x = Math.min(0, Math.max(st.view - st.w * k, st.x));
    st.y = Math.min(0, Math.max(st.view - st.h * k, st.y));
    img.style.width = `${st.w * k}px`;
    img.style.height = `${st.h * k}px`;
    img.style.transform = `translate3d(${st.x}px, ${st.y}px, 0)`;
    range.value = st.zoom;
  };
  // масштаб вокруг точки (cx, cy) рамки — она остаётся под пальцем
  const zoomAt = (zoom, cx, cy) => {
    const before = scale();
    st.zoom = Math.min(MAX_ZOOM, Math.max(1, zoom));
    const after = scale();
    st.x = cx - ((cx - st.x) / before) * after;
    st.y = cy - ((cy - st.y) / before) * after;
    render();
  };

  const pointers = new Map();
  stage.addEventListener("pointerdown", (e) => {
    stage.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  });
  stage.addEventListener("pointermove", (e) => {
    const prev = pointers.get(e.pointerId);
    if (!prev) return;
    const others = [...pointers.entries()].filter(([id]) => id !== e.pointerId).map(([, p]) => p);
    if (others.length === 0) {
      st.x += e.clientX - prev.x;
      st.y += e.clientY - prev.y;
      render();
    } else {
      // щипок: масштаб по расстоянию между пальцами, сдвиг — по их середине
      const other = others[0];
      const rect = stage.getBoundingClientRect();
      const dist = (a) => Math.hypot(a.x - other.x, a.y - other.y) || 1;
      const now = { x: e.clientX, y: e.clientY };
      const mid = { x: (prev.x + other.x) / 2 - rect.left, y: (prev.y + other.y) / 2 - rect.top };
      zoomAt(st.zoom * (dist(now) / dist(prev)), mid.x, mid.y);
      st.x += (now.x - prev.x) / 2;
      st.y += (now.y - prev.y) / 2;
      render();
    }
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  });
  ["pointerup", "pointercancel"].forEach((type) => stage.addEventListener(type, (e) => pointers.delete(e.pointerId)));
  stage.addEventListener("wheel", (e) => {
    e.preventDefault();
    const rect = stage.getBoundingClientRect();
    zoomAt(st.zoom * Math.exp(-e.deltaY * 0.0015), e.clientX - rect.left, e.clientY - rect.top);
  }, { passive: false });
  range.addEventListener("input", () => zoomAt(Number(range.value), st.view / 2, st.view / 2));

  const close = () => {
    box.remove();
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (e) => {
    if (e.key === "Escape") { close(); onDone(null); }
  };
  document.addEventListener("keydown", onKey);
  box.querySelector("[data-crop-cancel]").addEventListener("click", () => { close(); onDone(null); });
  box.querySelector("[data-crop-done]").addEventListener("click", () => {
    const k = scale();
    const side = st.view / k;
    close();
    onDone({
      // для сервера: доли от размеров картинки
      crop: [-st.x / k / st.w, -st.y / k / st.h, side / Math.min(st.w, st.h)].map((v) => v.toFixed(5)).join(","),
      // для превью: квадрат в пикселях исходника
      rect: { sx: -st.x / k, sy: -st.y / k, side },
      state: { zoom: st.zoom, fx: -st.x / k / st.w, fy: -st.y / k / st.h },
      img,
    });
  });

  img.addEventListener("load", () => {
    st.w = img.naturalWidth;
    st.h = img.naturalHeight;
    st.view = stage.clientWidth;
    if (saved) {
      // повторное открытие — с той же обрезкой
      st.zoom = saved.zoom;
      st.x = -saved.fx * st.w * scale();
      st.y = -saved.fy * st.h * scale();
    } else {
      st.x = (st.view - st.w * scale()) / 2;
      st.y = (st.view - st.h * scale()) / 2;
    }
    render();
    box.querySelector("[data-crop-done]").focus();
  });
  img.addEventListener("error", () => {
    close();
    toast(t("Браузер не смог показать это фото — оно будет обрезано по центру."), { timeout: 5000 });
    onDone(null, true);
  });
  document.body.append(box);
  img.src = url;
}

function initPhotoPicker() {
  const input = document.querySelector("[data-photo-input]");
  const preview = document.querySelector("[data-photo-preview]");
  const cropField = document.querySelector("[data-photo-crop]");
  if (!input || !preview || !cropField) return;
  const original = [...preview.childNodes];
  let url = null;
  let saved = null;

  const showCrop = (result) => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 224;  // xl-аватар 112px × 2 для чётких экранов
    canvas.className = "avatar xl";
    canvas.title = t("Нажмите, чтобы изменить обрезку");
    const { sx, sy, side } = result.rect;
    canvas.getContext("2d").drawImage(result.img, sx, sy, side, side, 0, 0, 224, 224);
    preview.replaceChildren(canvas);
    preview.classList.add("is-croppable");
  };
  const crop = () => openCropper(url, saved, (result, unreadable) => {
    if (result) {
      cropField.value = result.crop;
      saved = result.state;
      showCrop(result);
      const remove = document.querySelector("input[name=photo_remove]");
      if (remove) remove.checked = false;
    } else if (unreadable) {
      cropField.value = "";
    } else if (!saved) {
      // отменили обрезку только что выбранного файла — как будто его и не выбирали
      input.value = "";
      cropField.value = "";
      preview.replaceChildren(...original);
    }
  });

  input.addEventListener("change", () => {
    if (url) URL.revokeObjectURL(url);
    url = null;
    saved = null;
    cropField.value = "";
    preview.classList.remove("is-croppable");
    if (!input.files || !input.files[0]) {
      preview.replaceChildren(...original);
      return;
    }
    url = URL.createObjectURL(input.files[0]);
    crop();
  });
  preview.addEventListener("click", () => {
    if (url && saved) crop();
  });
}

// ===== индикаторы загрузки =====

function overlay(message, { progress = false } = {}) {
  const box = document.createElement("div");
  box.className = "busy-overlay";
  box.setAttribute("role", "status");
  box.innerHTML = '<div class="busy-box"><span class="spinner"></span><p></p>' +
    (progress ? '<div class="progress"><span></span></div><small class="hint"></small>' : "") + "</div>";
  box.querySelector("p").textContent = message;
  document.body.append(box);
  return {
    text(value) { box.querySelector("p").textContent = value; },
    percent(value, note) {
      const bar = box.querySelector(".progress");
      if (!bar) return;
      bar.classList.toggle("indeterminate", value === null);
      bar.firstElementChild.style.width = value === null ? "" : `${value}%`;
      box.querySelector("small").textContent = note || "";
    },
    close() { box.remove(); },
  };
}

// убрать все экраны ожидания и разблокировать формы
function clearBusy() {
  document.querySelectorAll(".busy-overlay").forEach((el) => el.remove());
  document.querySelectorAll(".is-busy").forEach((el) => el.classList.remove("is-busy"));
}

// возврат «Назад» из кэша браузера восстанавливает страницу вместе с открытым окном ожидания
window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    clearBusy();
    document.querySelectorAll(".toast").forEach((el) => el.remove());
  }
});

function toast(message, { busy = false, timeout = 0 } = {}) {
  document.querySelectorAll(".toast").forEach((el) => el.remove());
  const el = document.createElement("div");
  el.className = "toast";
  el.setAttribute("role", "status");
  if (busy) el.append(Object.assign(document.createElement("span"), { className: "spinner" }));
  el.append(document.createTextNode(message));
  document.body.append(el);
  if (timeout) setTimeout(() => el.remove(), timeout);
  return el;
}

function formatSize(bytes) {
  return bytes > 1048576 ? `${(bytes / 1048576).toFixed(1)} ${t("МБ")}` : `${Math.max(1, Math.round(bytes / 1024))} ${t("КБ")}`;
}

// формы с data-busy: после подтверждения — блокировка кнопки и экран ожидания
document.addEventListener("submit", (event) => {
  const form = event.target;
  if (event.defaultPrevented || !form.dataset || !("busy" in form.dataset)) return;
  if (form.matches("[data-import]")) return;  // у импорта свой обработчик с прогрессом
  form.classList.add("is-busy");
  overlay(form.dataset.busy || t("Минутку…"));
});

// импорт: этап 1 — отправка файла (XHR, прогресс по байтам),
// этап 2 — сервер сохраняет карточки в фоне, опрашиваем «N из M»
document.addEventListener("submit", (event) => {
  const form = event.target;
  if (event.defaultPrevented || !form.matches || !form.matches("[data-import]")) return;
  if (!window.XMLHttpRequest || !window.fetch) return;  // обычная отправка формы
  event.preventDefault();
  const busy = overlay(t("Загружаю файл…"), { progress: true });
  busy.percent(0, "");
  const fail = (message) => {
    clearBusy();
    toast(message, { timeout: 5000 });
  };

  const poll = async (job, total) => {
    busy.text(t("Сохраняю контакты…"));
    busy.percent(0, t("{done} из {total}", { done: 0, total }));
    for (;;) {
      let state;
      try {
        const response = await fetch(`/import/jobs/${encodeURIComponent(job)}`, { credentials: "same-origin" });
        if (!response.ok) throw new Error(response.status);
        state = await response.json();
      } catch (err) {
        fail(t("Связь прервалась. Импорт продолжается на сервере — обновите список чуть позже."));
        return;
      }
      const pct = state.total ? Math.round((state.done / state.total) * 100) : 100;
      busy.percent(pct, t("{done} из {total}", { done: state.done, total: state.total }));
      if (state.finished) {
        busy.text(t("Готово"));
        window.location.href = `/import?job=${encodeURIComponent(job)}`;
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  };

  const xhr = new XMLHttpRequest();
  xhr.open("POST", form.action);
  xhr.setRequestHeader("X-Import-Progress", "1");
  xhr.upload.addEventListener("progress", (e) => {
    if (e.lengthComputable) {
      busy.percent(Math.round((e.loaded / e.total) * 100), t("{done} из {total}", { done: formatSize(e.loaded), total: formatSize(e.total) }));
    }
  });
  xhr.upload.addEventListener("load", () => {
    busy.text(t("Читаю файл…"));
    busy.percent(null, "");
  });
  xhr.addEventListener("load", () => {
    // сессия истекла — сервер увёл на страницу входа
    if (xhr.responseURL && new URL(xhr.responseURL).pathname === "/login") {
      window.location.href = "/login";
      return;
    }
    if (xhr.status === 413) return fail(t("Файл слишком большой для сервера."));
    let data = null;
    try { data = JSON.parse(xhr.responseText); } catch (err) { /* не JSON */ }
    if (xhr.status !== 200 || !data || !data.job) {
      return fail(t("Не удалось импортировать (ошибка {status}).", { status: xhr.status }));
    }
    poll(data.job, data.total);
  });
  xhr.addEventListener("error", () => {
    // XHR не прошёл (сеть, прокси, политика браузера) — отправляем форму обычным способом
    busy.text(t("Импортирую контакты…"));
    busy.percent(null, "");
    HTMLFormElement.prototype.submit.call(form);
  });
  xhr.send(new FormData(form));
});

// экспорт: скачивание через fetch, чтобы показать, что файл готовится
document.addEventListener("click", async (event) => {
  const link = event.target.closest("a[data-download]");
  if (!link || !window.fetch) return;
  event.preventDefault();
  link.closest("details")?.removeAttribute("open");
  const pending = toast(link.dataset.download || t("Готовлю файл…"), { busy: true });
  // страховка: плашка ожидания не висит дольше двух минут
  const guard = setTimeout(() => pending.remove(), 120000);
  try {
    const response = await fetch(link.href, { credentials: "same-origin" });
    if (!response.ok) throw new Error(response.status);
    const blob = await response.blob();
    const header = response.headers.get("content-disposition") || "";
    const utf = header.match(/filename\*=UTF-8''([^;]+)/i);
    const plain = header.match(/filename="([^"]+)"/i);
    const name = utf ? decodeURIComponent(utf[1]) : (plain ? plain[1] : "contacts.vcf");
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: name });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    toast(t("Сохранено: {name} · {size}", { name, size: formatSize(blob.size) }), { timeout: 3000 });
  } catch (err) {
    toast(t("Не удалось скачать файл."), { timeout: 4000 });
  } finally {
    clearTimeout(guard);
    pending.remove();
  }
});

// ===== то, что нужно заново навесить после подмены <main> =====

function initPage() {
  // импорт: имена выбранных файлов и перетаскивание в зону
  document.querySelectorAll("[data-dropzone]").forEach((zone) => {
    const input = zone.querySelector("input[type=file]");
    const list = zone.querySelector("[data-files]");
    const show = () => {
      const files = Array.from(input.files);
      const size = files.reduce((sum, f) => sum + f.size, 0);
      list.textContent = files.length ? `${files.map((f) => f.name).join(", ")} · ${formatSize(size)}` : "";
    };
    input.addEventListener("change", show);
    ["dragenter", "dragover"].forEach((type) => zone.addEventListener(type, (event) => {
      event.preventDefault();
      zone.classList.add("is-over");
    }));
    ["dragleave", "drop"].forEach((type) => zone.addEventListener(type, () => zone.classList.remove("is-over")));
    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      if (event.dataTransfer && event.dataTransfer.files.length) {
        input.files = event.dataTransfer.files;
        show();
      }
    });
  });

  // очистка: кнопка активна, только когда введено слово-подтверждение
  document.querySelectorAll("[data-confirm-word]").forEach((input) => {
    const button = input.form.querySelector("button[type=submit]");
    const check = () => { button.disabled = input.value.trim().toUpperCase() !== input.dataset.confirmWord; };
    input.addEventListener("input", check);
    check();
  });
}

// ===== список: поиск на лету и алфавит =====

function plural(n, one, few, many) {
  if (LANG === "en") {
    const [singular, pluralForm] = EN_PLURAL[one] || [one, many];
    return n === 1 ? singular : pluralForm;
  }
  const d = n % 10, h = n % 100;
  if (d === 1 && h !== 11) return one;
  if (d >= 2 && d <= 4 && (h < 12 || h > 14)) return few;
  return many;
}

// та же логика, что _search на сервере: каждое слово ищется в имени/организации/e-mail
// или, если это номер, в цифрах телефонов (8 900… = +7 900…)
function wordMatches(word, text, digits) {
  if (text.includes(word)) return true;
  const num = word.replace(/[\s()+.-]/g, "");
  if (num.length < 2 || !/^\d+$/.test(num)) return false;
  return digits.includes(num) || (num[0] === "8" && digits.includes("7" + num.slice(1)));
}

function initLiveSearch() {
  const form = document.querySelector("[data-live-search]");
  const box = document.querySelector("[data-contacts]");
  if (!form || !box) return;
  const input = form.querySelector("input[type=search]");
  const orgSelect = form.querySelector("select[name=org]");
  const rows = [...box.querySelectorAll("li[data-search]")].map((el) => ({
    el, text: el.dataset.search, digits: el.dataset.digits,
    photo: el.dataset.photo === "1", org: el.dataset.org,
  }));
  const groups = [...box.querySelectorAll("[data-group]")];
  const count = document.querySelector("[data-count]");
  const empty = document.querySelector("[data-no-results]");
  const alphabet = document.querySelector("[data-alphabet]");
  const total = rows.length;

  const apply = () => {
    const query = input.value.toLowerCase().replace(/ё/g, "е").trim();
    // номер, набранный с пробелами («8 900 123»), ищем целиком, а не по словам
    const words = /^[\d\s()+.-]+$/.test(query) ? [query] : query.split(/\s+/).filter(Boolean);
    const photo = form.querySelector("input[name=photo]:checked")?.value || "";
    const org = orgSelect ? orgSelect.value : "";
    const orgKey = org === "-" ? "" : org;  // «-» — без организации
    const filtering = words.length > 0 || photo !== "" || org !== "";
    let shown = 0;
    // счётчики в фильтрах учитывают остальные условия: «Ромашка · 2» при включённом «С фото»
    const photoCounts = { "": 0, with: 0, without: 0 };
    const orgCounts = new Map();
    let orgAll = 0;
    for (const row of rows) {
      const m = words.every((w) => wordMatches(w, row.text, row.digits));
      const p = !photo || row.photo === (photo === "with");
      const o = !org || row.org === orgKey;
      const ok = m && p && o;
      row.el.hidden = !ok;
      if (ok) shown += 1;
      if (m && o) {
        photoCounts[""] += 1;
        photoCounts[row.photo ? "with" : "without"] += 1;
      }
      if (m && p) {
        orgAll += 1;
        const key = row.org || "-";
        orgCounts.set(key, (orgCounts.get(key) || 0) + 1);
      }
    }
    form.querySelectorAll("input[name=photo]").forEach((radio) => {
      const n = radio.closest("label").querySelector(".n");
      if (n) n.textContent = photoCounts[radio.value];
    });
    if (orgSelect) {
      [...orgSelect.options].forEach((opt) => {
        const n = opt.value ? (orgCounts.get(opt.value) || 0) : orgAll;
        opt.textContent = `${opt.textContent.split(" · ")[0]} · ${n}`;
      });
      orgSelect.dispatchEvent(new Event("counts"));
    }
    groups.forEach((g) => { g.hidden = !g.querySelector("li:not([hidden])"); });
    count.textContent = filtering
      ? t("Найдено {n} из {total}", { n: shown, total })
      : `${total} ${plural(total, "контакт", "контакта", "контактов")}`;
    if (empty) empty.hidden = !filtering || shown > 0;
    if (alphabet) {
      // в ленте — только буквы, по которым что-то осталось
      let letters = 0;
      alphabet.querySelectorAll("a[href]").forEach((a) => {
        a.hidden = document.querySelector(a.getAttribute("href"))?.hidden ?? true;
        if (!a.hidden) letters += 1;
      });
      alphabet.hidden = letters < 2;
    }
    orgSelect?.closest(".select-chip")?.classList.toggle("is-set", org !== "");
    // адрес с параметрами — чтобы «Назад» из карточки вернул тот же поиск и фильтры
    const params = new URLSearchParams();
    if (input.value.trim()) params.set("q", input.value.trim());
    if (photo) params.set("photo", photo);
    if (org) params.set("org", org);
    const qs = params.toString();
    history.replaceState(history.state, "", qs ? `/?${qs}` : "/");
  };
  input.addEventListener("input", apply);
  form.addEventListener("change", apply);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    apply();
    input.blur();  // на телефоне прячет клавиатуру
  });
  apply();
}

// фильтр организаций: системный выпадающий список не перекрашивается под тему,
// поэтому рисуем своё меню; скрытый <select> остаётся источником значения
function initOrgPicker() {
  const chip = document.querySelector("[data-org-picker]");
  const select = chip && chip.querySelector("select");
  if (!select) return;
  const menu = document.createElement("details");
  menu.className = "menu org-menu";
  const summary = document.createElement("summary");
  summary.className = "select-button";
  const panel = document.createElement("div");
  panel.className = "menu-panel";
  panel.setAttribute("role", "listbox");
  panel.setAttribute("aria-label", t("Организация"));
  const tick = '<svg class="tick" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
  const options = [...select.options].map((opt) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "theme-option";
    button.setAttribute("role", "option");
    button.dataset.value = opt.value;
    // «Ромашка · 30» → название и счётчик отдельно
    const [label, n] = opt.textContent.split(" · ");
    button.innerHTML = `<span class="opt-label"></span><span class="opt-n"></span>${tick}`;
    button.querySelector(".opt-label").textContent = label;
    button.querySelector(".opt-n").textContent = n || "";
    if (opt.value === "-") button.classList.add("is-separated");
    panel.append(button);
    return button;
  });
  const sync = () => {
    [...select.options].forEach((opt, i) => {
      const n = opt.textContent.split(" · ")[1] || "";
      options[i].querySelector(".opt-n").textContent = n;
      options[i].classList.toggle("is-empty", n === "0" && opt.value !== select.value);
    });
    const current = select.selectedOptions[0];
    summary.textContent = current ? current.textContent.split(" · ")[0] : t("Все организации");
    options.forEach((b) => b.setAttribute("aria-current", String(b.dataset.value === select.value)));
  };
  panel.addEventListener("click", (event) => {
    const button = event.target.closest("[data-value]");
    if (!button) return;
    select.value = button.dataset.value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    menu.removeAttribute("open");
    summary.focus();
  });
  // стрелки — по пунктам меню
  menu.addEventListener("keydown", (event) => {
    if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
    event.preventDefault();
    if (!menu.open) menu.open = true;
    const i = options.indexOf(document.activeElement);
    const next = event.key === "ArrowDown" ? Math.min(options.length - 1, i + 1) : Math.max(0, i - 1);
    options[i === -1 ? options.findIndex((b) => b.dataset.value === select.value) : next]?.focus();
  });
  menu.addEventListener("toggle", () => {
    if (menu.open) panel.querySelector('[aria-current="true"]')?.scrollIntoView({ block: "nearest" });
  });
  select.addEventListener("change", sync);
  select.addEventListener("counts", sync);
  select.classList.add("visually-hidden");
  select.tabIndex = -1;
  select.setAttribute("aria-hidden", "true");
  menu.append(summary, panel);
  chip.append(menu);
  chip.classList.add("is-enhanced");
  sync();
}

function initAlphabet() {
  const nav = document.querySelector("[data-alphabet]");
  if (!nav) return;
  let bubble = null;
  let current = null;

  const jump = (link) => {
    if (!link || link === current) return;
    current = link;
    document.querySelector(link.getAttribute("href"))?.scrollIntoView({ block: "start" });
    if (bubble) bubble.textContent = link.dataset.letter;
    if (navigator.vibrate) navigator.vibrate(4);
  };
  const linkAt = (e) => {
    const rect = nav.getBoundingClientRect();
    // по горизонтали берём середину ленты: палец не обязан попадать точно в букву
    const el = document.elementFromPoint(rect.left + rect.width / 2, e.clientY);
    return el && el.closest("[data-letter]");
  };
  const end = () => {
    nav.classList.remove("is-active");
    const shown = bubble;
    setTimeout(() => shown?.remove(), 350);  // буква видна и после короткого тапа
    bubble = null;
    current = null;
  };

  nav.addEventListener("click", (e) => e.preventDefault());
  nav.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    nav.setPointerCapture(e.pointerId);
    nav.classList.add("is-active");
    document.querySelectorAll(".alphabet-bubble").forEach((el) => el.remove());
    bubble = Object.assign(document.createElement("div"), { className: "alphabet-bubble" });
    bubble.setAttribute("aria-hidden", "true");
    document.body.append(bubble);
    jump(linkAt(e));
  });
  nav.addEventListener("pointermove", (e) => {
    if (bubble) jump(linkAt(e));
  });
  nav.addEventListener("pointerup", end);
  nav.addEventListener("pointercancel", end);
  // клавиатура: Enter на букве
  nav.addEventListener("keydown", (e) => {
    const link = e.target.closest("[data-letter]");
    if (link && e.key === "Enter") {
      current = null;
      jump(link);
    }
  });
}

initPage();
initPhotoPicker();
initOrgPicker();
initLiveSearch();
initAlphabet();
