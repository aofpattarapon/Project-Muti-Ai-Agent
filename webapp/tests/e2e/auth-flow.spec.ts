import { expect, test, type Page } from "@playwright/test";

async function openLoginReady(page: Page) {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Access the pilot dashboard" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign In" })).toBeVisible();
}

test("signed-out user is redirected from dashboard to login", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login$/);
});

test("invalid login shows safe error", async ({ page }) => {
  await openLoginReady(page);
  await page.getByPlaceholder("admin or admin@example.com").fill("unknown@example.com");
  await page.getByPlaceholder("Enter your password").fill("wrong-password");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page.getByText("Invalid username, email, or password.")).toBeVisible();
});

test("admin can log in, reach dashboard, and log out", async ({ page }) => {
  await openLoginReady(page);
  await page.getByPlaceholder("admin or admin@example.com").fill("admin");
  await page.getByPlaceholder("Enter your password").fill("Admin123!");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: /Welcome back,/ })).toBeVisible();
  await expect(page.getByText("You are signed in as Admin.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Admin controls" })).toBeVisible();

  await page.getByRole("button", { name: "Logout" }).click();
  await expect(page).toHaveURL(/\/login$/);
});
