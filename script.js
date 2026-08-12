const CONFIG = {
  spreadsheetUrl: "COLE_AQUI_O_LINK_CSV_PUBLICADO_DO_GOOGLE_SHEETS",
  refreshIntervalMs: 300000,
  affiliatePartners: {
    amazon: {
      label: "Amazon",
      hosts: ["amazon.com.br", "amzn.to"],
    },
    shopee: {
      label: "Shopee",
      hosts: ["shopee.com.br", "s.shopee.com.br"],
    },
    mercado_livre: {
      label: "Mercado Livre",
      hosts: ["mercadolivre.com.br", "meli.la"],
    },
    aliexpress: {
      label: "AliExpress",
      hosts: ["aliexpress.com", "s.click.aliexpress.com"],
    },
    shein: {
      label: "SHEIN",
      hosts: ["shein.com", "br.shein.com", "onelink.shein.com"],
    },
  },
};

(() => {
  "use strict";

  const CSV_HEADERS = Object.freeze([
    "id",
    "nome",
    "descricao_curta",
    "descricao",
    "categoria",
    "tipo",
    "preco",
    "preco_anterior",
    "imagem",
    "imagens",
    "loja",
    "link_afiliado",
    "destaque",
    "ativo",
  ]);

  class RowValidationError extends Error {
    constructor(fields) {
      super("Linha inválida.");
      this.fields = [...new Set(fields)].sort();
    }
  }

  function parseCsv(input) {
    const text = String(input ?? "").replace(/^\uFEFF/, "");
    const rows = [];
    let row = [];
    let field = "";
    let state = "FIELD";

    const finishField = () => {
      row.push(field);
      field = "";
    };
    const finishRow = () => {
      finishField();
      if (row.some((cell) => cell.trim() !== "")) rows.push(row);
      row = [];
    };

    for (let index = 0; index < text.length; index += 1) {
      const character = text[index];

      if (state === "QUOTED") {
        if (character === '"') {
          if (text[index + 1] === '"') {
            field += '"';
            index += 1;
          } else {
            state = "AFTER_QUOTE";
          }
        } else {
          field += character;
        }
        continue;
      }

      if (state === "AFTER_QUOTE") {
        if (character === ",") {
          finishField();
          state = "FIELD";
        } else if (character === "\r" || character === "\n") {
          finishRow();
          state = "FIELD";
          if (character === "\r" && text[index + 1] === "\n") index += 1;
        } else if (character !== " " && character !== "\t") {
          throw new Error("CSV inválido: conteúdo após aspas de fechamento.");
        }
        continue;
      }

      if (character === ",") {
        finishField();
      } else if (character === "\r" || character === "\n") {
        finishRow();
        if (character === "\r" && text[index + 1] === "\n") index += 1;
      } else if (character === '"') {
        if (field !== "") throw new Error("CSV inválido: aspas em campo não citado.");
        state = "QUOTED";
      } else {
        field += character;
      }
    }

    if (state === "QUOTED") throw new Error("CSV inválido: campo citado não foi fechado.");
    if (field !== "" || row.length > 0) finishRow();
    return rows;
  }

  function normalizeHost(value) {
    return String(value ?? "").trim().toLowerCase();
  }

  function isConfiguredHost(hostname, allowedHosts) {
    const host = normalizeHost(hostname);
    return allowedHosts.some((candidateValue) => {
      const candidate = normalizeHost(candidateValue);
      return candidate !== "" && (host === candidate || host.endsWith(`.${candidate}`));
    });
  }

  function parseHttpsUrl(raw) {
    if (typeof raw !== "string" || raw !== raw.trim() || raw.includes("\\")) return null;
    let url;
    try {
      url = new URL(raw);
    } catch {
      return null;
    }
    if (
      url.protocol !== "https:" ||
      url.username !== "" ||
      url.password !== "" ||
      url.port !== "" ||
      url.hostname === "" ||
      url.hostname.endsWith(".")
    ) {
      return null;
    }
    return url;
  }

  function validateImageUrl(raw) {
    return parseHttpsUrl(raw)?.href ?? null;
  }

  function validatePartnerUrl(raw, partnerKey) {
    const partner = CONFIG.affiliatePartners[partnerKey];
    if (!partner) return null;
    const url = parseHttpsUrl(raw);
    if (!url || !isConfiguredHost(url.hostname, partner.hosts)) return null;
    return url.href;
  }

  function parsePrice(raw, { optional = false } = {}) {
    const value = String(raw ?? "").trim();
    if (optional && value === "") return null;
    if (!/^(?:0|[1-9]\d*)\.\d{2}$/.test(value)) {
      throw new RowValidationError([optional ? "preco_anterior" : "preco"]);
    }
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      throw new RowValidationError([optional ? "preco_anterior" : "preco"]);
    }
    return parsed;
  }

  function parseBoolean(raw, field) {
    const value = String(raw ?? "").trim().toUpperCase();
    if (value === "TRUE") return true;
    if (value === "FALSE") return false;
    throw new RowValidationError([field]);
  }

  function required(record, field) {
    const value = String(record[field] ?? "").trim();
    if (!value) throw new RowValidationError([field]);
    return value;
  }

  function normalizeProduct(record) {
    const id = required(record, "id");
    if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(id)) throw new RowValidationError(["id"]);

    const name = required(record, "nome");
    const shortDescription = required(record, "descricao_curta");
    const description = String(record.descricao ?? "").trim();
    const category = required(record, "categoria");
    const type = required(record, "tipo");
    if (type !== "fisico" && type !== "digital") throw new RowValidationError(["tipo"]);

    const currentPrice = parsePrice(required(record, "preco"));
    const rawPreviousPrice = parsePrice(record.preco_anterior, { optional: true });
    const previousPrice = rawPreviousPrice !== null && rawPreviousPrice > currentPrice
      ? rawPreviousPrice
      : null;

    const primaryImage = validateImageUrl(required(record, "imagem"));
    if (!primaryImage) throw new RowValidationError(["imagem"]);
    const rawImages = String(record.imagens ?? "").trim();
    const images = rawImages === ""
      ? []
      : rawImages.split("|").map((entry) => {
          const image = validateImageUrl(entry.trim());
          if (!image) throw new RowValidationError(["imagens"]);
          return image;
        });

    const partner = required(record, "loja");
    if (!Object.hasOwn(CONFIG.affiliatePartners, partner)) throw new RowValidationError(["loja"]);
    const affiliateUrl = validatePartnerUrl(required(record, "link_afiliado"), partner);
    if (!affiliateUrl) throw new RowValidationError(["link_afiliado"]);

    return Object.freeze({
      id,
      name,
      shortDescription,
      description,
      category,
      type,
      currentPrice,
      previousPrice,
      primaryImage,
      images: Object.freeze(images),
      partner,
      affiliateUrl,
      featured: parseBoolean(record.destaque, "destaque"),
      active: parseBoolean(record.ativo, "ativo"),
    });
  }

  function normalizeRows(rows) {
    if (!Array.isArray(rows) || rows.length === 0) throw new Error("Cabeçalho CSV ausente.");
    const header = rows[0].map((cell) => String(cell).trim());
    const headerIsExact =
      header.length === CSV_HEADERS.length &&
      CSV_HEADERS.every((expected, index) => header[index] === expected);
    if (!headerIsExact) throw new Error("Cabeçalho CSV inválido.");

    const products = [];
    const rejected = [];
    const seenIds = new Set();

    rows.slice(1).forEach((cells, index) => {
      const rowNumber = index + 2;
      const values = Array.isArray(cells) ? cells : [];
      const record = Object.fromEntries(
        CSV_HEADERS.map((headerName, headerIndex) => [headerName, values[headerIndex] ?? ""]),
      );
      const safeId = /^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(String(record.id).trim())
        ? String(record.id).trim()
        : undefined;
      try {
        if (values.length > CSV_HEADERS.length && values.slice(CSV_HEADERS.length).some(String)) {
          throw new RowValidationError([]);
        }
        const product = normalizeProduct(record);
        if (seenIds.has(product.id)) throw new RowValidationError(["id"]);
        seenIds.add(product.id);
        products.push(product);
      } catch (error) {
        rejected.push(Object.freeze({
          row: rowNumber,
          ...(safeId ? { id: safeId } : {}),
          code: "INVALID_ROW",
          fields: error instanceof RowValidationError ? error.fields : [],
        }));
      }
    });

    return Object.freeze({
      products: Object.freeze(products),
      rejected: Object.freeze(rejected),
    });
  }

  function calculateDiscount(currentPrice, previousPrice) {
    if (
      !Number.isFinite(currentPrice) ||
      currentPrice <= 0 ||
      !Number.isFinite(previousPrice) ||
      previousPrice <= currentPrice
    ) {
      return null;
    }
    return Math.round(((previousPrice - currentPrice) / previousPrice) * 100);
  }

  function searchable(value) {
    return String(value ?? "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  }

  function partnerLabel(partnerKey) {
    return CONFIG.affiliatePartners[partnerKey]?.label ?? partnerKey;
  }

  function filterProducts(products, filters = {}) {
    const queryTokens = searchable(filters.query).split(" ").filter(Boolean);
    const category = searchable(filters.category);
    const type = String(filters.type ?? "").trim();
    return products.filter((product) => {
      const haystack = searchable([
        product.name,
        product.shortDescription,
        product.description,
        product.category,
        product.partner,
        partnerLabel(product.partner),
      ].join(" "));
      return (
        queryTokens.every((token) => haystack.includes(token)) &&
        (!category || searchable(product.category) === category) &&
        (!type || product.type === type)
      );
    });
  }

  function demoImage(label, accent) {
    const safeLabel = String(label).replace(/[<>&"']/g, "");
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="720" viewBox="0 0 960 720"><rect width="960" height="720" rx="48" fill="#eef0ff"/><circle cx="720" cy="170" r="170" fill="${accent}" opacity=".17"/><circle cx="230" cy="570" r="210" fill="#635BFF" opacity=".12"/><path d="M290 220h380a56 56 0 0 1 56 56v168a56 56 0 0 1-56 56H290a56 56 0 0 1-56-56V276a56 56 0 0 1 56-56Z" fill="#fff" stroke="#0B1020" stroke-width="14"/><text x="480" y="375" text-anchor="middle" font-family="system-ui,sans-serif" font-size="44" font-weight="700" fill="#0B1020">${safeLabel}</text></svg>`;
    return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
  }

  const DEMO_PRODUCTS = Object.freeze([
    ["demo-fone", "Fone Essencial", "Áudio confortável para a rotina.", "Eletrônicos", "fisico", 149.9, 199.9, "amazon", true, "Fone"],
    ["demo-teclado", "Teclado Horizonte", "Formato compacto e toque preciso.", "Eletrônicos", "fisico", 219.9, null, "mercado_livre", true, "Teclado"],
    ["demo-jaqueta", "Jaqueta Brisa", "Camada leve para dias versáteis.", "Moda", "fisico", 189.9, 239.9, "shein", true, "Jaqueta"],
    ["demo-game", "Jogo Nebulosa", "Aventura digital de exploração.", "Games", "digital", 79.9, 109.9, "aliexpress", false, "Game"],
    ["demo-luminaria", "Luminária Arco", "Luz ajustável para estudo e leitura.", "Casa", "fisico", 89.9, null, "shopee", true, "Luz"],
    ["demo-mochila", "Mochila Traço", "Organização discreta para o dia a dia.", "Moda", "fisico", 129.9, 169.9, "amazon", false, "Mochila"],
    ["demo-app", "Aplicativo Foco", "Planejamento simples em qualquer tela.", "Aplicativos", "digital", 29.9, null, "mercado_livre", false, "App"],
    ["demo-controle", "Controle Pulso", "Resposta precisa para jogar melhor.", "Games", "fisico", 249.9, 299.9, "shopee", true, "Controle"],
    ["demo-curso", "Guia de Fotografia", "Conteúdo digital para novos olhares.", "Educação", "digital", 59.9, 89.9, "aliexpress", false, "Guia"],
    ["demo-relogio", "Relógio Aurora", "Design limpo com recursos essenciais.", "Acessórios", "fisico", 179.9, null, "shein", false, "Relógio"],
  ].map(([id, name, shortDescription, category, type, currentPrice, previousPrice, partner, featured, label], index) => Object.freeze({
    id,
    name,
    shortDescription,
    description: `${shortDescription} Produto fictício usado somente para demonstrar o layout da Orvani.`,
    category,
    type,
    currentPrice,
    previousPrice,
    primaryImage: demoImage(label, index % 2 === 0 ? "#635BFF" : "#FF6B4A"),
    images: Object.freeze([]),
    partner,
    affiliateUrl: `https://${CONFIG.affiliatePartners[partner].hosts[0]}/`,
    featured,
    active: true,
    demo: true,
  })));

  const OrvaniCore = Object.freeze({
    CONFIG,
    CSV_HEADERS,
    DEMO_PRODUCTS,
    parseCsv,
    normalizeRows,
    validateImageUrl,
    validatePartnerUrl,
    calculateDiscount,
    filterProducts,
    partnerLabel,
  });

  globalThis.OrvaniCore = OrvaniCore;

  if (typeof document !== "undefined") {
    const currencyFormatter = new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    });

    const fallbackImage = demoImage("Orvani", "#635BFF");
    const state = {
      products: [],
      filters: { query: "", category: "", type: "" },
      demo: false,
    };
    const reducedMotionQuery = globalThis.matchMedia("(prefers-reduced-motion: reduce)");
    let carouselController = null;
    let revealObserver = null;
    let refreshTimer = null;
    let lastFetchAt = 0;
    let loadPromise = null;

    function element(tagName, className, text) {
      const node = document.createElement(tagName);
      if (className) node.className = className;
      if (text !== undefined) node.textContent = text;
      return node;
    }

    function productImage(product, { eager = false } = {}) {
      const wrapper = element("div", "product-image-wrap");
      const image = document.createElement("img");
      image.src = product.primaryImage;
      image.alt = product.name;
      image.width = 960;
      image.height = 720;
      image.decoding = "async";
      image.loading = eager ? "eager" : "lazy";
      image.addEventListener("error", () => {
        if (image.src !== fallbackImage) image.src = fallbackImage;
      }, { once: true });
      wrapper.append(image);
      return wrapper;
    }

    function offerLink(product, className = "button button-primary offer-link") {
      const link = element("a", className, `Ver oferta na ${partnerLabel(product.partner)}`);
      link.href = product.affiliateUrl;
      link.target = "_blank";
      link.rel = "sponsored nofollow noopener noreferrer";
      link.setAttribute("aria-label", `Ver oferta de ${product.name} na ${partnerLabel(product.partner)}`);
      return link;
    }

    function priceBlock(product) {
      const container = element("div", "price-block");
      const current = element("strong", "current-price", currencyFormatter.format(product.currentPrice));
      const discount = calculateDiscount(product.currentPrice, product.previousPrice);
      if (discount !== null) {
        const previous = element("del", "previous-price", currencyFormatter.format(product.previousPrice));
        previous.setAttribute("aria-label", `Preço anterior: ${currencyFormatter.format(product.previousPrice)}`);
        const badge = element("span", "discount-badge", `-${discount}%`);
        container.append(previous, current, badge);
      } else {
        container.append(current);
      }
      return container;
    }

    function createProductCard(product, index) {
      const card = element("article", "product-card reveal");
      card.dataset.productId = product.id;
      card.append(productImage(product, { eager: index < 4 }));

      const body = element("div", "product-card-body");
      const meta = element("div", "product-meta");
      meta.append(
        element("span", "category-label", product.category),
        element("span", "partner-label", partnerLabel(product.partner)),
      );
      const title = element("h3", "product-title", product.name);
      const description = element("p", "product-description", product.shortDescription);
      const footer = element("div", "product-card-footer");
      footer.append(priceBlock(product), offerLink(product));
      body.append(meta, title, description, footer);
      card.append(body);
      return card;
    }

    function createFeaturedSlide(product, index, total) {
      const slide = element("article", "carousel-slide");
      slide.dataset.slideIndex = String(index);
      slide.setAttribute("role", "group");
      slide.setAttribute("aria-roledescription", "slide");
      slide.setAttribute("aria-label", `${index + 1} de ${total}`);
      const content = element("div", "featured-content");
      content.append(
        element("span", "featured-partner", partnerLabel(product.partner)),
        element("h3", "featured-title", product.name),
        element("p", "featured-description", product.shortDescription),
        priceBlock(product),
        offerLink(product),
      );
      slide.append(productImage(product, { eager: index === 0 }), content);
      return slide;
    }

    function renderFeatured(products) {
      const featured = products.filter((product) => product.featured);
      const section = document.querySelector("#destaques");
      const track = document.querySelector("#carousel-track");
      const controls = document.querySelector("#carousel-controls");
      const indicators = document.querySelector("#carousel-indicators");
      if (!section || !track || !controls || !indicators) return;
      carouselController?.destroy();
      carouselController = null;
      section.hidden = featured.length === 0;
      track.replaceChildren(...featured.map((product, index) =>
        createFeaturedSlide(product, index, featured.length)));
      indicators.replaceChildren(...featured.map((product, index) => {
        const button = element("button", "carousel-indicator");
        button.type = "button";
        button.setAttribute("aria-label", `Ir para ${product.name}`);
        button.dataset.slideTarget = String(index);
        return button;
      }));
      controls.hidden = featured.length <= 1;
      if (featured.length > 0) carouselController = createCarousel(featured);
    }

    function createCarousel(products) {
      const root = document.querySelector("#featured-carousel");
      const viewport = document.querySelector("#carousel-viewport");
      const track = document.querySelector("#carousel-track");
      const previousButton = document.querySelector("#carousel-prev");
      const nextButton = document.querySelector("#carousel-next");
      const live = document.querySelector("#carousel-live");
      if (!root || !viewport || !track || !previousButton || !nextButton || !live) {
        return { destroy() {} };
      }

      const slides = [...track.querySelectorAll(".carousel-slide")];
      const indicators = [...root.querySelectorAll(".carousel-indicator")];
      const pauseReasons = new Set();
      let currentIndex = 0;
      let timer = null;
      let pointerId = null;
      let pointerStartX = 0;
      let pointerDeltaX = 0;

      root.tabIndex = 0;

      function clearTimer() {
        if (timer !== null) globalThis.clearTimeout(timer);
        timer = null;
      }

      function schedule() {
        clearTimer();
        if (slides.length <= 1 || reducedMotionQuery.matches || pauseReasons.size > 0) return;
        timer = globalThis.setTimeout(() => {
          goTo(currentIndex + 1, { userInitiated: false });
          schedule();
        }, 6000);
      }

      function update({ userInitiated = false } = {}) {
        root.dataset.carouselIndex = String(currentIndex);
        track.style.transform = `translate3d(${-currentIndex * 100}%, 0, 0)`;
        slides.forEach((slide, index) => {
          const active = index === currentIndex;
          slide.setAttribute("aria-hidden", String(!active));
          slide.toggleAttribute("inert", !active);
        });
        indicators.forEach((indicator, index) => {
          if (index === currentIndex) indicator.setAttribute("aria-current", "true");
          else indicator.removeAttribute("aria-current");
        });
        if (userInitiated) live.textContent = `${products[currentIndex].name}, destaque ${currentIndex + 1} de ${slides.length}`;
      }

      function goTo(index, { userInitiated = true } = {}) {
        currentIndex = (index + slides.length) % slides.length;
        update({ userInitiated });
        if (userInitiated) schedule();
      }

      function pause(reason) {
        pauseReasons.add(reason);
        clearTimer();
      }

      function resume(reason) {
        pauseReasons.delete(reason);
        schedule();
      }

      const onPrevious = () => goTo(currentIndex - 1);
      const onNext = () => goTo(currentIndex + 1);
      const onKeydown = (event) => {
        if (event.key === "ArrowLeft") {
          event.preventDefault();
          goTo(currentIndex - 1);
        } else if (event.key === "ArrowRight") {
          event.preventDefault();
          goTo(currentIndex + 1);
        }
      };
      const onMouseEnter = () => pause("hover");
      const onMouseLeave = () => resume("hover");
      const onFocusIn = () => pause("focus");
      const onFocusOut = (event) => {
        if (!root.contains(event.relatedTarget)) resume("focus");
      };
      const onPointerDown = (event) => {
        if (slides.length <= 1) return;
        pointerId = event.pointerId;
        pointerStartX = event.clientX;
        pointerDeltaX = 0;
        viewport.setPointerCapture?.(pointerId);
        viewport.classList.add("is-dragging");
        pause("pointer");
      };
      const onPointerMove = (event) => {
        if (event.pointerId !== pointerId) return;
        pointerDeltaX = event.clientX - pointerStartX;
        if (Math.abs(pointerDeltaX) > 8) event.preventDefault();
      };
      const finishPointer = (event) => {
        if (event.pointerId !== pointerId) return;
        if (Math.abs(pointerDeltaX) >= 48) {
          goTo(currentIndex + (pointerDeltaX < 0 ? 1 : -1));
        }
        viewport.releasePointerCapture?.(pointerId);
        viewport.classList.remove("is-dragging");
        pointerId = null;
        pointerDeltaX = 0;
        resume("pointer");
      };
      const onVisibilityChange = () => {
        if (document.hidden) pause("visibility");
        else resume("visibility");
      };
      const onMotionChange = () => {
        if (reducedMotionQuery.matches) pause("motion");
        else resume("motion");
      };

      previousButton.addEventListener("click", onPrevious);
      nextButton.addEventListener("click", onNext);
      indicators.forEach((indicator, index) => {
        indicator.addEventListener("click", () => goTo(index));
      });
      root.addEventListener("keydown", onKeydown);
      root.addEventListener("mouseenter", onMouseEnter);
      root.addEventListener("mouseleave", onMouseLeave);
      root.addEventListener("focusin", onFocusIn);
      root.addEventListener("focusout", onFocusOut);
      viewport.addEventListener("pointerdown", onPointerDown);
      viewport.addEventListener("pointermove", onPointerMove);
      viewport.addEventListener("pointerup", finishPointer);
      viewport.addEventListener("pointercancel", finishPointer);
      document.addEventListener("visibilitychange", onVisibilityChange);
      reducedMotionQuery.addEventListener?.("change", onMotionChange);

      update();
      schedule();

      return {
        goTo,
        next: onNext,
        previous: onPrevious,
        pause,
        resume,
        destroy() {
          clearTimer();
          previousButton.removeEventListener("click", onPrevious);
          nextButton.removeEventListener("click", onNext);
          root.removeEventListener("keydown", onKeydown);
          root.removeEventListener("mouseenter", onMouseEnter);
          root.removeEventListener("mouseleave", onMouseLeave);
          root.removeEventListener("focusin", onFocusIn);
          root.removeEventListener("focusout", onFocusOut);
          viewport.removeEventListener("pointerdown", onPointerDown);
          viewport.removeEventListener("pointermove", onPointerMove);
          viewport.removeEventListener("pointerup", finishPointer);
          viewport.removeEventListener("pointercancel", finishPointer);
          document.removeEventListener("visibilitychange", onVisibilityChange);
          reducedMotionQuery.removeEventListener?.("change", onMotionChange);
        },
      };
    }

    function categoriesFrom(products) {
      return [...new Set(products.map((product) => product.category))]
        .sort((left, right) => left.localeCompare(right, "pt-BR"));
    }

    function renderCategories(products) {
      const categories = categoriesFrom(products);
      const list = document.querySelector("#category-list");
      const select = document.querySelector("#category-filter");
      if (!list || !select) return;

      list.replaceChildren(...categories.map((category) => {
        const count = products.filter((product) => product.category === category).length;
        const button = element("button", "category-chip");
        button.type = "button";
        button.dataset.category = category;
        button.append(
          element("span", "category-chip-name", category),
          element("span", "category-chip-count", String(count)),
        );
        button.addEventListener("click", () => {
          state.filters.category = category;
          select.value = category;
          renderFilteredProducts();
          document.querySelector("#catalogo")?.scrollIntoView({ block: "start" });
        });
        return button;
      }));

      const allOption = element("option", "", "Todas");
      allOption.value = "";
      select.replaceChildren(allOption, ...categories.map((category) => {
        const option = element("option", "", category);
        option.value = category;
        return option;
      }));
      select.value = state.filters.category;
    }

    function setVisibility(selector, visible) {
      const node = document.querySelector(selector);
      if (node) node.hidden = !visible;
    }

    function renderFilteredProducts() {
      const activeProducts = state.products.filter((product) => product.active);
      const filtered = filterProducts(activeProducts, state.filters);
      const grid = document.querySelector("#product-grid");
      const count = document.querySelector("#result-count");
      if (!grid || !count) return;

      grid.replaceChildren(...filtered.map(createProductCard));
      count.textContent = `${filtered.length} ${filtered.length === 1 ? "produto" : "produtos"}`;
      setVisibility("#no-results", activeProducts.length > 0 && filtered.length === 0);
      setVisibility("#empty-catalog", activeProducts.length === 0);
      setVisibility("#product-grid", filtered.length > 0);
      observeReveals(grid);
    }

    function setProducts(products, { demo = false, resetFilters = true } = {}) {
      state.products = [...products];
      state.demo = demo;
      if (resetFilters) state.filters = { query: "", category: "", type: "" };
      const categories = categoriesFrom(state.products.filter((product) => product.active));
      if (state.filters.category && !categories.includes(state.filters.category)) {
        state.filters.category = "";
      }
      const search = document.querySelector("#catalog-search");
      const category = document.querySelector("#category-filter");
      const type = document.querySelector("#type-filter");
      if (search) search.value = state.filters.query;
      if (category) category.value = state.filters.category;
      if (type) type.value = state.filters.type;
      setVisibility("#catalog-state", false);
      setVisibility("#load-error", false);
      setVisibility("#demo-note", demo);
      const activeProducts = state.products.filter((product) => product.active);
      renderFeatured(activeProducts);
      renderCategories(activeProducts);
      renderFilteredProducts();
    }

    function isDemoConfiguration() {
      return CONFIG.spreadsheetUrl === "COLE_AQUI_O_LINK_CSV_PUBLICADO_DO_GOOGLE_SHEETS";
    }

    function hasActiveCatalog() {
      return state.products.some((product) => product.active);
    }

    function clearRefreshTimer() {
      if (refreshTimer !== null) globalThis.clearTimeout(refreshTimer);
      refreshTimer = null;
    }

    function scheduleRefresh(delay = CONFIG.refreshIntervalMs) {
      clearRefreshTimer();
      if (isDemoConfiguration() || document.hidden) return;
      refreshTimer = globalThis.setTimeout(() => {
        loadCatalog({ background: true });
      }, Math.max(0, delay));
    }

    function showLoading() {
      const hasCatalog = hasActiveCatalog();
      setVisibility("#catalog-state", !hasCatalog);
      setVisibility("#load-error", false);
      if (!hasCatalog) {
        setVisibility("#empty-catalog", false);
        setVisibility("#no-results", false);
        setVisibility("#product-grid", false);
        const count = document.querySelector("#result-count");
        if (count) count.textContent = "Carregando catálogo…";
      }
    }

    function showLoadError() {
      const hasCatalog = hasActiveCatalog();
      const panel = document.querySelector("#load-error");
      const title = document.querySelector("#load-error-title");
      const copy = document.querySelector("#load-error-copy");
      const retry = document.querySelector("#retry-button");
      setVisibility("#catalog-state", false);
      setVisibility("#load-error", true);
      panel?.classList.toggle("is-update-warning", hasCatalog);
      if (title) {
        title.textContent = hasCatalog
          ? "A última atualização não foi concluída."
          : "O catálogo está temporariamente indisponível.";
      }
      if (copy) {
        copy.textContent = hasCatalog
          ? "Você ainda está vendo o último catálogo válido. Tente atualizar novamente."
          : "Verifique sua conexão e tente novamente em instantes.";
      }
      if (retry) retry.textContent = hasCatalog ? "Atualizar novamente" : "Tentar novamente";
      if (!hasCatalog) {
        setVisibility("#product-grid", false);
        setVisibility("#empty-catalog", false);
        setVisibility("#no-results", false);
        const count = document.querySelector("#result-count");
        if (count) count.textContent = "Catálogo indisponível";
      }
    }

    async function performCatalogLoad({ background = false } = {}) {
      const spreadsheet = parseHttpsUrl(CONFIG.spreadsheetUrl);
      if (!spreadsheet) {
        showLoadError();
        return;
      }

      if (!background) showLoading();
      lastFetchAt = Date.now();
      try {
        const response = await globalThis.fetch(spreadsheet.href, { cache: "no-store" });
        if (!response.ok) throw new Error("CATALOG_HTTP_ERROR");
        const parsed = normalizeRows(parseCsv(await response.text()));
        parsed.rejected.forEach((rejection) => {
          console.warn("Linha do catálogo rejeitada.", {
            row: rejection.row,
            ...(rejection.id ? { id: rejection.id } : {}),
            code: rejection.code,
            fields: rejection.fields,
          });
        });
        setProducts(parsed.products, {
          demo: false,
          resetFilters: !hasActiveCatalog(),
        });
      } catch {
        showLoadError();
      } finally {
        scheduleRefresh();
      }
    }

    function loadCatalog(options = {}) {
      if (isDemoConfiguration()) {
        setProducts(DEMO_PRODUCTS, { demo: true });
        return Promise.resolve();
      }
      if (loadPromise) return loadPromise;
      loadPromise = performCatalogLoad(options).finally(() => {
        loadPromise = null;
      });
      return loadPromise;
    }

    function bindFilters() {
      const search = document.querySelector("#catalog-search");
      const category = document.querySelector("#category-filter");
      const type = document.querySelector("#type-filter");
      const clear = document.querySelector("#clear-filters");
      search?.addEventListener("input", () => {
        state.filters.query = search.value;
        renderFilteredProducts();
      });
      category?.addEventListener("change", () => {
        state.filters.category = category.value;
        renderFilteredProducts();
      });
      type?.addEventListener("change", () => {
        state.filters.type = type.value;
        renderFilteredProducts();
      });
      clear?.addEventListener("click", () => {
        state.filters = { query: "", category: "", type: "" };
        if (search) search.value = "";
        if (category) category.value = "";
        if (type) type.value = "";
        renderFilteredProducts();
        search?.focus();
      });
    }

    function bindCatalogLoading() {
      document.querySelector("#retry-button")?.addEventListener("click", () => {
        loadCatalog({ background: hasActiveCatalog() });
      });
      document.addEventListener("visibilitychange", () => {
        if (isDemoConfiguration()) return;
        if (document.hidden) {
          clearRefreshTimer();
          return;
        }
        const elapsed = Date.now() - lastFetchAt;
        if (elapsed >= CONFIG.refreshIntervalMs) loadCatalog({ background: hasActiveCatalog() });
        else scheduleRefresh(CONFIG.refreshIntervalMs - elapsed);
      });
    }

    function setupMobileMenu() {
      const toggle = document.querySelector("#menu-toggle");
      const menu = document.querySelector("#mobile-menu");
      if (!toggle || !menu) return;
      let closingTimer = null;

      function openMenu() {
        if (closingTimer !== null) globalThis.clearTimeout(closingTimer);
        menu.hidden = false;
        toggle.setAttribute("aria-expanded", "true");
        toggle.setAttribute("aria-label", "Fechar menu");
        globalThis.requestAnimationFrame(() => menu.classList.add("is-open"));
      }

      function closeMenu({ restoreFocus = false } = {}) {
        menu.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
        toggle.setAttribute("aria-label", "Abrir menu");
        if (closingTimer !== null) globalThis.clearTimeout(closingTimer);
        if (reducedMotionQuery.matches) menu.hidden = true;
        else closingTimer = globalThis.setTimeout(() => { menu.hidden = true; }, 180);
        if (restoreFocus) toggle.focus();
      }

      toggle.addEventListener("click", () => {
        if (toggle.getAttribute("aria-expanded") === "true") closeMenu();
        else openMenu();
      });
      menu.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => closeMenu()));
      document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
          closeMenu({ restoreFocus: true });
        }
      });
      document.addEventListener("pointerdown", (event) => {
        if (
          toggle.getAttribute("aria-expanded") === "true" &&
          !menu.contains(event.target) &&
          !toggle.contains(event.target)
        ) {
          closeMenu();
        }
      });
    }

    function observeReveals(scope = document) {
      const nodes = scope.querySelectorAll?.(".reveal:not(.is-visible)") ?? [];
      if (reducedMotionQuery.matches || !revealObserver) {
        nodes.forEach((node) => node.classList.add("is-visible"));
        return;
      }
      nodes.forEach((node) => revealObserver.observe(node));
    }

    function setupRevealObserver() {
      if (reducedMotionQuery.matches || !("IntersectionObserver" in globalThis)) {
        observeReveals(document);
        return;
      }
      document.body.classList.add("motion-ready");
      revealObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          revealObserver.unobserve(entry.target);
        });
      }, { rootMargin: "0px 0px -8%", threshold: 0.08 });
      observeReveals(document);
    }

    function initializeApp() {
      bindFilters();
      bindCatalogLoading();
      setupMobileMenu();
      setupRevealObserver();
      loadCatalog();
    }

    globalThis.OrvaniApp = Object.freeze({ loadCatalog, setProducts, renderFilteredProducts });
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", initializeApp, { once: true });
    } else {
      initializeApp();
    }
  }
})();
