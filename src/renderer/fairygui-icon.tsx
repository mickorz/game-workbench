import type { ImgHTMLAttributes } from "react";

const fairyguiIconUrl = new URL("./assets/fairygui.svg", import.meta.url).href;

export function FairyguiIcon({ size = 13, ...props }: ImgHTMLAttributes<HTMLImageElement> & { size?: number }) {
  return <img className="tool-brand-icon tool-brand-fairygui" src={fairyguiIconUrl} width={size} height={size} alt="" {...props} />;
}
