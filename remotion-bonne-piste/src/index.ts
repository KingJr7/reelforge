import { registerFont, getComposition, still } from "@remotion/cli";
import { BonnePisteComposition } from "./composition";

// Register local fonts (fallback to system if missing)
try {
  registerFont({
    family: "Poppins",
    src: localFont({
      name: "Poppins",
      path: "../assets/fonts/Poppins-SemiBold.ttf",
      style: "normal",
      weight: "600",
    }),
  });
  try {
    registerFont({
      family: "Poppins",
      src: localFont({
        name: "Poppins",
        path: "../assets/fonts/Poppins-ExtraBold.ttf",
        style: "normal",
        weight: "800",
      }),
    });
  } catch {}
} catch {}

export { BonnePisteComposition };
export { getComposition, still };
