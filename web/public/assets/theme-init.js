(() => {
  try {
    const stored = globalThis.localStorage.getItem("orqalis-theme");
    const preference = ["system", "dark", "light"].includes(stored)
      ? stored
      : "dark";
    const dark =
      preference === "dark" ||
      (preference === "system" &&
        globalThis.matchMedia("(prefers-color-scheme: dark)").matches);
    globalThis.document.documentElement.dataset.theme = dark ? "dark" : "light";
    globalThis.document.querySelector('meta[name="theme-color"]').content = dark
      ? "#07070f"
      : "#eef3f6";
  } catch {
    globalThis.document.documentElement.dataset.theme = "dark";
  }
})();
