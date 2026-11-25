import { describe, expect, it } from "vitest";
import type { ProviderSummary } from "../src/shared/contracts.js";
import { groupProviders } from "../src/renderer/provider-groups.js";

const summary = (
  id: string,
  overrides: Partial<ProviderSummary> = {},
): ProviderSummary => ({
  id,
  name: id,
  configured: false,
  capabilities: ["language"],
  status: "not_configured",
  methods: [],
  ...overrides,
});
const ids = (providers: ProviderSummary[]) =>
  providers.map((provider) => provider.id);
const predicates = {
  isConnected: (provider: ProviderSummary) => provider.status === "connected",
  isFree: (provider: ProviderSummary) => provider.managed === "free_cloud",
  isLocal: (provider: ProviderSummary) => provider.preset === "ollama",
};

describe("provider groups", () => {
  it("puts every working connection first, including free cloud and local services", () => {
    const groups = groupProviders(
      [
        summary("cerebras"),
        summary("cloud-hyper3d", {
          managed: "free_cloud",
          status: "connected",
        }),
        summary("openai", { status: "connected" }),
        summary("custom:ollama", { preset: "ollama", status: "connected" }),
        summary("deepseek"),
        summary("openrouter"),
      ],
      predicates,
    );
    expect(ids(groups.connected)).toEqual([
      "cloud-hyper3d",
      "openai",
      "custom:ollama",
    ]);
    expect(groups.free).toEqual([]);
    expect(groups.local).toEqual([]);
    expect(ids(groups.popular)).toEqual(["openrouter", "deepseek"]);
    expect(ids(groups.more)).toEqual(["cerebras"]);
  });

  it("offers unconnected free, popular, and local providers in their own groups", () => {
    const groups = groupProviders(
      [
        summary("tripo", { capabilities: ["3d"] }),
        summary("cerebras"),
        summary("openrouter"),
        summary("cloud-hyper3d", { managed: "free_cloud" }),
        summary("custom:ollama", { preset: "ollama" }),
        summary("deepseek"),
        summary("openai"),
      ],
      predicates,
    );
    expect(ids(groups.free)).toEqual(["cloud-hyper3d"]);
    expect(ids(groups.popular)).toEqual([
      "openai",
      "openrouter",
      "deepseek",
      "tripo",
    ]);
    expect(ids(groups.local)).toEqual(["custom:ollama"]);
    expect(ids(groups.more)).toEqual(["cerebras"]);
  });

  it("honours configured priority groups from provider-groups.config.json", () => {
    const groups = groupProviders(
      [
        summary("openai"),
        summary("deepseek"),
        summary("moonshotai"),
        summary("zai"),
        summary("cerebras"),
      ],
      {
        ...predicates,
        priorityGroups: [{ id: "china", providers: ["deepseek", "zai", "moonshotai"] }],
      },
    );
    expect(groups.priority.map((group) => group.id)).toEqual(["china"]);
    expect(groups.priority[0]!.items.map((item) => item.id)).toEqual([
      "deepseek",
      "zai",
      "moonshotai",
    ]);
    // claimed providers leave the popular group even when listed there
    expect(ids(groups.popular)).toEqual(["openai"]);
    expect(ids(groups.more)).toEqual(["cerebras"]);
  });

  it("defaults to no priority groups so settings keep their existing shape", () => {
    const groups = groupProviders([summary("deepseek"), summary("openai")], predicates);
    expect(groups.priority).toEqual([]);
    expect(ids(groups.popular)).toEqual(["openai", "deepseek"]);
  });
});
