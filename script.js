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
    // A inicialização da interface é adicionada no próximo checkpoint.
  }
})();
