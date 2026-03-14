const { defineConfig, devices } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const useSystemChrome = String(process.env.PLAYWRIGHT_USE_SYSTEM_CHROME || '').trim() === '1';
const systemChromePath = process.env.PLAYWRIGHT_CHROME_PATH
  || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const useExternalServer = String(process.env.PLAYWRIGHT_EXTERNAL_SERVER || '').trim() === '1';
const venvPythonPath = path.join(process.cwd(), '.venv', 'Scripts', 'python.exe');
const pythonCommand = fs.existsSync(venvPythonPath) ? `"${venvPythonPath}"` : 'python';

const chromiumDesktopUse = useSystemChrome
  ? {
      ...devices['Desktop Chrome'],
      browserName: 'chromium',
      launchOptions: {
        executablePath: systemChromePath,
      },
    }
  : { ...devices['Desktop Chrome'] };

const mobileUse = useSystemChrome
  ? {
      ...devices['iPhone 13'],
      browserName: 'chromium',
      viewport: { width: 390, height: 844 },
      launchOptions: {
        executablePath: systemChromePath,
      },
    }
  : {
      ...devices['iPhone 13'],
      viewport: { width: 390, height: 844 },
    };

module.exports = defineConfig({
  testDir: './tests',
  timeout: 60000,
  expect: {
    timeout: 10000
  },
  webServer: useExternalServer
    ? undefined
    : {
        command: `${pythonCommand} app.py`,
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
      use: chromiumDesktopUse
    },
    {
      name: 'webkit-mobile',
      use: mobileUse
    }
  ]
});
