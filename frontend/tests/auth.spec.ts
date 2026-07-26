import {test, expect} from './fixtures';

/**
 * Authenticated browser journeys.
 *
 * These tests exercise the real frontend and backend:
 *   - isolated users are created through the registration form;
 *   - login state is preserved in localStorage and survives a page reload;
 *   - authenticated navigation reaches the resume workspace.
 *
 * The backend must be running at VITE_API_BASE_URL (default http://127.0.0.1:8000).
 */

test('isolated user can register and land on the workspace', async ({authenticatedPage, isolatedUser}) => {
  await expect(authenticatedPage.getByRole('banner')).toContainText(isolatedUser.fullName);
  await expect(authenticatedPage.getByRole('heading', {name: 'Tailor a resume for one job posting.'})).toBeVisible();
  await expect(authenticatedPage.getByRole('button', {name: 'Logout'})).toBeVisible();
});

test('login restores session for an existing isolated user', async ({page, isolatedUser}) => {
  // Register the isolated user first.
  await page.goto('/');
  await page.getByRole('button', {name: 'Register'}).click();
  await page.getByLabel('Full name').fill(isolatedUser.fullName);
  await page.getByLabel('Email').fill(isolatedUser.email);
  await page.getByLabel('Password').fill(isolatedUser.password);
  await page.getByRole('button', {name: 'Create account'}).click();
  await expect(page.getByRole('heading', {name: 'Tailor a resume for one job posting.'})).toBeVisible();

  // Log out and log back in.
  await page.getByRole('button', {name: 'Logout'}).click();
  // AuthScreen renders this copy in a paragraph, not a heading; match the rendered element.
  await expect(page.getByText(/Sign in to manage candidate profiles/)).toBeVisible();

  await page.getByLabel('Email').fill(isolatedUser.email);
  await page.getByLabel('Password').fill(isolatedUser.password);
  // In login mode AuthScreen renders both a "Login" mode toggle and the form
  // submit button; target the submit button inside the form.
  await page.locator('form').getByRole('button', {name: 'Login'}).click();

  await expect(page.getByRole('banner')).toContainText(isolatedUser.fullName);
  await expect(page.getByRole('heading', {name: 'Tailor a resume for one job posting.'})).toBeVisible();
});

test('login state survives a page reload', async ({authenticatedPage, isolatedUser}) => {
  await authenticatedPage.reload();
  await expect(authenticatedPage.getByRole('banner')).toContainText(isolatedUser.fullName);
  await expect(authenticatedPage.getByRole('heading', {name: 'Tailor a resume for one job posting.'})).toBeVisible();
});
