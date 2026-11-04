import { describe, expect, it } from "vitest";
import {
  PLUGIN_MANIFEST_PATH,
  PLUGIN_MANIFEST_PATHS,
  PLUGIN_MANIFEST_WRITE_PATH,
  isPluginManifest,
  isNewerPluginVersion,
  isPluginVersion,
  parsePluginMentions,
  serializePluginMentions,
  type PluginSummary,
} from "../src/shared/plugins.js";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { readPluginManifest } from "../src/daemon/local-plugins.js";

const minimalManifest = {
  name: "protocol-check",
  version: "1.0.0",
  description: "Manifest path protocol check",
};

async function pluginWithManifest(relative: string): Promise<string> {
  const root = await mkdtemp(path.join(tmpdir(), "xcflow-manifest-protocol-"));
  await mkdir(path.join(root, path.dirname(relative)), { recursive: true });
  await writeFile(path.join(root, relative), JSON.stringify(minimalManifest));
  return root;
}

async function withTemp<T>(root: string, action: () => Promise<T>): Promise<T> {
  try { return await action(); } finally { await rm(root, { recursive: true, force: true }); }
}

describe("plugin protocol", () => {
  it("exposes the new manifest path with the legacy fallback", () => {
    // 写入侧只用新名；读取优先级新名在前，旧名永久回落
    expect(PLUGIN_MANIFEST_WRITE_PATH).toBe(".xcflow-plugin/plugin.json");
    expect(PLUGIN_MANIFEST_PATHS).toEqual([".xcflow-plugin/plugin.json", ".ohmygame-plugin/plugin.json"]);
  });

  it("reads the new manifest path, the legacy path, and prefers the new one when both exist", async () => {
    // 新名单独存在
    const onlyNew = await pluginWithManifest(PLUGIN_MANIFEST_WRITE_PATH);
    await withTemp(onlyNew, async () => {
      await expect(readPluginManifest(onlyNew)).resolves.toMatchObject(minimalManifest);
    });
    // 旧名单独存在（存量已装插件与上游生态）
    const onlyLegacy = await pluginWithManifest(PLUGIN_MANIFEST_PATH);
    await withTemp(onlyLegacy, async () => {
      await expect(readPluginManifest(onlyLegacy)).resolves.toMatchObject(minimalManifest);
    });
    // 双存时新名优先
    const both = await pluginWithManifest(PLUGIN_MANIFEST_WRITE_PATH);
    await mkdir(path.join(both, ".ohmygame-plugin"), { recursive: true });
    await writeFile(path.join(both, PLUGIN_MANIFEST_PATH), JSON.stringify({ ...minimalManifest, description: "legacy must lose" }));
    await withTemp(both, async () => {
      await expect(readPluginManifest(both)).resolves.toMatchObject(minimalManifest);
    });
  });

  it("accepts a minimal plugin manifest", () => {
    expect(isPluginManifest({
      name: "character-writer",
      enabledByDefault: false,
      version: "1.0.0",
      description: "Reusable character writing workflow",
      skills: "./skills/",
    })).toBe(true);
  });

  it("accepts skills, connections, and display metadata", () => {
    expect(isPluginManifest({
      name: "godot-tools",
      version: "0.1.0-alpha.1",
      description: "Godot workflows and tools",
      skills: "./skills/",
      connections: ["ohmygame-godot"],
      interface: {
        beta: true,
        displayName: "Godot",
        shortDescription: "Godot workflows",
        longDescription: "Build and edit Godot projects through the connected editor.",
        defaultPrompt: ["Build a player controller."],
        projectTypes: ["godot-game"],
      },
    })).toBe(true);
  });

  it("accepts multiple skill paths", () => {
    expect(isPluginManifest({
      name: "game-tools",
      version: "1.0.0",
      description: "Game tools",
      skills: ["./skills/godot/", "./skills/web/"],
    })).toBe(true);
  });

  it("rejects invalid identities, paths, and undeclared fields", () => {
    const base = {
      name: "valid-plugin",
      version: "1.0.0",
      description: "Valid plugin",
    };

    expect(isPluginManifest({ ...base, name: "Invalid Plugin" })).toBe(false);
    expect(isPluginManifest({ ...base, skills: "skills/" })).toBe(false);
    expect(isPluginManifest({ ...base, skills: "./../skills/" })).toBe(false);
    expect(isPluginManifest({ ...base, homepage: "https://ohmygame.ai" })).toBe(false);
    expect(isPluginManifest({ ...base, version: "" })).toBe(false);
    expect(isPluginManifest({ ...base, enabled: true })).toBe(false);
    expect(isPluginManifest({ ...base, enabledByDefault: "false" })).toBe(false);
    expect(isPluginManifest({ ...base, mcpServers: "../mcp.json" })).toBe(false);
    expect(isPluginManifest({ ...base, apps: "./apps.json" })).toBe(false);
    expect(isPluginManifest({ ...base, hooks: "./hooks.json" })).toBe(false);
    expect(isPluginManifest({ ...base, tools: ["generate-image"] })).toBe(false);
    expect(isPluginManifest({ ...base, interface: { logo: "./logo.png" } })).toBe(false);
    expect(isPluginManifest({ ...base, interface: { beta: "true" } })).toBe(false);
  });

  it("accepts declared icons and rejects unknown IDs and non-package image paths", () => {
    const base = { name: "icon-plugin", version: "1.0.0", description: "Icons" };
    for (const icon of [{ type: "preset", id: "image" }, { type: "asset", path: "./assets/icon.png" }, { type: "asset", path: "./assets/icon.webp" }, { type: "asset", path: "./assets/icon.svg" }]) {
      expect(isPluginManifest({ ...base, interface: { icon } })).toBe(true);
    }
    for (const icon of [{ type: "preset", id: "invented" }, { type: "asset", path: "./../icon.png" }, { type: "asset", path: "https://example.com/icon.png" }, { type: "asset", path: "./icon.gif" }]) {
      expect(isPluginManifest({ ...base, interface: { icon } })).toBe(false);
    }
  });

  it("accepts SemVer versions only", () => {
    expect(isPluginVersion("1.0.0-alpha.1+build.7")).toBe(true);
    expect(isPluginVersion("1.0")).toBe(false);
    expect(isPluginVersion("1.0.0-01")).toBe(false);
    expect(isPluginVersion("1/2")).toBe(false);
  });

  it("orders stable and prerelease Plugin versions", () => {
    expect(isNewerPluginVersion("1.1.0", "1.0.9")).toBe(true);
    expect(isNewerPluginVersion("1.0.0", "1.0.0-beta.2")).toBe(true);
    expect(isNewerPluginVersion("1.0.0-beta.10", "1.0.0-beta.2")).toBe(true);
    expect(isNewerPluginVersion("1.0.0-alpha", "1.0.0")).toBe(false);
  });

  it("keeps installation state outside the author manifest", () => {
    const plugin: PluginSummary = {
      id: "ohmygame:godot",
      name: "godot",
      displayName: "Godot",
      description: "Connect the agent to the Godot editor",
      marketplace: { id: "ohmygame", displayName: "XC-UI-Flow" },
      source: { type: "builtIn" },
      installed: true,
      enabled: true,
    };

    expect(plugin.source).toEqual({ type: "builtIn" });
  });

  it("serializes and restores Codex-style Plugin mentions", () => {
    const mention = { name: "godot", displayName: "Godot", marketplaceId: "ohmygame" };
    const serialized = serializePluginMentions("Use @Godot to inspect the scene", [mention]);

    expect(serialized).toBe("Use [@Godot](plugin://godot@ohmygame) to inspect the scene");
    expect(parsePluginMentions(serialized)).toEqual({
      text: "Use @Godot to inspect the scene",
      mentions: [mention],
    });
  });

  it("serializes longer Plugin names before matching prefixes", () => {
    const mentions = [
      { name: "foo", displayName: "Foo", marketplaceId: "personal" },
      { name: "foo-bar", displayName: "Foo Bar", marketplaceId: "personal" },
    ];

    expect(serializePluginMentions("Use @Foo Bar, then @Foo", mentions)).toBe(
      "Use [@Foo Bar](plugin://foo-bar@personal), then [@Foo](plugin://foo@personal)",
    );
  });

  it("leaves malformed Plugin references untouched", () => {
    const malformed = "Use [@Godot](plugin://%E0%A4%A@ohmygame)";
    expect(parsePluginMentions(malformed)).toEqual({ text: malformed, mentions: [] });
  });

});
