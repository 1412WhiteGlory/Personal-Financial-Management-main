import { Builder } from "selenium-webdriver";
import chrome from "selenium-webdriver/chrome.js";
import "chromedriver";

export async function createChromeDriver({ headed = false } = {}) {
  const options = new chrome.Options();

  if (!headed) {
    options.addArguments("--headless=new");
  }

  options.addArguments(
    "--window-size=1440,900",
    "--disable-gpu",
    "--no-sandbox",
    "--disable-dev-shm-usage"
  );

  return new Builder().forBrowser("chrome").setChromeOptions(options).build();
}
