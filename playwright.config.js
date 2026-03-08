const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 60000,
  expect: {
    timeout: 10000
  },
  webServer: {
    command: 'python app.py',
    env: {
      WEAVE_PORT: '5111',
      WEAVE_DB_PATH: 'instance/playwright.db',
    },
    url: 'http://127.0.0.1:5111/healthz',
    reuseExistingServer: false,
    timeout: 120000,
  },
  use: {
    baseURL: 'http://127.0.0.1:5111',
    trace: 'on-first-retry'
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    },
    {
      name: 'webkit-mobile',
      use: {
        ...devices['iPhone 13'],
        viewport: { width: 390, height: 844 }
      }
    }
  ]
});
