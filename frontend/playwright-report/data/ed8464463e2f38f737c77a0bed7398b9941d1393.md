# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: auth.spec.ts >> Authentication Flow >> should register a new user
- Location: e2e\auth.spec.ts:12:3

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('text=Registration successful')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" locator('text=Registration successful') with timeout 5000ms
  - waiting for locator('text=Registration successful')

```

```yaml
- navigation:
  - link "✦ Dyscover":
    - /url: /
  - link "Explore":
    - /url: /
  - link "How it works":
    - /url: /how-it-works
  - link "Research":
    - /url: /research
  - link "For parents":
    - /url: /parent/dashboard
  - link "Educators":
    - /url: /educator/dashboard
  - link "Start screening ↗":
    - /url: /child/home
  - text: Language
  - combobox "Choose your language":
    - option "English" [selected]
    - option "தமிழ்"
  - link "Log in":
    - /url: /login
  - link "Sign up ✦":
    - /url: /register
  - button "Open accessibility settings": Aa
- main:
  - text: ✦
  - heading "Create your account" [level=1]
  - paragraph: Start your Dyscover journey
  - text: Display name
  - textbox "Display name":
    - /placeholder: Alex's parent
    - text: Test User
  - text: Email
  - textbox "Email":
    - /placeholder: you@example.com
    - text: test@example.com
  - text: Password
  - textbox "Password":
    - /placeholder: ••••••••
    - text: password123
  - text: Confirm password
  - textbox "Confirm password":
    - /placeholder: ••••••••
  - text: I am a…
  - radio "Parent" [checked]
  - text: Parent
  - radio "Educator"
  - text: Educator
  - button "Create account"
  - paragraph:
    - text: Already have an account?
    - link "Sign in":
      - /url: /login
- contentinfo:
  - link "✦ Dyscover":
    - /url: /
  - paragraph: A little world built around how children learn.
  - link "About":
    - /url: /about
  - link "Contact":
    - /url: /contact
  - link "Research":
    - /url: /research
  - text: Dyscover is a non-diagnostic screening and support experience.
- button "Open Lexi": L Lexi
```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test';
  2  | 
  3  | test.describe('Authentication Flow', () => {
  4  |   test('should show registration form', async ({ page }) => {
  5  |     await page.goto('/register');
  6  |     await expect(page.locator('text=Create your account')).toBeVisible();
  7  |     await expect(page.locator('input[type="email"]')).toBeVisible();
  8  |     await expect(page.locator('input[id="password"]')).toBeVisible();
  9  |     await expect(page.locator('button:has-text("Create account")')).toBeVisible();
  10 |   });
  11 | 
  12 |   test('should register a new user', async ({ page }) => {
  13 |     await page.goto('/register');
  14 |     await page.fill('input[type="email"]', 'test@example.com');
  15 |     await page.fill('input[id="password"]', 'password123');
  16 |     await page.fill('input[name="display_name"]', 'Test User');
  17 |     await page.click('button:has-text("Create account")');
> 18 |     await expect(page.locator('text=Registration successful')).toBeVisible();
     |                                                                ^ Error: expect(locator).toBeVisible() failed
  19 |   });
  20 | 
  21 |   test('should show login form', async ({ page }) => {
  22 |     await page.goto('/login');
  23 |     await expect(page.locator('text=Welcome back')).toBeVisible();
  24 |     await expect(page.locator('input[type="email"]')).toBeVisible();
  25 |     await expect(page.locator('input[type="password"]')).toBeVisible();
  26 |     await expect(page.locator('button:has-text("Log in")')).toBeVisible();
  27 |   });
  28 | 
  29 |   test('should login with registered user', async ({ page }) => {
  30 |     await page.goto('/login');
  31 |     await page.fill('input[type="email"]', 'test@example.com');
  32 |     await page.fill('input[type="password"]', 'password123');
  33 |     await page.click('button:has-text("Log in")');
  34 |     await expect(page.locator('text=Welcome')).toBeVisible();
  35 |   });
  36 | 
  37 |   test('should logout', async ({ page }) => {
  38 |     await page.goto('/login');
  39 |     await page.fill('input[type="email"]', 'test@example.com');
  40 |     await page.fill('input[type="password"]', 'password123');
  41 |     await page.click('button:has-text("Log in")');
  42 |     await expect(page.locator('text=Welcome')).toBeVisible();
  43 |     await page.click('button:has-text("Log out")');
  44 |     await expect(page.locator('text=Log in')).toBeVisible();
  45 |   });
  46 | });
  47 | 
  48 | test.describe('Child Profile Management', () => {
  49 |   test.beforeEach(async ({ page }) => {
  50 |     await page.goto('/login');
  51 |     await page.fill('input[type="email"]', 'test@example.com');
  52 |     await page.fill('input[type="password"]', 'password123');
  53 |     await page.click('button:has-text("Log in")');
  54 |   });
  55 | 
  56 |   test('should create a child profile', async ({ page }) => {
  57 |     await page.click('button:has-text("Add Child")');
  58 |     await page.fill('input[name="display_name"]', 'Test Child');
  59 |     await page.click('button:has-text("Create")');
  60 |     await expect(page.locator('text=Test Child')).toBeVisible();
  61 |   });
  62 | });
  63 | 
  64 | test.describe('Assessment Flow', () => {
  65 |   test.beforeEach(async ({ page }) => {
  66 |     await page.goto('/login');
  67 |     await page.fill('input[type="email"]', 'test@example.com');
  68 |     await page.fill('input[type="password"]', 'password123');
  69 |     await page.click('button:has-text("Log in")');
  70 |   });
  71 | 
  72 |   test('should start an assessment', async ({ page }) => {
  73 |     await page.click('button:has-text("Start Assessment")');
  74 |     await expect(page.locator('text=Letter Detective')).toBeVisible();
  75 |   });
  76 | });
```