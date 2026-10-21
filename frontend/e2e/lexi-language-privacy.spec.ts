import { expect, test } from '@playwright/test';
import {
  PASSWORD,
  apiAs,
  createChildViaUi,
  expectNoSeriousA11yViolations,
  loginViaUi,
  registerViaUi,
} from './fixtures';

test.describe('Lexi', () => {
  test('asks a signed-out visitor to sign in', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Open Lexi, the Dyscover guide' }).click();
    await expect(page.getByText('A grown-up needs to sign in before we can chat')).toBeVisible();
  });

  test('persists conversations and sends prior turns as context', async ({ page }) => {
    await registerViaUi(page, 'parent', 'Lex Parent');
    await page.getByRole('button', { name: 'Open Lexi, the Dyscover guide' }).click();
    const dialog = page.getByRole('dialog', { name: 'Lexi' });
    await expect(dialog.getByText(/AI assistant \(Groq\)/)).toBeVisible();
    await expectNoSeriousA11yViolations(page, 'Lexi panel');

    const input = dialog.getByLabel('Message Lexi');
    await input.fill('What is Mirror Match?');
    await input.press('Enter');
    // The e2e backend uses a labelled echo provider at the model boundary.
    await expect(
      dialog.getByText('[test reply] You said: What is Mirror Match? (context turns: 1)')
    ).toBeVisible();

    await input.fill('Can we play it?');
    await dialog.getByRole('button', { name: 'Send' }).click();
    await expect(dialog.getByText('(context turns: 3)')).toBeVisible();

    // History survives a reload (server-side persistence).
    await page.reload();
    await page.getByRole('button', { name: 'Open Lexi, the Dyscover guide' }).click();
    await expect(page.getByText('You said: Can we play it?')).toBeVisible();

    // A new conversation starts without context; old one remains in history.
    await page.getByRole('button', { name: 'New conversation' }).click();
    await page.getByLabel('Message Lexi').fill('Hello again');
    await page.getByLabel('Message Lexi').press('Enter');
    await expect(page.getByText('You said: Hello again (context turns: 1)')).toBeVisible();
    await page.getByRole('button', { name: 'Past conversations' }).click();
    await expect(
      page
        .getByRole('navigation', { name: 'Past conversations' })
        .getByRole('button', { name: 'What is Mirror Match?', exact: true })
    ).toBeVisible();

    // Escape closes the panel and returns focus to the toggle.
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog', { name: 'Lexi' })).toBeHidden();
    await expect(page.getByRole('button', { name: 'Open Lexi, the Dyscover guide' })).toBeFocused();
  });
});

test.describe('English and Tamil', () => {
  test('switching language updates the interface and honest availability', async ({ page }) => {
    await registerViaUi(page, 'parent', 'Lang Parent');
    await createChildViaUi(page, 'Kavi');
    await page.getByLabel('Choose your language').selectOption('ta');
    await expect(page.getByRole('link', { name: 'பெரியவர்களுக்கு' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'குழந்தை சுயவிவரங்கள்' })).toBeVisible();
    await expect(page.locator('html')).toBeVisible();

    // Speech games are curated in English only and are reported as unavailable in Tamil.
    await page.goto('/child/assessment');
    await expect(page.locator('.hub-unavailable')).toBeVisible();

    // The choice persists across reloads.
    await page.reload();
    await expect(
      page.getByLabel('உங்கள் மொழியைத் தேர்ந்தெடுக்கவும்').or(page.getByRole('combobox')).first()
    ).toHaveValue('ta');
    await page.getByRole('combobox').first().selectOption('en');
    await expect(page.getByRole('link', { name: 'For parents' })).toBeVisible();
  });
});

test.describe('privacy', () => {
  test('data summary, export download and account deletion', async ({ page, request }) => {
    const email = await registerViaUi(page, 'parent', 'Priv Parent');
    await createChildViaUi(page, 'Mia');
    await page.goto('/account');
    await expect(page.getByRole('heading', { name: 'Your data' })).toBeVisible();
    await expect(page.locator('dl').filter({ hasText: 'Child profiles' })).toContainText('1');
    await expectNoSeriousA11yViolations(page, 'account page');

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download all my data' }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/^dyscover-export-\d{4}-\d{2}-\d{2}\.zip$/);

    const deleteButton = page.getByRole('button', { name: 'Delete my account' });
    await page.locator('#delete_password').fill(PASSWORD);
    await expect(deleteButton).toBeDisabled();
    await page.getByLabel('Type DELETE to confirm').fill('DELETE');
    await deleteButton.click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole('link', { name: 'Log in' })).toBeVisible();

    const login = await request.post('/api/auth/login', { data: { email, password: PASSWORD } });
    expect(login.status()).toBe(401);
    await loginViaUi(page, email);
    await expect(page.getByRole('alert')).toContainText('Invalid email or password');
  });

  test('another parent cannot see someone else’s child', async ({ browser, request }) => {
    const ownerPage = await (await browser.newContext()).newPage();
    const ownerEmail = await registerViaUi(ownerPage, 'parent', 'Owner');
    await createChildViaUi(ownerPage, 'Private Child');
    const owner = await apiAs(request, ownerEmail);
    const [child] = await owner.get<Array<{ id: string }>>('/children');

    const intruderPage = await (await browser.newContext()).newPage();
    const intruderEmail = await registerViaUi(intruderPage, 'parent', 'Intruder');
    const login = await request.post('/api/auth/login', {
      data: { email: intruderEmail, password: PASSWORD },
    });
    const { access_token: token } = await login.json();
    const response = await request.get(`/api/children/${child.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(response.status()).toBe(404);
    await expect(intruderPage.getByText('Private Child')).toHaveCount(0);
  });
});

test.describe('mobile layout @mobile', () => {
  test('dashboard and Lexi fit a phone screen without horizontal scrolling @mobile', async ({
    page,
  }) => {
    await registerViaUi(page, 'parent', 'Phone Parent');
    await createChildViaUi(page, 'Ada');
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth
    );
    expect(overflow).toBeLessThanOrEqual(1);
    await page.getByRole('button', { name: 'Open Lexi, the Dyscover guide' }).click();
    const box = await page.getByRole('dialog', { name: 'Lexi' }).boundingBox();
    const viewport = page.viewportSize();
    expect(box && viewport && box.width <= viewport.width + 1).toBeTruthy();
  });
});
