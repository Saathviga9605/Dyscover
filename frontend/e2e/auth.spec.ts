import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should show registration form', async ({ page }) => {
    await expect(page.locator('text=Register')).toBeVisible();
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button:has-text("Register")')).toBeVisible();
  });

  test('should register a new user', async ({ page }) => {
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'password123');
    await page.fill('input[name="display_name"]', 'Test User');
    await page.click('button:has-text("Register")');
    await expect(page.locator('text=Registration successful')).toBeVisible();
  });

  test('should login with registered user', async ({ page }) => {
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button:has-text("Login")');
    await expect(page.locator('text=Welcome')).toBeVisible();
  });

  test('should logout', async ({ page }) => {
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button:has-text("Login")');
    await expect(page.locator('text=Welcome')).toBeVisible();
    await page.click('button:has-text("Logout")');
    await expect(page.locator('text=Login')).toBeVisible();
  });
});

test.describe('Child Profile Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button:has-text("Login")');
  });

  test('should create a child profile', async ({ page }) => {
    await page.click('button:has-text("Add Child")');
    await page.fill('input[name="display_name"]', 'Test Child');
    await page.click('button:has-text("Create")');
    await expect(page.locator('text=Test Child')).toBeVisible();
  });
});

test.describe('Assessment Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.fill('input[type="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button:has-text("Login")');
  });

  test('should start an assessment', async ({ page }) => {
    await page.click('button:has-text("Start Assessment")');
    await expect(page.locator('text=Letter Detective')).toBeVisible();
  });
});