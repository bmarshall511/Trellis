// Trellis: exclude framework-owned paths. See .claude/framework-paths.json
// Spread into your flat config: export default [trellisIgnores, ...yourConfig]
export const trellisIgnores = {
  ignores: [".claude/**", ".githooks/**", "setup/**", "stacks/**"],
};
export default [trellisIgnores];
