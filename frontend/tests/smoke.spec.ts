import {test, expect} from '@playwright/test';

/**
 * Minimal smoke test: the frontend builds, serves, and reaches the auth screen.
 * This test intentionally does not require the backend to be running.
 */
test('landing page shows the authentication screen', async ({page}) => {
  await page.goto('/');

  await expect(page.getByText('careerOS')).toBeVisible();
  await expect(page.getByText(/Sign in to manage candidate profiles/)).toBeVisible();
  // AuthScreen renders two "Login" buttons in login mode: the mode toggle and
  // the form submit button. Assert both, scoping the submit lookup to the form.
  await expect(page.getByRole('button', {name: 'Login'}).first()).toBeVisible();
  await expect(page.locator('form').getByRole('button', {name: 'Login'})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Register'})).toBeVisible();
  await expect(page.getByLabel('Email')).toBeVisible();
  await expect(page.getByLabel('Password')).toBeVisible();
});
