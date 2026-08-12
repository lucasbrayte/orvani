type LimiterOptions = { max: number; windowMs: number };

export class SlidingWindowLimiter {
  private readonly attempts = new Map<string, number[]>();

  constructor(private readonly options: LimiterOptions) {
    if (options.max < 1 || options.windowMs < 1) throw new Error("Configuração de limite inválida.");
  }

  check(key: string, now: number): { allowed: boolean; retryAfterSeconds: number } {
    const recent = (this.attempts.get(key) ?? []).filter(
      (timestamp) => timestamp > now - this.options.windowMs,
    );
    if (recent.length >= this.options.max) {
      this.attempts.set(key, recent);
      return {
        allowed: false,
        retryAfterSeconds: Math.max(
          1,
          Math.ceil((recent[0] + this.options.windowMs - now) / 1_000),
        ),
      };
    }

    recent.push(now);
    this.attempts.set(key, recent);
    return { allowed: true, retryAfterSeconds: 0 };
  }
}
