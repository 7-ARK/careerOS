import {test, expect} from './fixtures';
import {
  authenticatedRequestContext,
  createPrivateProfile,
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
 * The backend must be running at VITE_API_BASE_URL (default http://127.0.0.1:8000).
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

