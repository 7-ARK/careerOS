import {test, expect} from './fixtures';
import {
  approveCurrentDraft,
  authenticatedRequestContext,
  createPrivateProfile,
  downloadApprovedPdf,
  expectAuthenticationScreen,
  login,
  register,
  submitManualJob,
} from './acceptance-helpers';

/**
 * Authenticated browser journeys.
 *
 * These tests exercise the real frontend and backend:
 *   - isolated users are created through the registration form;
 *   - login state is preserved in localStorage and survives a page reload;
 *   - authenticated navigation reaches the resume workspace.
 *
 * Same-origin `/api` requests reach the test backend through Vite's loopback proxy.
 */

test('isolated user can register and land on the workspace', async ({authenticatedPage, isolatedUser}) => {
  await expect(authenticatedPage.getByRole('banner')).toContainText(isolatedUser.fullName);
  await expect(authenticatedPage.getByRole('heading', {name: 'Tailor a resume for one job posting.'})).toBeVisible();
  await expect(authenticatedPage.getByRole('button', {name: 'Logout'})).toBeVisible();
});

test('login restores session for an existing isolated user', async ({page, isolatedUser}) => {
  await page.goto('/');
  await register(page, isolatedUser);

  await page.getByRole('button', {name: 'Logout'}).click();
  await expectAuthenticationScreen(page);
  await login(page, isolatedUser);

  const api = await authenticatedRequestContext(page);
  try {
    const response = await api.get('/api/v1/auth/me');
    expect(response.ok()).toBeTruthy();
    expect(await response.json()).toMatchObject({
      email: isolatedUser.email,
      full_name: isolatedUser.fullName,
    });
  } finally {
    await api.dispose();
  }
});

test('login state survives a page reload', async ({authenticatedPage, isolatedUser}) => {
  await authenticatedPage.reload();
  await expect(authenticatedPage.getByRole('banner')).toContainText(isolatedUser.fullName);
  await expect(authenticatedPage.getByRole('heading', {name: 'Tailor a resume for one job posting.'})).toBeVisible();
});

test('isolated user creates a private profile and downloads a tailored PDF resume', async ({page, isolatedUser}) => {
  await page.goto('/');
  await register(page, isolatedUser);

  await page.getByRole('button', {name: 'Logout'}).click();
  await login(page, isolatedUser);

  const profileId = await createPrivateProfile(page, {
    fullName: 'Flow A Candidate',
    skills: ['TypeScript'],
    projects: [
      {
        name: 'Resume Builder',
        description: 'Built a truthful resume generation workflow.',
        technologies: 'TypeScript, React',
      },
    ],
  });
  expect(profileId).not.toBe('');

  await submitManualJob(page, {
    title: 'Senior TypeScript Engineer',
    company: 'Acme Career Tools',
    location: 'Remote',
    description: 'Acme Career Tools needs a Senior TypeScript Engineer to build React resume workflows. Required skills include TypeScript, React, and clear communication.',
  });

  const results = page.locator('#analysis-results');
  await expect(results.getByRole('heading', {name: 'Senior TypeScript Engineer', exact: true})).toBeVisible();
  await expect(results.getByText('Acme Career Tools', {exact: true})).toBeVisible();
  await expect(results.getByRole('heading', {name: 'Requirement-to-evidence map'})).toBeVisible();
  await expect(results.getByText('TypeScript', {exact: true}).first()).toBeVisible();
  await expect(results.getByText('Resume Builder', {exact: true}).first()).toBeVisible();

  await approveCurrentDraft(page);
  await downloadApprovedPdf(page);
});

