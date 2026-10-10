import {expect, test} from './fixtures';
import {register} from './acceptance-helpers';

test('a new user sees distinct empty profile and resume history states', async ({page, isolatedUser}) => {
  await page.goto('/');
  await register(page, isolatedUser);

  await expect(page.getByText('No candidate profiles yet. Create one to start tailoring resumes.', {exact: true})).toBeVisible();
  await expect(
    page.getByText('No profile selected yet, so there is no resume history to show.', {exact: true}),
  ).toBeVisible();
  await expect(page.getByRole('alert')).not.toBeVisible();
});

test('profile validation failures keep entered values available for correction', async ({page, isolatedUser}) => {
  await page.goto('/');
  await register(page, isolatedUser);

  await page.route('**/api/v1/candidates', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 422,
      contentType: 'application/json',
      body: JSON.stringify({
        error: {
          code: 'validation_error',
          message: 'Provide a complete LinkedIn URL before saving this profile.',
          details: [],
        },
      }),
    });
  });

  await page.getByRole('button', {name: 'New candidate profile', exact: true}).click();
  await page.getByRole('textbox', {name: 'Full name'}).fill('Retained Candidate');
  await page.getByRole('textbox', {name: 'Professional headline'}).fill('Platform Engineer');
  await page.getByRole('button', {name: 'Create profile', exact: true}).last().click();

  await expect(page.getByRole('alert')).toHaveText('Provide a complete LinkedIn URL before saving this profile.');
  await expect(page.getByRole('textbox', {name: 'Full name'})).toHaveValue('Retained Candidate');
  await expect(page.getByRole('textbox', {name: 'Professional headline'})).toHaveValue('Platform Engineer');
  await expect(page.getByRole('textbox', {name: 'Full name'})).toBeEditable();
  await expect(page.getByRole('textbox', {name: 'Professional headline'})).toBeEditable();
});

