# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: auth.spec.ts >> Authentication Flow >> should show registration form
- Location: e2e\auth.spec.ts:8:3

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('text=Register')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" locator('text=Register') with timeout 5000ms
  - waiting for locator('text=Register')

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
  - button "Open accessibility settings": Aa
- main:
  - text: ✦ + a A little world for curious minds
  - heading "Discover how you learn." [level=1]
  - paragraph: Every mind has its own way of finding the words. Dyscover makes early learning patterns easier to notice, understand, and support.
  - link "Start the adventure →":
    - /url: /child/home
  - link "See how it works ↗":
    - /url: /how-it-works
  - paragraph: ✦ Gentle activities. Clearer conversations. No labels.
  - text: abc ✦ ✦
  - img "Dyscover companion": ✦ ✦
  - text: Learning looks different for everyone
  - heading "Noticing is the first step." [level=2]
  - paragraph: Good support starts with curiosity, not assumptions. Dyscover uses short, playful activities to build a fuller picture of how a child interacts with words, symbols, and patterns.
  - text: 01 ↻
  - heading "Play without pressure" [level=3]
  - paragraph: Small activities feel like an adventure, not a test.
  - link "Meet the explorer →":
    - /url: /child/home
  - text: 02 ✦
  - heading "Notice the patterns" [level=3]
  - paragraph: We keep useful observations connected to each activity.
  - link "See our approach →":
    - /url: /research
  - text: 03 ⌁
  - heading "Grow the conversation" [level=3]
  - paragraph: Clearer information can lead to more helpful next steps.
  - link "Why it matters →":
    - /url: /about
  - text: ✦ Timing choices words focus A fuller picture
  - heading "Built around the way children interact." [level=2]
  - paragraph: Every response tells a small part of the story. Dyscover can organize accuracy, reaction time, hesitation, and interaction events at the trial level. Optional gaze research stays separate and consent-based.
  - strong: "01"
  - text: Response
  - strong: "02"
  - text: Timing
  - strong: "03"
  - text: Interaction
  - link "Explore the research direction ↗":
    - /url: /research
  - text: For grown-ups
  - heading "A calmer view of the journey." [level=2]
  - paragraph: The parent space is designed for thoughtful conversations, not alarming scores.
  - text: Alex's Dyscover journey Demo view Good morning
  - heading "Let's see what Alex explored." [level=3]
  - paragraph: Latest screening · just now
  - text: Play without pressure Notice the patterns Grow the conversation Observed areas
  - strong: "04"
  - text: Activities
  - strong: "--"
  - text: Next step
  - strong: Ready
  - link "Visit the parent space ↗":
    - /url: /parent/dashboard
  - img "Dyscover companion": ✦ ✦
  - text: A friendly guide
  - heading "Meet Lexi." [level=2]
  - paragraph: A gentle companion for questions, hints, and the next little step.
  - button "Say hello →"
  - text: Designed with care
  - heading "Warmth and intelligence, together." [level=2]
  - text: ◌
  - heading "Accessible" [level=3]
  - paragraph: Readable type, clear focus, reduced motion, and room to go at your own pace.
  - text: ⌂
  - heading "Privacy-aware" [level=3]
  - paragraph: Only the information needed for a thoughtful screening experience belongs here.
  - text: ✧
  - heading "Non-diagnostic" [level=3]
  - paragraph: We describe observed patterns, never a label or a clinical conclusion.
  - text: ✦ Your next little step
  - heading "Ready to explore?" [level=2]
  - paragraph: Come see what learning can look like when curiosity leads the way.
  - link "Start Dyscover →":
    - /url: /child/home
  - text: ✦
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
  4  |   test.beforeEach(async ({ page }) => {
  5  |     await page.goto('/');
  6  |   });
  7  | 
  8  |   test('should show registration form', async ({ page }) => {
> 9  |     await expect(page.locator('text=Register')).toBeVisible();
     |                                                 ^ Error: expect(locator).toBeVisible() failed
  10 |     await expect(page.locator('input[type="email"]')).toBeVisible();
  11 |     await expect(page.locator('input[type="password"]')).toBeVisible();
  12 |     await expect(page.locator('button:has-text("Register")')).toBeVisible();
  13 |   });
  14 | 
  15 |   test('should register a new user', async ({ page }) => {
  16 |     await page.fill('input[type="email"]', 'test@example.com');
  17 |     await page.fill('input[type="password"]', 'password123');
  18 |     await page.fill('input[name="display_name"]', 'Test User');
  19 |     await page.click('button:has-text("Register")');
  20 |     await expect(page.locator('text=Registration successful')).toBeVisible();
  21 |   });
  22 | 
  23 |   test('should login with registered user', async ({ page }) => {
  24 |     await page.fill('input[type="email"]', 'test@example.com');
  25 |     await page.fill('input[type="password"]', 'password123');
  26 |     await page.click('button:has-text("Login")');
  27 |     await expect(page.locator('text=Welcome')).toBeVisible();
  28 |   });
  29 | 
  30 |   test('should logout', async ({ page }) => {
  31 |     await page.fill('input[type="email"]', 'test@example.com');
  32 |     await page.fill('input[type="password"]', 'password123');
  33 |     await page.click('button:has-text("Login")');
  34 |     await expect(page.locator('text=Welcome')).toBeVisible();
  35 |     await page.click('button:has-text("Logout")');
  36 |     await expect(page.locator('text=Login')).toBeVisible();
  37 |   });
  38 | });
  39 | 
  40 | test.describe('Child Profile Management', () => {
  41 |   test.beforeEach(async ({ page }) => {
  42 |     await page.goto('/');
  43 |     await page.fill('input[type="email"]', 'test@example.com');
  44 |     await page.fill('input[type="password"]', 'password123');
  45 |     await page.click('button:has-text("Login")');
  46 |   });
  47 | 
  48 |   test('should create a child profile', async ({ page }) => {
  49 |     await page.click('button:has-text("Add Child")');
  50 |     await page.fill('input[name="display_name"]', 'Test Child');
  51 |     await page.click('button:has-text("Create")');
  52 |     await expect(page.locator('text=Test Child')).toBeVisible();
  53 |   });
  54 | });
  55 | 
  56 | test.describe('Assessment Flow', () => {
  57 |   test.beforeEach(async ({ page }) => {
  58 |     await page.goto('/');
  59 |     await page.fill('input[type="email"]', 'test@example.com');
  60 |     await page.fill('input[type="password"]', 'password123');
  61 |     await page.click('button:has-text("Login")');
  62 |   });
  63 | 
  64 |   test('should start an assessment', async ({ page }) => {
  65 |     await page.click('button:has-text("Start Assessment")');
  66 |     await expect(page.locator('text=Letter Detective')).toBeVisible();
  67 |   });
  68 | });
```