import { By } from "selenium-webdriver";
import { createChromeDriver } from "../helpers/driver.mjs";
import {
  fillInput,
  saveFailureScreenshot,
  waitForElement,
  waitForUrlContains
} from "../helpers/ui.mjs";

const args = new Set(process.argv.slice(2));
const headed = args.has("--headed");
const baseUrl = process.env.E2E_BASE_URL || "http://localhost:5173";

const runId = Date.now();
const testUser = {
  fullName: `Selenium User ${runId}`,
  email: `selenium_${runId}@example.com`,
  password: "Pass123!"
};

const incomePayload = {
  source: `SELENIUM_INCOME_${runId}`,
  amount: "123456"
};

async function runTest() {
  const driver = await createChromeDriver({ headed });

  try {
    console.log("[1/5] Open sign up page");
    await driver.get(`${baseUrl}/signUp`);

    console.log("[2/5] Register a new user");
    const textInputs = await driver.findElements(By.css("input[type='text']"));
    if (textInputs.length < 2) {
      throw new Error("Could not find sign-up text inputs");
    }

    await fillInput(textInputs[0], testUser.fullName);
    await fillInput(textInputs[1], testUser.email);

    const passwordInput = await waitForElement(driver, By.css("input[type='password']"));
    await fillInput(passwordInput, testUser.password);

    const signUpButton = await waitForElement(driver, By.css("button[type='submit']"));
    await signUpButton.click();

    await waitForUrlContains(driver, "/dashboard");

    console.log("[3/5] Open income page");
    await driver.get(`${baseUrl}/income`);

    const addIncomeTrigger = await waitForElement(
      driver,
      By.xpath("//button[contains(normalize-space(.), 'Them thu nhap') or contains(normalize-space(.), 'Thêm thu nhập')]")
    );
    await addIncomeTrigger.click();

    console.log("[4/5] Add an income transaction");
    const modalTextInputs = await driver.findElements(By.css("div.fixed input[type='text']"));
    if (modalTextInputs.length < 2) {
      throw new Error("Could not find income modal inputs");
    }

    await fillInput(modalTextInputs[0], incomePayload.source);
    await fillInput(modalTextInputs[1], incomePayload.amount);

    const addIncomeButton = await waitForElement(
      driver,
      By.xpath("//button[normalize-space(.)='Add Income']")
    );
    await addIncomeButton.click();

    console.log("[5/5] Verify the added income appears");
    await waitForElement(
      driver,
      By.xpath(`//*[contains(normalize-space(.), '${incomePayload.source}')]`)
    );

    console.log("PASS: Selenium E2E sign-up + add income flow is working.");
  } catch (error) {
    const screenshotPath = `e2e/selenium/artifacts/failure-${runId}.png`;
    await saveFailureScreenshot(driver, screenshotPath);
    console.error(`FAIL: ${error.message}`);
    console.error(`Screenshot: ${screenshotPath}`);
    process.exitCode = 1;
  } finally {
    await driver.quit();
  }
}

runTest();
