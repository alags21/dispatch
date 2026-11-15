import { test, expect } from "@playwright/test";

test("configure a provider, clear the key from the form, and test the saved connection", async ({
  page,
}) => {
  const tier = { model: "", input_per_million: null, output_per_million: null };
  let profile = {
    kind: "anthropic",
    base_url: "https://api.anthropic.com/v1",
    key_saved: false,
    configured: false,
    source: "none",
    problems: [],
    small: tier,
    medium: tier,
    large: tier,
  };
  let checks = 0;
  await page.route("**/api/provider", async (route) => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      expect(body.api_key).toBe("browser-fixture-not-a-real-key");
      expect(body.kind).toBe("anthropic");
      expect(body.small.model).toBe("fixture-model");
      expect(body.medium).toEqual(body.small);
      expect(body.large).toEqual(body.small);
      profile = {
        ...profile,
        ...body,
        key_saved: true,
        configured: true,
        source: "saved",
      };
      delete (profile as any).api_key;
    }
    await route.fulfill({ json: profile });
  });
  await page.route("**/api/provider/models", (route) =>
    route.fulfill({
      json: { models: [{ id: "fixture-model", name: "Fixture model" }] },
    }),
  );
  await page.route("**/api/provider/test", (route) => {
    checks += 1;
    return route.fulfill({
      json: {
        success: true,
        model: "fixture-model",
        message:
          "Authentication and tool-calling check passed. Run a live workflow to verify the full pipeline.",
        input_tokens: 50,
        output_tokens: 10,
        estimated_cost: 0.00007,
      },
    });
  });
  await page.goto("/settings");
  await expect(
    page.getByRole("heading", { name: "AI provider", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("API key", { exact: true })
    .fill("browser-fixture-not-a-real-key");
  await page.getByRole("button", { name: "Load available models" }).click();
  await expect(page.getByRole("status")).toContainText("1 model loaded");
  await page.locator("#model-small").fill("fixture-model");
  await page.locator("#input-small").fill("1");
  await page.locator("#output-small").fill("2");
  await expect(
    page.getByLabel("Use different models for each tier"),
  ).not.toBeChecked();
  await page
    .getByRole("button", { name: "Save provider", exact: true })
    .click();
  await expect(page.locator("#provider-key")).toHaveValue("");
  await expect(
    page.getByText("Key saved on server", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Test connection", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "tool-calling check passed",
  );
  expect(checks).toBe(1);
  await page.reload();
  await expect(page.locator("#provider-key")).toHaveValue("");
  await expect(
    page.getByText("Key saved on server", { exact: true }),
  ).toBeVisible();
  await page.locator("#model-small").fill("different-fixture-model");
  await expect(page.locator("#input-small")).toHaveValue("");
  await expect(page.locator("#output-small")).toHaveValue("");
  await expect(
    page.getByRole("button", { name: "Test connection", exact: true }),
  ).toBeDisabled();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("configured instances default to live execution and preserve an explicit demo choice", async ({
  page,
}) => {
  await page.route("**/api/configuration", (route) =>
    route.fulfill({
      json: { repository_root: "/fixtures", provider: { configured: true } },
    }),
  );
  await page.goto("/new");
  await expect(page.getByLabel("Execution mode")).toHaveValue("live");
  await page.goto("/new?mode=scripted");
  await expect(page.getByLabel("Repository path")).toHaveValue(
    "/fixtures/demo",
  );
  await expect(page.getByLabel("Execution mode")).toHaveValue("scripted");
});
