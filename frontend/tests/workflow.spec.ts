import { test, expect } from "@playwright/test";
test("create workflow in UI, observe repairs, inspect real artifacts", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Workspace overview" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "New workflow", exact: true })
    .last()
    .click();
  await expect(page.getByLabel("Repository path")).not.toHaveValue("");
  await page.getByRole("button", { name: "Start workflow" }).click();
  await expect(page).toHaveURL(/\/runs\//);
  await expect(
    page.getByText("Review-ready recommendation; no merge performed", {
      exact: false,
    }),
  ).toBeVisible({ timeout: 80000 });
  await expect(page.getByText("REPAIRING", { exact: true })).toHaveCount(2);
  await page.getByRole("button", { name: "Patch", exact: true }).click();
  await expect(page.locator("pre.diff")).toContainText("price * quantity");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download patch" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.patch$/);
  await page.getByRole("button", { name: "Tests", exact: true }).click();
  await expect(page.locator("pre").first()).toContainText("passed");
  await page.getByRole("button", { name: "Security", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "No blocking findings" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Report", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Recommended for human review" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
  await page.goto("/");
  await page.screenshot({ path: "../docs/dashboard.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Workspace overview" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
