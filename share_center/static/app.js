"use strict";

const state = {
  items: [],
  filter: "PENDENTE",
  loading: false,
  authenticated: false,
};

const grid = document.getElementById("grid");
const notice = document.getElementById("notice");
const template = document.getElementById("card-template");
const refreshButton = document.getElementById("refresh");
const loginPanel = document.getElementById("login-panel");
const loginForm = document.getElementById("login-form");
const pinInput = document.getElementById("pin-input");
const loginNotice = document.getElementById("login-notice");
const logoutButton = document.getElementById("logout");

function setNotice(message, kind = "") {
  notice.textContent = message;
  notice.className = `notice ${kind}`.trim();
}

function setLoginNotice(message, kind = "") {
  loginNotice.textContent = message;
  loginNotice.className = `login-notice ${kind}`.trim();
}

function setLocked(locked) {
  state.authenticated = !locked;
  document.body.classList.toggle("locked", locked);
  loginPanel.setAttribute("aria-hidden", locked ? "false" : "true");
  if (locked) {
    state.items = [];
    grid.replaceChildren();
    pinInput.focus();
  }
}

function counts() {
  const result = { PENDENTE: 0, PUBLICADO: 0, ARQUIVADO: 0 };
  for (const item of state.items) {
    if (Object.hasOwn(result, item.status)) result[item.status] += 1;
  }
  document.getElementById("count-pendente").textContent = result.PENDENTE;
  document.getElementById("count-publicado").textContent = result.PUBLICADO;
  document.getElementById("count-arquivado").textContent = result.ARQUIVADO;
  document.getElementById("count-todos").textContent = state.items.length;
}

function fallbackCopy(value) {
  const field = document.createElement("textarea");
  field.value = value;
  field.setAttribute("readonly", "");
  field.style.position = "fixed";
  field.style.opacity = "0";
  field.style.pointerEvents = "none";
  document.body.appendChild(field);
  field.focus();
  field.select();
  field.setSelectionRange(0, field.value.length);
  const copied = document.execCommand("copy");
  field.remove();
  if (!copied) throw new Error("copy");
}

async function copyText(value, success) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(value);
    } else {
      fallbackCopy(value);
    }
    setNotice(success, "success");
  } catch {
    setNotice(
      "Não foi possível copiar automaticamente. Selecione e copie manualmente.",
      "error",
    );
  }
}

async function apiJson(url, options = {}) {
  const response = await fetch(url, options);
  let data = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }
  if (response.status === 401) {
    setLocked(true);
    setLoginNotice("Sua sessão expirou. Digite o PIN novamente.", "error");
  }
  return { response, data };
}

async function setStatus(item, status) {
  try {
    const { response, data } = await apiJson(
      `/api/items/${encodeURIComponent(item.id)}/status`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      },
    );
    if (!response.ok || !data.ok) throw new Error(data.error || "status");
    item.status = status;
    render();
    setNotice("Status atualizado.", "success");
  } catch (error) {
    if (!state.authenticated) return;
    setNotice(
      error instanceof Error && error.message
        ? error.message
        : "Não foi possível atualizar o status.",
      "error",
    );
  }
}

function button(card, action) {
  return card.querySelector(`[data-action="${action}"]`);
}

function renderCard(item) {
  const card = template.content.firstElementChild.cloneNode(true);
  const imageLink = card.querySelector(".media");
  const image = card.querySelector("img");
  image.src = item.image;
  image.alt = item.name;
  imageLink.href = item.image;

  card.querySelector(".partner").textContent = item.partner || "Parceiro";
  const status = card.querySelector(".status");
  status.textContent = item.status;
  status.dataset.status = item.status;

  card.querySelector("h2").textContent = item.name;
  card.querySelector(".description").textContent = item.description;
  card.querySelector(".price").textContent = item.price;
  card.querySelector(".affiliate").textContent = item.affiliateUrl;

  button(card, "whatsapp").href = "https://web.whatsapp.com/";
  button(card, "image").href = item.image;
  button(card, "copy-publication").addEventListener(
    "click",
    () => copyText(item.publication, "Publicação copiada."),
  );
  button(card, "copy-link").addEventListener(
    "click",
    () => copyText(item.affiliateUrl, "Link afiliado copiado."),
  );
  button(card, "published").addEventListener(
    "click",
    () => setStatus(item, "PUBLICADO"),
  );
  button(card, "pending").addEventListener(
    "click",
    () => setStatus(item, "PENDENTE"),
  );
  button(card, "archive").addEventListener(
    "click",
    () => setStatus(item, "ARQUIVADO"),
  );

  button(card, "published").hidden = item.status === "PUBLICADO";
  button(card, "pending").hidden = item.status === "PENDENTE";
  button(card, "archive").hidden = item.status === "ARQUIVADO";
  return card;
}

function render() {
  counts();
  const visible = state.items.filter(
    (item) => state.filter === "TODOS" || item.status === state.filter,
  );
  grid.replaceChildren(...visible.map(renderCard));
  if (!visible.length && !state.loading) {
    setNotice(
      state.filter === "PENDENTE"
        ? "Nenhuma divulgação pendente."
        : "Nenhum item neste filtro.",
    );
  } else if (visible.length) {
    setNotice("");
  }
}

async function load() {
  if (state.loading || !state.authenticated) return;
  state.loading = true;
  refreshButton.disabled = true;
  setNotice("Atualizando fila…");
  try {
    const { response, data } = await apiJson(
      "/api/items",
      { cache: "no-store" },
    );
    if (!response.ok || !data.ok || !Array.isArray(data.items)) {
      throw new Error(data.error || "Fila indisponível.");
    }
    state.items = data.items;
    render();
  } catch (error) {
    if (!state.authenticated) return;
    setNotice(
      error instanceof Error && error.message
        ? error.message
        : "Fila backend ainda não está disponível.",
      "error",
    );
  } finally {
    state.loading = false;
    refreshButton.disabled = false;
  }
}

async function checkSession() {
  try {
    const response = await fetch("/api/session", { cache: "no-store" });
    const data = await response.json();
    if (response.ok && data.ok && data.authenticated === true) {
      setLocked(false);
      await load();
      return;
    }
  } catch {
    setLoginNotice("A Central local não respondeu.", "error");
  }
  setLocked(true);
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const pin = pinInput.value.trim();
  if (!/^\d{8}$/.test(pin)) {
    setLoginNotice("Digite os 8 dígitos do PIN.", "error");
    return;
  }

  const submit = loginForm.querySelector('button[type="submit"]');
  submit.disabled = true;
  setLoginNotice("Validando…");
  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "PIN inválido.");
    }
    pinInput.value = "";
    setLoginNotice("");
    setLocked(false);
    await load();
  } catch (error) {
    setLoginNotice(
      error instanceof Error && error.message
        ? error.message
        : "Não foi possível entrar.",
      "error",
    );
  } finally {
    submit.disabled = false;
  }
});

logoutButton.addEventListener("click", async () => {
  try {
    await fetch("/api/logout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
  } finally {
    setLocked(true);
    setLoginNotice("Sessão encerrada.");
  }
});

document.querySelectorAll(".filter").forEach((control) => {
  control.addEventListener("click", () => {
    state.filter = control.dataset.filter;
    document.querySelectorAll(".filter").forEach((item) => {
      item.classList.toggle("active", item === control);
    });
    render();
  });
});

refreshButton.addEventListener("click", load);
checkSession();
window.setInterval(load, 20000);
