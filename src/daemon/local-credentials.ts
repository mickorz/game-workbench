import { readFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

/** Where an importable local key was found. Env keys are NOT here: Pi's auth
 * resolution already counts them, so those providers report connected. */
export type LocalCredentialSource = "codex" | "opencode";

export interface LocalCredentialCandidate {
  providerId: string;
  source: LocalCredentialSource;
  /** Masked preview for the UI; the plain key never leaves the daemon. */
  keyHint: string;
}

export function maskKey(key: string): string {
  const trimmed = key.trim();
  if (trimmed.length <= 8) return "*".repeat(trimmed.length);
  return `${trimmed.slice(0, 3)}…${trimmed.slice(-4)}`;
}

interface DiscoveryOptions {
  /** Providers that can be imported into (unconfigured, api-key capable). */
  providers: readonly string[];
  /** Overrides for tests; defaults to the real home directory. */
  homedir?: string;
}

async function readJsonFile(filePath: string): Promise<unknown> {
  try {
    return JSON.parse(await readFile(filePath, "utf8"));
  } catch {
    // Missing or malformed files simply mean "nothing to import".
    return undefined;
  }
}

/** Codex stores `{"OPENAI_API_KEY": "sk-..."}` for API-key sign-in mode. */
async function readCodexApiKey(homedir: string): Promise<string | undefined> {
  const config = await readJsonFile(path.join(homedir, ".codex", "auth.json"));
  const key = (config as { OPENAI_API_KEY?: unknown } | undefined)?.OPENAI_API_KEY;
  return typeof key === "string" && key.trim() ? key.trim() : undefined;
}

interface OpencodeAuthEntry {
  type?: unknown;
  key?: unknown;
}

/** OpenCode stores `{ "<providerId>": { "type": "api", "key": "..." } }`. */
async function readOpencodeApiKeys(homedir: string): Promise<Record<string, string>> {
  const config = await readJsonFile(path.join(homedir, ".opencode", "auth.json"));
  if (!config || typeof config !== "object") return {};
  const keys: Record<string, string> = {};
  for (const [providerId, entry] of Object.entries(config as Record<string, unknown>)) {
    const auth = entry as OpencodeAuthEntry;
    if (typeof auth?.key === "string" && auth.key.trim() && (!auth.type || auth.type === "api")) {
      keys[providerId] = auth.key.trim();
    }
  }
  return keys;
}

/** Detect importable API keys from local CLI credential files. */
export async function discoverFileCredentials(
  options: DiscoveryOptions,
): Promise<LocalCredentialCandidate[]> {
  const homedir = options.homedir ?? os.homedir();
  const wanted = new Set(options.providers);
  const candidates: LocalCredentialCandidate[] = [];
  const codexKey = await readCodexApiKey(homedir);
  if (codexKey && wanted.has("openai")) {
    candidates.push({ providerId: "openai", source: "codex", keyHint: maskKey(codexKey) });
    wanted.delete("openai");
  }
  const opencodeKeys = await readOpencodeApiKeys(homedir);
  for (const providerId of wanted) {
    const key = opencodeKeys[providerId];
    if (key) candidates.push({ providerId, source: "opencode", keyHint: maskKey(key) });
  }
  return candidates;
}

/** Re-read the plain key for an import; the daemon never takes keys from the client. */
export async function readLocalCredential(
  source: LocalCredentialSource,
  providerId: string,
  homedir?: string,
): Promise<string | undefined> {
  const home = homedir ?? os.homedir();
  if (source === "codex") {
    if (providerId !== "openai") return undefined;
    return readCodexApiKey(home);
  }
  const keys = await readOpencodeApiKeys(home);
  return keys[providerId];
}
