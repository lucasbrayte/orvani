// Orvani Apps Script Web App bridge.

function orvaniCanonicalJson_(value) {
  if (value === null) return "null";

  if (Array.isArray(value)) {
    return "[" + value.map(orvaniCanonicalJson_).join(",") + "]";
  }

  if (typeof value === "object") {
    const keys = Object.keys(value).sort();
    return "{" + keys.map(
      (key) => JSON.stringify(key) + ":" + orvaniCanonicalJson_(value[key])
    ).join(",") + "}";
  }

  if (typeof value === "string" || typeof value === "boolean") {
    return JSON.stringify(value);
  }

  if (typeof value === "number" && Number.isFinite(value)) {
    return JSON.stringify(value);
  }

  throw new Error("Valor não canônico.");
}

function orvaniUnsignedEnvelope_(envelope) {
  return {
    version: envelope.version,
    action: envelope.action,
    timestamp: envelope.timestamp,
    nonce: envelope.nonce,
    payload: envelope.payload,
  };
}

function orvaniConstantTimeEqual_(left, right) {
  if (typeof left !== "string" || typeof right !== "string") {
    return false;
  }

  if (left.length !== right.length) {
    return false;
  }

  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

function orvaniVerifyEnvelopeCore_(
  envelope,
  secret,
  nowSeconds,
  hmacHexFn,
  nonceAcceptFn
) {
  if (!envelope || envelope.version !== "v1") {
    throw new Error("Versão de protocolo inválida.");
  }

  if (!Number.isInteger(envelope.timestamp)) {
    throw new Error("Timestamp inválido.");
  }

  if (Math.abs(nowSeconds - envelope.timestamp) > 120) {
    throw new Error("Timestamp fora da janela.");
  }

  if (
    typeof envelope.nonce !== "string" ||
    !/^[A-Za-z0-9_-]{16,128}$/.test(envelope.nonce)
  ) {
    throw new Error("Nonce inválido.");
  }

  if (
    typeof envelope.signature !== "string" ||
    !/^[0-9a-f]{64}$/.test(envelope.signature)
  ) {
    throw new Error("Assinatura inválida.");
  }

  const canonical = orvaniCanonicalJson_(
    orvaniUnsignedEnvelope_(envelope)
  );
  const expected = hmacHexFn(secret, canonical);

  if (!orvaniConstantTimeEqual_(expected, envelope.signature)) {
    throw new Error("Assinatura inválida.");
  }

  if (!nonceAcceptFn(envelope.nonce)) {
    throw new Error("Nonce já utilizado.");
  }

  return envelope;
}

function orvaniHmacHex_(secret, text) {
  const bytes = Utilities.computeHmacSha256Signature(
    text,
    secret,
    Utilities.Charset.UTF_8
  );

  return bytes.map((value) => {
    const byte = value < 0 ? value + 256 : value;
    return byte.toString(16).padStart(2, "0");
  }).join("");
}

const ORVANI_CLIENT_FIELDS_ = Object.freeze([
  "ID Automação",
  "Ativo",
  "Publicar",
  "Destaque",
  "Ordem",
  "Modo de Atualização",
  "Link do Produto",
  "Link de Afiliado",
  "Plataforma",
  "Nome",
  "Descrição",
  "Categoria",
  "Subcategoria",
  "Tipo",
  "Preço Atual",
  "Preço Anterior",
  "Cupom",
  "Validade do Cupom",
  "Imagem 1",
  "Imagem 2",
  "Imagem 3",
  "Imagem 4",
  "Texto do Botão",
]);

function orvaniValidateUpsertProduct_(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Produto inválido.");
  }

  const allowed = new Set(ORVANI_CLIENT_FIELDS_);
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) {
      throw new Error("Campo não permitido: " + key);
    }
  }

  if (
    typeof value["ID Automação"] !== "string" ||
    !value["ID Automação"].trim()
  ) {
    throw new Error("ID Automação inválido.");
  }

  for (const field of ["Ativo", "Publicar", "Destaque"]) {
    if (!["Sim", "Não"].includes(value[field])) {
      throw new Error(field + " deve ser Sim ou Não.");
    }
  }

  if (
    !["Automático", "Manual", "Bloqueado"].includes(
      value["Modo de Atualização"]
    )
  ) {
    throw new Error("Modo de Atualização inválido.");
  }

  const textFields = [
    "Link do Produto",
    "Link de Afiliado",
    "Plataforma",
    "Nome",
    "Descrição",
    "Categoria",
    "Subcategoria",
    "Tipo",
    "Cupom",
    "Validade do Cupom",
    "Imagem 1",
    "Imagem 2",
    "Imagem 3",
    "Imagem 4",
    "Texto do Botão",
  ];

  for (const field of textFields) {
    if (!Object.prototype.hasOwnProperty.call(value, field)) {
      continue;
    }

    if (typeof value[field] !== "string") {
      throw new Error(field + " deve ser texto.");
    }

    if (value[field].length > 10000) {
      throw new Error(field + " excede o tamanho máximo de 10000 caracteres.");
    }
  }

  if (
    Object.prototype.hasOwnProperty.call(value, "Preço Atual") &&
    (
      typeof value["Preço Atual"] !== "number" ||
      !Number.isFinite(value["Preço Atual"]) ||
      value["Preço Atual"] <= 0
    )
  ) {
    throw new Error("Preço Atual deve ser positivo.");
  }

  const result = {};
  for (const key of ORVANI_CLIENT_FIELDS_) {
    if (Object.prototype.hasOwnProperty.call(value, key)) {
      result[key] = value[key];
    }
  }

  return result;
}

function orvaniPayloadKeysExactly_(payload, allowedKeys) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("Payload inválido.");
  }

  const allowed = new Set(allowedKeys);
  for (const key of Object.keys(payload)) {
    if (!allowed.has(key)) {
      throw new Error("Campo de payload não permitido: " + key);
    }
  }

  for (const key of allowedKeys) {
    if (!Object.prototype.hasOwnProperty.call(payload, key)) {
      throw new Error("Campo de payload obrigatório ausente: " + key);
    }
  }

  return payload;
}

function orvaniValidateActionPayload_(action, payload) {
  if (action === "upsert_products") {
    orvaniPayloadKeysExactly_(payload, ["products"]);

    if (
      !Array.isArray(payload.products) ||
      payload.products.length < 1 ||
      payload.products.length > 50
    ) {
      throw new Error("products deve conter entre 1 e 50 produtos.");
    }

    return {
      products: payload.products.map(orvaniValidateUpsertProduct_),
    };
  }

  if (action === "get_status") {
    orvaniPayloadKeysExactly_(payload, ["ids"]);

    if (
      !Array.isArray(payload.ids) ||
      payload.ids.length < 1 ||
      payload.ids.length > 100
    ) {
      throw new Error("Entre 1 e 100 IDs são obrigatórios.");
    }

    const normalizedIds = payload.ids.map((id) => {
      if (typeof id !== "string" || !id.trim()) {
        throw new Error("ID inválido.");
      }
      return id.trim();
    });

    if (new Set(normalizedIds).size !== normalizedIds.length) {
      throw new Error("ID duplicado no payload.");
    }

    return {
      ids: normalizedIds,
    };
  }

  if (action === "health") {
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new Error("Payload inválido.");
    }

    const keys = Object.keys(payload);
    if (keys.length !== 0) {
      throw new Error("Campo de payload não permitido: " + keys[0]);
    }

    return payload;
  }

  throw new Error("Ação não suportada.");
}
