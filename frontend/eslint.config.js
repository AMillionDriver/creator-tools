// eslint.config.js
"use strict";

const js = require("@eslint/js");

module.exports = [
  js.configs.recommended,
  {
    languageOptions: {
      globals: {
        "browser": true,
        "document": true,
        "window": true,
        "fetch": true,
        "setTimeout": true,
        "setInterval": true,
        "clearInterval": true,
        "console": true,
        "alert": true,
        "node": true
      }
    },
    rules: {
      "no-unused-vars": "warn",
      "no-undef": "warn"
    }
  }
];
