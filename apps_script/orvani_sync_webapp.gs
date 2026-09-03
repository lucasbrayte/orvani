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
