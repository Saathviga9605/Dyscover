import { expect, test } from '@playwright/test';
import {
  PASSWORD,
  apiAs,
  createChildViaUi,
  expectNoSeriousA11yViolations,
  loginViaUi,
  registerViaUi,
  uniqueEmail,
} from './fixtures';

test.describe('accounts and protected routes', () => {
  test('protected pages redirect anonymous visitors to login and back', async ({ page }) => {
    await page.goto('/parent/dashboard');
    await expect(page).toHaveURL(/\/login\?next=%2Fparent%2Fdashboard/);
    await page.goto('/child/assessment/visual');
    await expect(page).toHaveURL(/\/login\?next=/);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  });

  test('register, keep the session across reload, log out, log back in', async ({ page }) => {
    const email = await registerViaUi(page, 'parent', 'Pat Parent');
    await expect(page.getByRole('heading', { name: 'Child profiles' })).toBeVisible();

    // The access token is memory-only; reload restores the session from the HttpOnly cookie.
    await page.reload();
    await expect(page).toHaveURL(/\/parent\/dashboard/);
    await expect(page.getByRole('link', { name: /Account · Pat Parent/ })).toBeVisible();
    expect(await page.evaluate(() => JSON.stringify(window.localStorage))).not.toContain('eyJ');

    await page.getByRole('button', { name: 'Log out' }).click();
    await expect(page.getByRole('link', { name: 'Log in' })).toBeVisible();
    await page.goto('/parent/dashboard');
    await expect(page).toHaveURL(/\/login/);

    await loginViaUi(page, email, 'wrong-password');
    await expect(page.getByRole('alert')).toContainText('Invalid email or password');
    await loginViaUi(page, email);
    await expect(page).toHaveURL(/\/parent\/dashboard/);
  });

  test('login returns to the originally requested page', async ({ page, request }) => {
    const email = uniqueEmail('next');
    await request.post('/api/auth/register', {
      data: { email, password: PASSWORD, display_name: 'Next', role: 'parent' },
    });
    await page.goto('/account');
    await expect(page).toHaveURL(/\/login\?next=%2Faccount/);
    await page.getByLabel('Email').fill(email);
    await page.getByLabel('Password').fill(PASSWORD);
    await page.getByRole('button', { name: 'Log in' }).click();
    await expect(page).toHaveURL(/\/account$/);
    await expect(page.getByRole('heading', { name: 'Account and privacy' })).toBeVisible();
  });

  test('registration validates the password confirmation', async ({ page }) => {
    await page.goto('/register');
    await page.getByLabel('Display name').fill('X');
    await page.getByLabel('Email').fill(uniqueEmail('mismatch'));
    await page.getByLabel('Password', { exact: true }).fill(PASSWORD);
    await page.getByLabel('Confirm password').fill('something-else');
    await page.getByRole('button', { name: 'Create account' }).click();
    await expect(page.getByRole('alert')).toContainText('Passwords do not match');
  });

  test('educators cannot open the parent workspace', async ({ page }) => {
    await registerViaUi(page, 'educator', 'Ms Teacher');
    await page.goto('/parent/dashboard');
    await expect(
      page.getByRole('heading', { name: 'This area is for a different account type' })
    ).toBeVisible();
  });
});

test.describe('child profiles and educator sharing', () => {
  test('parent creates a child, shares with an educator, then revokes', async ({
    browser,
    request,
  }) => {
    const educatorContext = await browser.newContext();
    const educatorPage = await educatorContext.newPage();
    const educatorEmail = await registerViaUi(educatorPage, 'educator', 'Ms Rivera');
    await expect(educatorPage.getByText('No learners shared with you yet')).toBeVisible();

    const parentContext = await browser.newContext();
    const page = await parentContext.newPage();
    const parentEmail = await registerViaUi(page, 'parent', 'Sam Parent');
    await createChildViaUi(page, 'Ava');
    await expectNoSeriousA11yViolations(page, 'parent dashboard');

    await page.getByLabel('Educator’s account email').fill('nobody@example.com');
    await page.getByRole('button', { name: 'Share' }).click();
    await expect(page.getByRole('alert')).toContainText('No educator account uses that email');

    await page.getByLabel('Educator’s account email').fill(educatorEmail);
    await page.getByRole('button', { name: 'Share' }).click();
    await expect(page.getByText('Access shared.')).toBeVisible();
    await expect(page.getByText('Ms Rivera')).toBeVisible();

    await educatorPage.reload();
    await expect(educatorPage.getByRole('heading', { name: 'Ava' })).toBeVisible();
    await expect(educatorPage.getByText('No activity evidence yet')).toBeVisible();

    await page.getByRole('button', { name: 'Remove' }).click();
    await page.getByRole('button', { name: 'Remove access' }).click();
    await expect(page.getByText('Not shared with any educator.')).toBeVisible();
    await educatorPage.reload();
    await expect(educatorPage.getByText('No learners shared with you yet')).toBeVisible();

    const api = await apiAs(request, parentEmail);
    const children = await api.get<Array<{ display_name: string }>>('/children');
    expect(children.map(child => child.display_name)).toEqual(['Ava']);
    await educatorContext.close();
    await parentContext.close();
  });
});
