# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: auth.spec.ts >> Authentication Flow >> should logout
- Location: e2e\auth.spec.ts:37:3

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: page.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for locator('button:has-text("Log out")')

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - navigation [ref=e4]:
    - link "✦ Dyscover" [ref=e5] [cursor=pointer]:
      - /url: /
      - generic [ref=e6]: ✦
      - generic [ref=e7]: Dyscover
    - generic [ref=e8]:
      - link "Explore" [ref=e9] [cursor=pointer]:
        - /url: /
      - link "How it works" [ref=e10] [cursor=pointer]:
        - /url: /how-it-works
      - link "Research" [ref=e11] [cursor=pointer]:
        - /url: /research
      - link "For parents" [ref=e13] [cursor=pointer]:
        - /url: /parent/dashboard
      - link "Educators" [ref=e14] [cursor=pointer]:
        - /url: /educator/dashboard
      - link "Start screening ↗" [ref=e15] [cursor=pointer]:
        - /url: /child/home
        - text: Start screening
        - generic [ref=e16]: ↗
      - generic [ref=e17]:
        - generic [ref=e18]: Language
        - combobox "Choose your language" [ref=e19] [cursor=pointer]:
          - option "English" [selected]
          - option "தமிழ்"
      - link "Log in" [ref=e20] [cursor=pointer]:
        - /url: /login
      - link "Sign up ✦" [ref=e21] [cursor=pointer]:
        - /url: /register
        - text: Sign up
        - generic [ref=e22]: ✦
      - button "Open accessibility settings" [ref=e23] [cursor=pointer]: Aa
  - main [ref=e24]:
    - generic [ref=e26]:
      - generic [ref=e27]:
        - generic [ref=e28]: ✦
        - heading "Welcome back" [level=1] [ref=e29]
        - paragraph [ref=e30]: Sign in to continue your journey
      - generic [ref=e31]:
        - alert [ref=e32]: Not Found
        - generic [ref=e33]:
          - generic [ref=e34]: Email
          - textbox "Email" [ref=e35]:
            - /placeholder: you@example.com
            - text: test@example.com
        - generic [ref=e36]:
          - generic [ref=e37]: Password
          - textbox "Password" [ref=e38]:
            - /placeholder: ••••••••
            - text: password123
        - button "Log in" [ref=e39] [cursor=pointer]
      - paragraph [ref=e40]:
        - text: Don't have an account?
        - link "Create one" [ref=e41] [cursor=pointer]:
          - /url: /register
  - contentinfo [ref=e42]:
    - generic [ref=e43]:
      - link "✦ Dyscover" [ref=e44] [cursor=pointer]:
        - /url: /
        - generic [ref=e45]: ✦
        - text: Dyscover
      - paragraph [ref=e46]: A little world built around how children learn.
    - generic [ref=e47]:
      - link "About" [ref=e48] [cursor=pointer]:
        - /url: /about
      - link "Contact" [ref=e49] [cursor=pointer]:
        - /url: /contact
      - link "Research" [ref=e50] [cursor=pointer]:
        - /url: /research
    - generic [ref=e51]: Dyscover is a non-diagnostic screening and support experience.
  - button "Open Lexi" [ref=e53] [cursor=pointer]:
    - text: L
    - generic [ref=e54]: Lexi
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
  18 |     await expect(page.locator('text=Registration successful')).toBeVisible();
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
> 43 |     await page.click('button:has-text("Log out")');
     |                ^ Error: page.click: Test timeout of 30000ms exceeded.
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