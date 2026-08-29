import {expect, test} from '@playwright/test';

async function resetSession(page: import('@playwright/test').Page) {
  await page.goto('/#/landing');
  await page.evaluate(() => {
    localStorage.removeItem('swasthyanet-token');
    localStorage.removeItem('swasthyanet-user');
    localStorage.removeItem('swasthyanet-theme');
  });
  await page.reload();
}

async function signIn(page: import('@playwright/test').Page, username: string, password: string) {
  await page.goto('/#/login');
  await page.getByLabel('Username').fill(username);
  await page.locator('input[autocomplete="current-password"]').fill(password);
  await page.getByRole('button', {name: 'Sign in securely'}).click();
  await expect(page.getByText('NETWORK ONLINE')).toBeVisible();
}

test.describe('public theme and authentication flows', () => {
  test('landing page routes to login and theme preference persists', async ({page}) => {
    await resetSession(page);
    await expect(page.getByRole('heading', {name: 'See the signal.'})).toBeVisible();
    await expect(page.getByRole('button', {name: 'Get started'})).toBeVisible();

    await page.getByRole('button', {name: 'Switch to dark mode'}).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await page.reload();
    await expect(page.getByRole('button', {name: 'Switch to light mode'})).toBeVisible();

    await page.getByRole('button', {name: 'Get started'}).click();
    await expect(page).toHaveURL(/#\/login$/);
    await expect(page.getByText('Coordinate care')).toBeVisible();
  });

  test('password visibility control reveals and hides the password', async ({page}) => {
    await resetSession(page);
    await page.goto('/#/login');
    const password = page.locator('input[autocomplete="current-password"]');
    await expect(password).toHaveAttribute('type', 'password');
    await page.getByRole('button', {name: 'Show password'}).click();
    await expect(password).toHaveAttribute('type', 'text');
    await expect(page.getByRole('button', {name: 'Hide password'})).toBeVisible();
    await page.getByRole('button', {name: 'Hide password'}).click();
    await expect(password).toHaveAttribute('type', 'password');
  });

  test('state official can sign in, navigate pages, and sign out', async ({page}) => {
    await resetSession(page);
    await signIn(page, 'state.official', 'State@2026');
    await expect(page.getByText('STATE OFFICIAL', {exact: true})).toBeVisible();
    await expect(page.getByRole('button', {name: 'Simulate update'})).toBeVisible();

    for (const [name, heading] of [
      ['Outbreak intelligence', 'Disease outbreak trends'],
      ['Supply logistics', 'LIVE CAPACITY PULSE'],
      ['Federation & reports', 'Federated learning boundary'],
    ]) {
      await page.getByRole('button', {name}).click();
      await expect(page.getByText(heading)).toBeVisible();
    }

    await page.getByRole('button', {name: 'Sign out'}).click();
    await expect(page).toHaveURL(/#\/login$/);
    await expect(page.getByRole('button', {name: 'Sign in securely'})).toBeVisible();
  });

  test('PHC administrator receives scoped access and no state simulation control', async ({page}) => {
    await resetSession(page);
    await signIn(page, 'rajapur.admin', 'Rajapur@2026');
    await expect(page.getByText('PHC ADMIN', {exact: true})).toBeVisible();
    await expect(page.getByRole('heading', {name: 'Rajapur PHC operational health'})).toBeVisible();
    await expect(page.getByRole('button', {name: 'Simulate update'})).toHaveCount(0);
    await expect(page.getByText('State official')).toHaveCount(0);
  });
});
