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

test('isolated user creates a private profile and downloads a tailored PDF resume', async ({page, isolatedUser}) => {
  await page.goto('/');
  await page.getByRole('button', {name: 'Register'}).click();
  await page.getByLabel('Full name').fill(isolatedUser.fullName);
  await page.getByLabel('Email').fill(isolatedUser.email);
  await page.getByLabel('Password').fill(isolatedUser.password);
  await page.getByRole('button', {name: 'Create account'}).click();
  await expect(page.getByRole('heading', {name: 'Tailor a resume for one job posting.'})).toBeVisible();

  await page.getByRole('button', {name: 'Logout'}).click();
  await page.getByLabel('Email').fill(isolatedUser.email);
  await page.getByLabel('Password').fill(isolatedUser.password);
  await page.locator('form').getByRole('button', {name: 'Login'}).click();
  await expect(page.getByRole('banner')).toContainText(isolatedUser.fullName);

  await page.getByRole('button', {name: 'Create profile', exact: true}).click();
  await page.getByLabel('Full name').fill('Flow A Candidate');

  const skillsSection = page.getByRole('heading', {name: 'Skills', exact: true}).locator('..');
  await skillsSection.getByRole('button', {name: 'Add', exact: true}).click();
  await page.getByLabel('Skill').fill('TypeScript');

  const projectsSection = page.getByRole('heading', {name: 'Projects', exact: true}).locator('..');
  await projectsSection.getByRole('button', {name: 'Add', exact: true}).click();
  await page.getByLabel('Project name').fill('Resume Builder');
  await page.getByLabel('Description').fill('Built a truthful resume generation workflow.');
  await page.getByLabel('Technologies (comma separated)').fill('TypeScript, React');

  await page.locator('form').getByRole('button', {name: 'Create profile', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Flow A Candidate', exact: true})).toBeVisible();
  await expect(page.getByLabel('Candidate profile')).toHaveText('Flow A Candidate');

  await page.getByRole('button', {name: 'Paste job manually', exact: true}).click();
  await page.getByLabel('Job title').fill('Senior TypeScript Engineer');
  await page.getByRole('textbox', {name: 'Company', exact: true}).fill('Acme Career Tools');
  await page.getByLabel('Location').fill('Remote');
  await page.getByLabel('Source platform').selectOption('company');
  await page.getByLabel('Job description').fill(
    'Acme Career Tools needs a Senior TypeScript Engineer to build React resume workflows. Required skills include TypeScript, React, and clear communication.',
  );
  await page.getByRole('button', {name: 'Generate resume', exact: true}).click();

  await expect(page.getByRole('heading', {name: 'Senior TypeScript Engineer', exact: true})).toBeVisible();
  await expect(page.getByText('Acme Career Tools', {exact: true})).toBeVisible();
  await expect(page.getByText('Match Summary', {exact: true})).toBeVisible();
  const resultPanel = page.getByRole('complementary');
  await expect(resultPanel.getByText('TypeScript', {exact: true})).toBeVisible();
  await expect(resultPanel.getByText('Resume Builder', {exact: true})).toBeVisible();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', {name: 'Download resume', exact: true}).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  if (!stream) {
    throw new Error('The generated resume download did not provide a readable stream.');
  }
  const chunks: Uint8Array[] = [];
  for await (const chunk of stream) {
    chunks.push(chunk as Uint8Array);
  }
  const artifact = Buffer.concat(chunks);
  expect(artifact.length).toBeGreaterThan(0);
  expect(artifact.subarray(0, 5).toString('ascii')).toBe('%PDF-');
});
