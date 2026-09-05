"use strict";
const state = { items: [], filter: "PENDENTE", loading: false };
const grid = document.getElementById("grid");
const notice = document.getElementById("notice");
const template = document.getElementById("card-template");
const refreshButton = document.getElementById("refresh");

function setNotice(message, kind = "") {
  notice.textContent = message;
  notice.className = `notice ${kind}`.trim();
}
function counts() {
  const result = { PENDENTE: 0, PUBLICADO: 0, ARQUIVADO: 0 };
  for (const item of state.items) if (Object.hasOwn(result, item.status)) result[item.status] += 1;
  document.getElementById("count-pendente").textContent = result.PENDENTE;
  document.getElementById("count-publicado").textContent = result.PUBLICADO;
  document.getElementById("count-arquivado").textContent = result.ARQUIVADO;
  document.getElementById("count-todos").textContent = state.items.length;
}
async function copyText(value, success) {
  try { await navigator.clipboard.writeText(value); setNotice(success, "success"); }
  catch { setNotice("Não foi possível copiar automaticamente.", "error"); }
}
async function setStatus(item, status) {
  try {
    const response = await fetch(`/api/items/${encodeURIComponent(item.id)}/status`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error("status");
    item.status = status; render(); setNotice("Status atualizado.", "success");
  } catch { setNotice("Não foi possível atualizar o status.", "error"); }
}
function button(card, action) { return card.querySelector(`[data-action="${action}"]`); }
function renderCard(item) {
  const card = template.content.firstElementChild.cloneNode(true);
  const imageLink = card.querySelector(".media");
  const image = card.querySelector("img");
  image.src = item.image; image.alt = item.name; imageLink.href = item.image;
  card.querySelector(".partner").textContent = item.partner || "Parceiro";
  const status = card.querySelector(".status"); status.textContent = item.status; status.dataset.status = item.status;
  card.querySelector("h2").textContent = item.name;
  card.querySelector(".description").textContent = item.description;
  card.querySelector(".price").textContent = item.price;
  card.querySelector(".affiliate").textContent = item.affiliateUrl;
  button(card, "whatsapp").href = "https://web.whatsapp.com/";
  button(card, "image").href = item.image;
  button(card, "copy-publication").addEventListener("click", () => copyText(item.publication, "Publicação copiada."));
  button(card, "copy-link").addEventListener("click", () => copyText(item.affiliateUrl, "Link afiliado copiado."));
  button(card, "published").addEventListener("click", () => setStatus(item, "PUBLICADO"));
  button(card, "pending").addEventListener("click", () => setStatus(item, "PENDENTE"));
  button(card, "archive").addEventListener("click", () => setStatus(item, "ARQUIVADO"));
  button(card, "published").hidden = item.status === "PUBLICADO";
  button(card, "pending").hidden = item.status === "PENDENTE";
  button(card, "archive").hidden = item.status === "ARQUIVADO";
  return card;
}
function render() {
  counts();
  const visible = state.items.filter((item) => state.filter === "TODOS" || item.status === state.filter);
  grid.replaceChildren(...visible.map(renderCard));
  if (!visible.length && !state.loading) setNotice(state.filter === "PENDENTE" ? "Nenhuma divulgação pendente." : "Nenhum item neste filtro.");
  else if (visible.length) setNotice("");
}
async function load() {
  if (state.loading) return;
  state.loading = true; refreshButton.disabled = true; setNotice("Atualizando fila…");
  try {
    const response = await fetch("/api/items", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok || !data.ok || !Array.isArray(data.items)) throw new Error(data.error || "Fila indisponível.");
    state.items = data.items; render();
  } catch (error) { setNotice(error instanceof Error && error.message ? error.message : "Fila backend ainda não está disponível.", "error"); }
  finally { state.loading = false; refreshButton.disabled = false; }
}
document.querySelectorAll(".filter").forEach((control) => control.addEventListener("click", () => {
  state.filter = control.dataset.filter;
  document.querySelectorAll(".filter").forEach((item) => item.classList.toggle("active", item === control));
  render();
}));
refreshButton.addEventListener("click", load);
load(); window.setInterval(load, 20000);
