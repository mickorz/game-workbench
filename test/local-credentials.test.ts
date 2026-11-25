import { mkdir, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  discoverFileCredentials,
  maskKey,
  readLocalCredential,
} from "../src/daemon/local-credentials.js";
import { ModelAuthError, ModelAuthManager } from "../src/daemon/model-auth.js";
import type { ModelRuntime } from "@earendil-works/pi-coding-agent";

let home: string;

afterEach(async () => {
  vi.unstubAllEnvs();
  home = await mkhome();
});

async function mkhome(): Promise<string> {
  home = path.join(await mkdtemp(), "home");
  return home;
}

async function mkdtemp(): Promise<string> {
  const { mkdtemp } = await import("node:fs/promises");
  return mkdtemp(path.join(os.tmpdir(), "local-creds-"));
}

async function writeHome(relative: string, content: string): Promise<void> {
  const target = path.join(home, relative);
  await mkdir(path.dirname(target), { recursive: true });
  await writeFile(target, content);
}

describe("discoverFileCredentials", () => {
  it("finds an OpenAI key in the Codex login file", async () => {
    await mkhome();
    await writeHome(".codex/auth.json", JSON.stringify({ OPENAI_API_KEY: "sk-openai-1234567890" }));
    const items = await discoverFileCredentials({ providers: ["openai", "anthropic"], homedir: home });
    expect(items).toEqual([
      { providerId: "openai", source: "codex", keyHint: "sk-…7890" },
    ]);
  });

  it("finds api keys in the OpenCode auth file for matching providers only", async () => {
    await mkhome();
    await writeHome(
      ".opencode/auth.json",
      JSON.stringify({
        deepseek: { type: "api", key: "sk-deepseek-1234567890" },
        unknown_cli: { type: "api", key: "sk-unknown" },
        oauth_only: { type: "oauth", key: "not-a-key" },
      }),
    );
    const items = await discoverFileCredentials({ providers: ["deepseek", "anthropic"], homedir: home });
    expect(items).toEqual([
      { providerId: "deepseek", source: "opencode", keyHint: "sk-…7890" },
    ]);
  });

  it("prefers the Codex source for OpenAI over OpenCode and tolerates missing files", async () => {
    await mkhome();
    await writeHome(".codex/auth.json", JSON.stringify({ OPENAI_API_KEY: "sk-codex-1234567890" }));
    await writeHome(
      ".opencode/auth.json",
      JSON.stringify({ openai: { type: "api", key: "sk-opencode" } }),
    );
    const items = await discoverFileCredentials({ providers: ["openai"], homedir: home });
    expect(items).toEqual([
      { providerId: "openai", source: "codex", keyHint: "sk-…7890" },
    ]);
    expect(await discoverFileCredentials({ providers: ["openai"], homedir: path.join(home, "empty") })).toEqual([]);
  });

  it("ignores malformed credential files", async () => {
    await mkhome();
    await writeHome(".codex/auth.json", "not json {");
    await writeHome(".opencode/auth.json", "['array']");
    expect(await discoverFileCredentials({ providers: ["openai", "deepseek"], homedir: home })).toEqual([]);
  });
});

describe("readLocalCredential", () => {
  it("re-reads the plain key per source and provider", async () => {
    await mkhome();
    await writeHome(".codex/auth.json", JSON.stringify({ OPENAI_API_KEY: "sk-codex-key" }));
    await writeHome(
      ".opencode/auth.json",
      JSON.stringify({ deepseek: { type: "api", key: "sk-deepseek-key" } }),
    );
    expect(await readLocalCredential("codex", "openai", home)).toBe("sk-codex-key");
    expect(await readLocalCredential("opencode", "deepseek", home)).toBe("sk-deepseek-key");
    expect(await readLocalCredential("codex", "deepseek", home)).toBeUndefined();
    expect(await readLocalCredential("opencode", "openai", home)).toBeUndefined();
  });
});

describe("maskKey", () => {
  it("masks short keys fully and keeps the tail of long ones", () => {
    expect(maskKey("short")).toBe("*****");
    expect(maskKey("sk-openai-1234567890")).toBe("sk-…7890");
  });
});

describe("ModelAuthManager.importApiKey", () => {
  function fakeRuntime(overrides: Partial<Pick<ModelRuntime, "getProvider" | "getProviders" | "getProviderAuthStatus" | "login">> = {}) {
    const provider = {
      id: "deepseek",
      name: "DeepSeek",
      auth: { apiKey: { login: true } },
    };
    return {
      getProvider: (id: string) => (id === provider.id ? provider : undefined),
      getProviders: () => [provider],
      getProviderAuthStatus: () => ({ configured: false }),
      login: async () => {},
      ...overrides,
    } as unknown as ModelRuntime;
  }

  it("answers the api_key prompt with the discovered key", async () => {
    // login 发起一次 secret 提示；值回填后整个登录完成
    const runtime = fakeRuntime({
      login: async (
        _providerId: unknown,
        _method: unknown,
        interaction: { prompt: (prompt: { type: string; message: string }) => Promise<string> },
      ) => {
        const key = await interaction.prompt({ type: "secret", message: "API key" });
        expect(key).toBe("sk-discovered");
      },
    } as never);
    const importing = new ModelAuthManager(async () => runtime);
    await importing.importApiKey("deepseek", "sk-discovered");
  });

  it("fails when the provider never prompts and finishes instead", async () => {
    const runtime = fakeRuntime({ login: async () => {} } as never);
    const importing = new ModelAuthManager(async () => runtime);
    await expect(importing.importApiKey("deepseek", "sk-x")).rejects.toMatchObject({
      statusCode: 502,
    });
  });

  it("rejects unknown providers like the interactive flow", async () => {
    const importing = new ModelAuthManager(async () => fakeRuntime());
    await expect(importing.importApiKey("nope", "sk-x")).rejects.toBeInstanceOf(ModelAuthError);
  });
});
