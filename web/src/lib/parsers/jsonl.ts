/**
 * Minimal JSONL parser. Skips blank lines, surfaces parse errors with line context.
 * Designed to be pure so it works in both server and client contexts.
 */
export function parseJSONL<T>(text: string): T[] {
  const out: T[] = [];
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]?.trim();
    if (!line) continue;
    try {
      out.push(JSON.parse(line) as T);
    } catch (err) {
      const message = err instanceof Error ? err.message : "unknown";
      throw new Error(`JSONL parse error at line ${i + 1}: ${message}`);
    }
  }
  return out;
}
