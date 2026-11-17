// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  expoConfig,
  {
    ignores: ['dist/*', 'mock_espejo/*'],
  },
  {
    // Reglas del React Compiler (eslint-plugin-react-hooks 6). La app no usa el compilador y los
    // patrones que marcan funcionan bien en React 19 (useRef(...).current para objetos estables,
    // setState al cambiar una dependencia en un efecto). Quedan como avisos para revisarlos, no
    // como errores. Revisado en S4-1.
    rules: {
      'react-hooks/refs': 'warn',
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/purity': 'warn',
    },
  },
  {
    // Tests de Jest: `jest.mock` debe ir antes de los imports que mockea (Jest lo eleva igual).
    files: ['**/__tests__/**', 'jest.setup.js'],
    languageOptions: { globals: { jest: 'readonly', require: 'readonly' } },
    rules: { 'import/first': 'off', '@typescript-eslint/no-require-imports': 'off' },
  },
]);
