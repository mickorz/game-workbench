import type { ProviderSummary } from "../shared/contracts.js";
import groupsConfig from "./provider-groups.config.json" with { type: "json" };

/** A display group declared in provider-groups.config.json; array order is priority order. */
export interface ProviderPriorityGroup {
  id: string;
  providers: readonly string[];
}

/** Edit provider-groups.config.json to adjust groups and priority without touching code. */
export const PROVIDER_PRIORITY_GROUPS = (groupsConfig as { groups: ProviderPriorityGroup[] }).groups;
const POPULAR_ORDER = (groupsConfig as { popularOrder: readonly string[] }).popularOrder;

/** Providers listed ahead of the rest in Settings and first-run setup, in display order. */
const POPULAR_PROVIDER_IDS = POPULAR_ORDER;

export interface ProviderGroups {
  /** Every working connection, including free cloud and local services. */
  connected: ProviderSummary[];
  free: ProviderSummary[];
  popular: ProviderSummary[];
  local: ProviderSummary[];
  more: ProviderSummary[];
  /** Config-file groups in file order, right after connected; empty when unused. */
  priority: Array<{ id: string; items: ProviderSummary[] }>;
}

/** Splits providers into the groups both provider lists show, keeping each group's order stable. */
export function groupProviders(
  providers: readonly ProviderSummary[],
  {
    isConnected,
    isFree,
    isLocal,
    priorityGroups = [],
  }: {
    isConnected: (provider: ProviderSummary) => boolean;
    isFree: (provider: ProviderSummary) => boolean;
    isLocal: (provider: ProviderSummary) => boolean;
    priorityGroups?: readonly ProviderPriorityGroup[];
  },
): ProviderGroups {
  const connected = providers.filter(isConnected);
  const remaining = providers.filter((provider) => !isConnected(provider));
  const claimed = new Set(priorityGroups.flatMap((group) => group.providers));
  const priority = priorityGroups
    .map((group) => ({
      id: group.id,
      items: group.providers
        .filter((id) => remaining.some((provider) => provider.id === id))
        .map((id) => remaining.find((provider) => provider.id === id)!),
    }))
    .filter((group) => group.items.length > 0);
  const rest = remaining.filter((provider) => !claimed.has(provider.id));
  const free = rest.filter(isFree);
  const local = rest.filter((provider) => !isFree(provider) && isLocal(provider));
  const ungrouped = rest.filter((provider) => !isFree(provider) && !isLocal(provider));
  const popular = ungrouped
    .filter((provider) => POPULAR_PROVIDER_IDS.includes(provider.id))
    .sort(
      (first, second) =>
        POPULAR_PROVIDER_IDS.indexOf(first.id) -
        POPULAR_PROVIDER_IDS.indexOf(second.id),
    );
  const more = ungrouped.filter((provider) => !popular.includes(provider));
  return { connected, free, popular, local, more, priority };
}
