import { until } from "selenium-webdriver";

export const DEFAULT_TIMEOUT = 20000;

export async function waitForUrlContains(driver, partialUrl, timeout = DEFAULT_TIMEOUT) {
  await driver.wait(until.urlContains(partialUrl), timeout);
}

export async function waitForElement(driver, locator, timeout = DEFAULT_TIMEOUT) {
  const element = await driver.wait(until.elementLocated(locator), timeout);
  await driver.wait(until.elementIsVisible(element), timeout);
  return element;
}

export async function fillInput(element, value) {
  await element.clear();
  await element.sendKeys(value);
}

export async function saveFailureScreenshot(driver, filePath) {
  const screenshot = await driver.takeScreenshot();
  const fs = await import("node:fs/promises");
  await fs.mkdir(filePath.substring(0, filePath.lastIndexOf("/")), { recursive: true });
  await fs.writeFile(filePath, screenshot, "base64");
}
