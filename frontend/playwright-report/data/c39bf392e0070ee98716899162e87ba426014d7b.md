# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: auth.spec.ts >> Authentication Flow >> should login with registered user
- Location: e2e\auth.spec.ts:23:3

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: page.fill: Test timeout of 30000ms exceeded.
Call log:
  - waiting for locator('input[type="email"]')

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
      - button "Open accessibility settings" [ref=e20] [cursor=pointer]: Aa
  - main [ref=e21]:
    - generic [ref=e22]:
      - generic: ✦
      - generic: +
      - generic: a
      - generic [ref=e23]:
        - generic [ref=e24]: A little world for curious minds
        - heading "Discover how you learn." [level=1] [ref=e25]
        - paragraph [ref=e26]: Every mind has its own way of finding the words. Dyscover makes early learning patterns easier to notice, understand, and support.
        - generic [ref=e27]:
          - link "Start the adventure →" [ref=e28] [cursor=pointer]:
            - /url: /child/home
            - text: Start the adventure
            - generic [ref=e29]: →
          - link "See how it works ↗" [ref=e30] [cursor=pointer]:
            - /url: /how-it-works
            - text: See how it works
            - generic [ref=e31]: ↗
        - paragraph [ref=e32]:
          - generic [ref=e33]: ✦
          - text: Gentle activities. Clearer conversations. No labels.
      - generic [ref=e34]:
        - generic [ref=e41]: abc
        - generic [ref=e43]: ✦
        - generic [ref=e44]: ✦
        - img "Dyscover companion" [ref=e45]:
          - generic [ref=e46]: ✦
          - generic [ref=e47]: ✦
    - generic [ref=e54]:
      - generic [ref=e55]:
        - generic [ref=e56]: Learning looks different for everyone
        - heading "Noticing is the first step." [level=2] [ref=e57]
        - paragraph [ref=e58]: Good support starts with curiosity, not assumptions. Dyscover uses short, playful activities to build a fuller picture of how a child interacts with words, symbols, and patterns.
      - generic [ref=e59]:
        - generic [ref=e60]:
          - text: "01"
          - generic [ref=e61]: ↻
          - heading "Play without pressure" [level=3] [ref=e62]
          - paragraph [ref=e63]: Small activities feel like an adventure, not a test.
          - link "Meet the explorer →" [ref=e64] [cursor=pointer]:
            - /url: /child/home
        - generic [ref=e65]:
          - text: "02"
          - generic [ref=e66]: ✦
          - heading "Notice the patterns" [level=3] [ref=e67]
          - paragraph [ref=e68]: We keep useful observations connected to each activity.
          - link "See our approach →" [ref=e69] [cursor=pointer]:
            - /url: /research
        - generic [ref=e70]:
          - text: "03"
          - generic [ref=e71]: ⌁
          - heading "Grow the conversation" [level=3] [ref=e72]
          - paragraph [ref=e73]: Clearer information can lead to more helpful next steps.
          - link "Why it matters →" [ref=e74] [cursor=pointer]:
            - /url: /about
    - generic [ref=e75]:
      - generic [ref=e76]:
        - generic [ref=e79]: ✦
        - generic [ref=e81]: Timing
        - generic [ref=e82]: choices
        - generic [ref=e83]: words
        - generic [ref=e84]: focus
      - generic [ref=e85]:
        - generic [ref=e86]: A fuller picture
        - heading "Built around the way children interact." [level=2] [ref=e87]
        - paragraph [ref=e88]: Every response tells a small part of the story. Dyscover can organize accuracy, reaction time, hesitation, and interaction events at the trial level. Optional gaze research stays separate and consent-based.
        - generic [ref=e89]:
          - generic [ref=e90]:
            - strong [ref=e91]: "01"
            - generic [ref=e92]: Response
          - generic [ref=e93]:
            - strong [ref=e94]: "02"
            - generic [ref=e95]: Timing
          - generic [ref=e96]:
            - strong [ref=e97]: "03"
            - generic [ref=e98]: Interaction
        - link "Explore the research direction ↗" [ref=e99] [cursor=pointer]:
          - /url: /research
          - text: Explore the research direction
          - generic [ref=e100]: ↗
    - generic [ref=e101]:
      - generic [ref=e102]:
        - generic [ref=e103]: For grown-ups
        - heading "A calmer view of the journey." [level=2] [ref=e104]
        - paragraph [ref=e105]: The parent space is designed for thoughtful conversations, not alarming scores.
      - generic [ref=e106]:
        - generic [ref=e107]: Alex's Dyscover journey Demo view
        - generic [ref=e112]:
          - generic [ref=e113]:
            - generic [ref=e114]: Good morning
            - heading "Let's see what Alex explored." [level=3] [ref=e115]
            - paragraph [ref=e116]: Latest screening · just now
          - generic [ref=e125]:
            - generic [ref=e126]: Play without pressure
            - generic [ref=e127]: Notice the patterns
            - generic [ref=e128]: Grow the conversation
          - generic [ref=e129]:
            - generic [ref=e130]:
              - generic [ref=e131]: Observed areas
              - strong [ref=e132]: "04"
            - generic [ref=e133]:
              - generic [ref=e134]: Activities
              - strong [ref=e135]: "--"
            - generic [ref=e136]:
              - generic [ref=e137]: Next step
              - strong [ref=e138]: Ready
      - link "Visit the parent space ↗" [ref=e139] [cursor=pointer]:
        - /url: /parent/dashboard
        - text: Visit the parent space
        - generic [ref=e140]: ↗
    - generic [ref=e141]:
      - img "Dyscover companion" [ref=e142]:
        - generic [ref=e143]: ✦
        - generic [ref=e144]: ✦
      - generic [ref=e151]:
        - generic [ref=e152]: A friendly guide
        - heading "Meet Lexi." [level=2] [ref=e153]
        - paragraph [ref=e154]: A gentle companion for questions, hints, and the next little step.
      - button "Say hello →" [ref=e155] [cursor=pointer]:
        - text: Say hello
        - generic [ref=e156]: →
    - generic [ref=e157]:
      - generic [ref=e158]:
        - generic [ref=e159]: Designed with care
        - heading "Warmth and intelligence, together." [level=2] [ref=e160]
      - generic [ref=e161]:
        - generic [ref=e162]:
          - generic [ref=e163]: ◌
          - heading "Accessible" [level=3] [ref=e164]
          - paragraph [ref=e165]: Readable type, clear focus, reduced motion, and room to go at your own pace.
        - generic [ref=e166]:
          - generic [ref=e167]: ⌂
          - heading "Privacy-aware" [level=3] [ref=e168]
          - paragraph [ref=e169]: Only the information needed for a thoughtful screening experience belongs here.
        - generic [ref=e170]:
          - generic [ref=e171]: ✧
          - heading "Non-diagnostic" [level=3] [ref=e172]
          - paragraph [ref=e173]: We describe observed patterns, never a label or a clinical conclusion.
    - generic [ref=e174]:
      - text: ✦
      - generic [ref=e175]: Your next little step
      - heading "Ready to explore?" [level=2] [ref=e176]
      - paragraph [ref=e177]: Come see what learning can look like when curiosity leads the way.
      - link "Start Dyscover →" [ref=e178] [cursor=pointer]:
        - /url: /child/home
        - text: Start Dyscover
        - generic [ref=e179]: →
      - text: ✦
  - contentinfo [ref=e180]:
    - generic [ref=e181]:
      - link "✦ Dyscover" [ref=e182] [cursor=pointer]:
        - /url: /
        - generic [ref=e183]: ✦
        - text: Dyscover
      - paragraph [ref=e184]: A little world built around how children learn.
    - generic [ref=e185]:
      - link "About" [ref=e186] [cursor=pointer]:
        - /url: /about
      - link "Contact" [ref=e187] [cursor=pointer]:
        - /url: /contact
      - link "Research" [ref=e188] [cursor=pointer]:
        - /url: /research
    - generic [ref=e189]: Dyscover is a non-diagnostic screening and support experience.
  - button "Open Lexi" [ref=e191] [cursor=pointer]:
    - text: L
    - generic [ref=e192]: Lexi
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
  9  |     await expect(page.locator('text=Register')).toBeVisible();
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
> 24 |     await page.fill('input[type="email"]', 'test@example.com');
     |                ^ Error: page.fill: Test timeout of 30000ms exceeded.
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