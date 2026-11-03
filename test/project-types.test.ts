import { describe, expect, it } from "vitest";
import { defaultProjectName, GAME_PROJECT_TYPES, PROJECT_TYPES, projectTypeLabel } from "../src/renderer/project-types.js";

describe("project types", () => {
  it("keeps the shared labels and display order", () => {
    expect(PROJECT_TYPES).toEqual([
      { label: "Web Game", value: "web-game" },
      { label: "Interactive Story", value: "interactive-story" },
      { label: "Asset Canvas", value: "asset-canvas" },
      { label: "Godot", value: "godot-game" },
      { label: "FairyGUI", value: "fairygui" },
      { label: "General Game", value: "general" },
    ]);
  });

  it("keeps Asset Canvas and the hidden types out of the home game types", () => {
    // HIDDEN_PROJECT_TYPE_IDS 隐藏 4 类工作室，首页只剩 FairyGUI
    expect(GAME_PROJECT_TYPES.map(({ value }) => value)).toEqual(["fairygui"]);
  });

  it("provides labels and default names", () => {
    expect(projectTypeLabel("general")).toBe("General Game");
    expect(defaultProjectName("general")).toBe("Untitled project");
    expect(projectTypeLabel("interactive-story")).toBe("Interactive Story");
    expect(defaultProjectName("interactive-story")).toBe("Untitled story");
    expect(defaultProjectName("web-game")).toBe("Untitled project");
  });
});
