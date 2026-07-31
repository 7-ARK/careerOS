import {expect, test} from './fixtures';

/**
 * Flow A browser acceptance: register -> login -> private candidate profile ->
 * manual job -> tailored resume -> PDF download.
 *
 * Runs entirely against the disposable local SQLite/Playwright harness with
 * deterministic local data only; no external network dependency.
 */

test('Flow A: register to resume download', async ({page, isolatedUser}) => {
  await page.goto('/');

  // Register a fresh isolated user.
  await page.getByRole('button', {name: 'Register'}).click();
  await page.getByLabel('Full name').fill(isolatedUser.fullName);
  await page.getByLabel('Email').fill(isolatedUser.email);
  await page.getByLabel('Password').fill(isolatedUser.password);
  await page.getByRole('button', {name: 'Create account'}).click();
  await expect(page.getByRole('heading', {name: 'Tailor a resume for one job posting.'})).toBeVisible();

  // Log out and log back in to prove the login path works.
  await page.getByRole('button', {name: 'Logout'}).click();
  await expect(page.getByText(/Sign in to manage candidate profiles/)).toBeVisible();
  await page.getByLabel('Email').fill(isolatedUser.email);
  await page.getByLabel('Password').fill(isolatedUser.password);
  await page.locator('form').getByRole('button', {name: 'Login'}).click();
  await expect(page.getByRole('banner')).toContainText(isolatedUser.fullName);

  // Create a private candidate profile.
  const newCandidateProfileButton = page.getByRole('button', {name: 'New candidate profile', exact: true});
  await expect(newCandidateProfileButton).toHaveCount(1);
  await newCandidateProfileButton.click();
  await page.getByLabel('Full name').fill('Ada Candidate');
  await page.getByLabel('Email').fill('ada.candidate@example.com');
  await page.getByLabel('Phone number').fill('+1-555-0100');
  await page.getByLabel('Location').fill('Remote');
  await page.getByLabel('Professional headline').fill('Backend Engineer');
  await page.getByLabel('Professional summary').fill('Backend engineer building reliable Python services.');

  await page.getByRole('button', {name: 'Add competency', exact: true}).click();
  await page.getByLabel('Skill').fill('Python');

  const createProfileButton = page.getByRole('button', {name: 'Create profile', exact: true});
  await expect(createProfileButton).toHaveCount(1);
  await createProfileButton.click();
  await expect(page.getByText('Profile created successfully.')).toBeVisible();
  await expect(page.getByLabel('Candidate profile', {exact: true})).toContainText('Ada Candidate');

  // Enter a manual job and generate the tailored resume.
  await page.getByRole('button', {name: 'Paste job manually'}).click();
  await page.getByLabel('Job title').fill('Backend Engineer');
  await page.getByLabel('Company', {exact: true}).fill('Platform Labs');
  await page.getByLabel('Location').fill('Remote');
  await page.getByLabel('Job description').fill(
    'Build reliable Python and FastAPI services, PostgreSQL integrations, automated tests, and production API workflows.',
  );
  await page.getByRole('button', {name: 'Generate resume'}).click();

  await expect(page.getByRole('heading', {name: 'Backend Engineer'})).toBeVisible();
  await expect(page.getByText('Platform Labs')).toBeVisible();

  // Download the generated resume and assert it is a non-empty PDF.
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', {name: 'Download resume'}).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  const fileBuffer = Buffer.concat(chunks);
  expect(fileBuffer.length).toBeGreaterThan(0);
  expect(fileBuffer.subarray(0, 4).toString('latin1')).toBe('%PDF');
});
