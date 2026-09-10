import js from "@eslint/js";
import globals from "globals";

export default [
  { ignores: ["vendor/**", "node_modules/**"] },
  js.configs.recommended,
  { languageOptions: { globals: globals.node } },
];
