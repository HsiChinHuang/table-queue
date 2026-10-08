// ESLint 9 flat config (t22, platform #77).
// Seeded minimum per docs/issues/t22.md: typescript-eslint `recommended` for
// **/*.ts, **/*.tsx plus the react-hooks `recommended` flat config.
// eslint 9 ignores node_modules by default; build output is ignored below.
// src/ and tests/ are deliberately NOT ignored (a vacuous config is the
// failure class AC-2/AC-3 exist to refuse).
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist/", "coverage/"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  // `recommended-latest` is the flat-config variant of eslint-plugin-react-hooks 5.x
  // (`configs.recommended` is the eslintrc shape: plugins as string names).
  reactHooks.configs["recommended-latest"],
  {
    rules: {
      // t22: `src/api/**` carries `_branchId` placeholder parameters on purpose
      // (uniform branch-scoped API shape; the client does not send them yet).
      // The underscore prefix marks them intentionally unused, so exempt `_*`
      // arguments instead of renaming the public API signatures.
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_" },
      ],
    },
  },
);
