# Sidebar Configuration Guide (sidebar-config)

> Reader-facing: for anyone changing the sidebar brand/navigation. Design analysis: `dev-docs/design/侧边栏主导航可配置化分析.md` (Chinese).

## Where the config lives

**Single source**: `src/renderer/sidebar-config.ts`

This file centralizes two areas of the left sidebar; editing anywhere else has no effect:

| Config | Controls | Type |
|---|---|---|
| `SIDEBAR_BRAND` | Brand name + brand mark | const object |
| `SIDEBAR_ITEMS` | All main-navigation items (order/group/visibility/icon/label) | array |

The component `app-sidebar.tsx` only renders — it hardcodes nothing. Change the config, not the component.

## How to edit

### Brand name & mark (SIDEBAR_BRAND)

```ts
export const SIDEBAR_BRAND = {
  name: "xc-ui-flow",          // brand name: sidebar text + mark alt
  mark: brandMark as string,   // mark URL: asset path or data URI
} as const;
```

- **Rename**: edit the `name` string
- **Replace the mark**: set `mark` to any image URL. Three options:
  - import an SVG/PNG: `mark: myLogo as string` (add the import at the top)
  - public path: `mark: "/my-logo.png"`
  - data URI: `mark: "data:image/svg+xml,..."`

### Navigation items (SIDEBAR_ITEMS)

```ts
export const SIDEBAR_ITEMS: SidebarItemConfig[] = [
  { id: "home",      labelKey: "sidebar.home",      icon: "home",      group: "main" },
  { id: "projects",  labelKey: "sidebar.projects",  icon: "project",   group: "main" },
  // ...
  { id: "web-game",  labelKey: "projectType.web-game", icon: "web-game", group: "studios" },
];
```

Common operations:

| Goal | How |
|---|---|
| Hide an item | add `visible: false` (route stays reachable; only the sidebar entry hides) |
| Remove entirely | delete the line |
| Reorder | move the array element (render order = array order) |
| Change group | `group`: `"main"` (top) / `"studios"` (under the "Studios" label) |
| Change label | point `labelKey` at an existing i18n key (must exist in `src/renderer/locales/zh-CN.ts` and `en.ts`; TypeScript enforces this) |
| Change icon | pick from the registered enum: home / project / library / plugins / community / interactive-story / asset-canvas / web-game / godot / general |

**Constraint**: `id` must be a member of the `SidebarPage` union (see `src/renderer/routes.ts`). A brand-new page id needs route registration before it can appear in the sidebar.

## How changes take effect

### Dev mode (bun run dev:renderer, http://127.0.0.1:43120)

**Save the file — that's it.** Vite HMR picks up the change within ~1s:

```
[vite] hmr update /src/renderer/sidebar-config.ts → app-sidebar.tsx → browser re-renders
```

No page reload; the new brand/navigation shows immediately.

### Desktop / production builds (bun run start:desktop or packaged app)

**No hot reload — rebuild**:

```bash
bun run build:renderer    # rebuild the renderer layer (or build:desktop-app for everything)
```

Then relaunch the Electron shell. The config is compile-time frontend code, not a runtime config file — changing it in a production package means shipping a new build.

### One-liner

> **Dev: Ctrl+S and it's live. Prod: config change = code change = rebuild.**

## FAQ

| Problem | Cause/Fix |
|---|---|
| `labelKey` edit fails typecheck | key missing in locales; add it to both `zh-CN.ts` and `en.ts` |
| Mark URL doesn't show | relative paths resolve from the project root in dev; prefer the import form (goes through the vite asset pipeline) |
| Add a brand-new page | the sidebar config doesn't do routing: register the page id in `routes.ts` + mount the component in `app.tsx` first, then add the config entry |
| Desktop shows no change | the desktop loads built output; rerun `bun run build:renderer` (or full `build:desktop-app`) and restart |

## Related files

- `src/renderer/sidebar-config.ts` — the config (edit this)
- `src/renderer/app-sidebar.tsx` — rendering component (rarely touched)
- `src/renderer/routes.ts` — page ids & hash routing (only for new pages)
- `src/renderer/locales/{zh-CN,en}.ts` — labels (only for literal text changes)
- `src/renderer/styles.css` — `.home-nav-icon-*` masks (only for new icon kinds)
