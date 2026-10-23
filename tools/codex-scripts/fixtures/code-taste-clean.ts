// 正对照 · JS/TS 侧应当零命中（P0 = 0）

export interface ParsedLine {
  key: string;
  value: string;
}

export class LineError extends Error {}

export function parseLine(raw: string): ParsedLine {
  const index = raw.indexOf("=");
  if (index <= 0) {
    throw new LineError(`not a k=v line: ${raw.slice(0, 40)}`);
  }
  return { key: raw.slice(0, index).trim(), value: raw.slice(index + 1).trim() };
}

export function tallyKeys(lines: ParsedLine[]): Record<string, number> {
  const tally: Record<string, number> = {};
  for (const line of lines) {
    tally[line.key] = (tally[line.key] ?? 0) + 1;
  }
  return tally;
}
