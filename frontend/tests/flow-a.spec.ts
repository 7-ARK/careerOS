import {expect, test} from './fixtures';

/**
 * Flow A browser acceptance: register -> login -> private candidate profile ->
 * manual job -> evidence analysis -> human approval -> PDF -> tracker.
 *
 * Runs entirely against the disposable local SQLite/Playwright harness with
 * deterministic local data only; no external network dependency.
 */

test('Flow A: register to resume download', async ({page, isolatedUser}) => {
  const applicationErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error' && !message.location().url.startsWith('chrome-extension://')) {
      applicationErrors.push(`console: ${message.text()}`);
    }
  });
  page.on('requestfailed', (request) => {
    if (request.url().startsWith('http://127.0.0.1:')) {
      applicationErrors.push(`request: ${request.method()} ${request.url()} ${request.failure()?.errorText ?? ''}`);
    }
  });
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
  await page.getByLabel('Location').first().fill('Remote');
  await page.getByLabel('Professional headline').fill('Backend Engineer');
  await page.getByLabel('Professional summary').fill('Backend engineer building reliable Python services.');

  await page.getByRole('button', {name: 'Add competency', exact: true}).click();
  await page.getByLabel('Skill').fill('Python');

  const createProfileButton = page.getByRole('button', {name: 'Create profile', exact: true});
  await expect(createProfileButton).toHaveCount(1);
  await createProfileButton.click();
  await expect(page.getByText('Profile created successfully.')).toBeVisible();
  await expect(page.getByLabel('Candidate profile', {exact: true})).toContainText('Ada Candidate');

  // Enter a manual job and run the deterministic evidence analysis.
  await page.getByRole('button', {name: 'Paste job manually'}).click();
  await page.getByLabel('Job title').fill('Backend Engineer');
  await page.getByLabel('Company', {exact: true}).fill('Platform Labs');
  await page.getByLabel('Location').fill('Remote');
  await page.getByLabel('Job description').fill(
    'Build reliable Python and FastAPI services, PostgreSQL integrations, automated tests, and production API workflows.',
  );
  await page.getByRole('button', {name: 'Analyze evidence'}).click();

  await expect(page.getByRole('heading', {name: 'Backend Engineer', exact: true})).toBeVisible();
  await expect(page.locator('#analysis-results').getByText('Platform Labs')).toBeVisible();
  await expect(page.getByRole('heading', {name: 'Requirement-to-evidence map'})).toBeVisible();
  await expect(page.getByRole('heading', {name: 'Human review required'})).toBeVisible();

  // Documents do not exist until the reviewer explicitly approves the grounded draft.
  await expect(page.getByRole('button', {name: /Download PDF/})).toHaveCount(0);
  await page.getByLabel('Review notes').fill('Reviewed the evidence citations and candidate facts.');
  await page.getByRole('button', {name: 'Approve and export'}).click();
  await expect(page.getByRole('heading', {name: 'Approved and saved'})).toBeVisible();
  await expect(page.getByRole('heading', {name: 'Analysis history'})).toBeVisible();

  // Download the generated resume and assert it is a non-empty PDF.
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', {name: 'Download PDF'}).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  const fileBuffer = Buffer.concat(chunks);
  expect(fileBuffer.length).toBeGreaterThan(0);
  expect(fileBuffer.subarray(0, 4).toString('latin1')).toBe('%PDF');

  // The approved flow saves a user-editable tracker record with evidence coverage.
  await page.getByRole('button', {name: 'Applications'}).click();
  await expect(page.getByRole('cell', {name: 'Backend Engineer', exact: true})).toBeVisible();
  await expect(page.getByRole('cell', {name: 'Platform Labs', exact: true})).toBeVisible();
  const status = page.getByLabel('Status for Backend Engineer at Platform Labs');
  await expect(status).toHaveValue('saved');
  await status.selectOption('applied');
  await expect(status).toHaveValue('applied');
  await status.selectOption('offer');
  await expect(status).toHaveValue('offer');
  await expect(page.locator('tbody tr')).toHaveCount(1);
  await page.getByRole('button', {name: 'View analysis for Backend Engineer at Platform Labs'}).click();
  await expect(page.getByRole('heading', {name: 'Backend Engineer', exact: true})).toBeVisible();
  await expect(page.getByRole('heading', {name: 'Requirement-to-evidence map'})).toBeVisible();
  await expect(page.getByText('Saved evidence analysis')).toBeVisible();
  await expect(page.getByRole('heading', {name: 'Approved and saved'})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Download DOCX'})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Download PDF'})).toBeVisible();
  await expect(page.locator('#analysis-results')).toBeFocused();

  // A browser reload still exposes the same persisted run through history.
  await page.reload();
  const persistedHistoryCard = page.getByRole('button', {
    name: /Backend Engineer at Platform Labs, Remote, completed, \d+\.\d% coverage, .+ 20\d{2}/,
  });
  await expect(persistedHistoryCard).toBeVisible();
  await persistedHistoryCard.click();
  await expect(page.getByRole('heading', {name: 'Requirement-to-evidence map'})).toBeVisible();
  await expect(page.getByRole('heading', {name: 'Approved and saved'})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Download DOCX'})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Download PDF'})).toBeVisible();
  for (const format of ['DOCX', 'PDF']) {
    const persistedDownload = page.waitForEvent('download');
    await page.getByRole('button', {name: `Download ${format}`}).click();
    const downloadedDocument = await persistedDownload;
    expect(downloadedDocument.suggestedFilename().toLowerCase()).toMatch(
      format === 'DOCX' ? /\.docx$/ : /\.pdf$/,
    );
  }

  // Opening the persisted run does not create a second run or tracker record.
  await page.getByRole('button', {name: 'Applications'}).click();
  await expect(page.locator('tbody tr')).toHaveCount(1);
  expect(applicationErrors).toEqual([]);
});
