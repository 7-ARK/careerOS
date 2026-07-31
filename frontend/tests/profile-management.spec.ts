import {expect, test} from './fixtures';
import {register} from './acceptance-helpers';

test('profile edits persist after reload and remain selected for resume generation', async ({page, isolatedUser}) => {
  await page.goto('/');
  await register(page, isolatedUser);

  await page.getByRole('button', {name: 'Create profile', exact: true}).click();
  await page.getByRole('textbox', {name: 'Full name'}).fill('Persistent Profile Candidate');
  await page.getByRole('button', {name: 'Create profile', exact: true}).last().click();

  await expect(
    page.getByRole('heading', {name: 'Persistent Profile Candidate', exact: true}),
  ).toBeVisible();
  await page.getByRole('button', {name: 'Edit profile'}).click();
  await page
    .getByRole('textbox', {name: 'Professional headline'})
    .fill('Reloaded Platform Engineer');
  await page.getByRole('button', {name: 'Save changes', exact: true}).click();

  await page.reload();

  await expect(page.getByLabel('Candidate profile')).toHaveText('Persistent Profile Candidate');
  await expect(
    page.getByRole('heading', {name: 'Persistent Profile Candidate', exact: true}),
  ).toBeVisible();
  await expect(page.getByText('Reloaded Platform Engineer', {exact: true})).toBeVisible();
  await expect(
    page.getByRole('heading', {name: 'Tailor a resume for one job posting.'}),
  ).toBeVisible();
});
