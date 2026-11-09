/** Sliding windows for a single long-running Next process (the Compose web service).
 * Reservations are synchronous and never refunded: concurrent/failing calls count too.
 * Move this state to a shared store BEFORE running multiple web replicas/serverless.
 */
type Reservation = { at: number; tokens: number };
type Client = { minute: number[]; day: number[] };
export class OverviewLimiter {
  minute: Reservation[] = [];
  day: Reservation[] = [];
  clients = new Map<string, Client>();
  blockedUntil = 0;

  reserve(client: string, tokens: number, now = Date.now()): number {
    this.minute = this.minute.filter((entry) => entry.at > now - 60_000);
    this.day = this.day.filter((entry) => entry.at > now - 86_400_000);
    // Expire client records and bound memory. Unknown clients fail closed at capacity.
    for (const [key, value] of this.clients) {
      if (!value.day.some((at) => at > now - 86_400_000)) this.clients.delete(key);
    }
    const user = this.clients.get(client) ?? { minute: [], day: [] };
    user.minute = user.minute.filter((at) => at > now - 60_000);
    user.day = user.day.filter((at) => at > now - 86_400_000);
    const waits = [this.blockedUntil - now];
    const check = (entries: Reservation[], duration: number, requests: number, budget: number) => {
      let count = entries.length;
      let used = entries.reduce((sum, entry) => sum + entry.tokens, 0);
      for (const entry of entries) {
        if (count < requests && used + tokens <= budget) break;
        waits.push(entry.at + duration - now);
        count--; used -= entry.tokens;
      }
      if (tokens > budget) waits.push(duration);
    };
    check(this.minute, 60_000, 20, 5000);
    check(this.day, 86_400_000, 1000, 400_000);
    if (user.minute.length >= 3) waits.push(user.minute[0] + 60_000 - now);
    if (user.day.length >= 30) waits.push(user.day[0] + 86_400_000 - now);
    if (!this.clients.has(client) && this.clients.size >= 5000) waits.push(60_000);
    const retry = Math.ceil(Math.max(0, ...waits) / 1000);
    if (retry) return retry;
    this.minute.push({ at: now, tokens }); this.day.push({ at: now, tokens });
    user.minute.push(now); user.day.push(now); this.clients.set(client, user);
    return 0;
  }

  cooldown(seconds: number, now = Date.now()) {
    this.blockedUntil = Math.max(this.blockedUntil, now + seconds * 1000);
  }
}
