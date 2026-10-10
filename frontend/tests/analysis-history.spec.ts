import {expect, test} from './fixtures';

async function createCandidate(page: import('@playwright/test').Page): Promise<void> {
  await page.getByRole('button', {name: 'New candidate profile', exact: true}).click();
  await page.getByLabel('Full name').fill('History Demo Candidate');
  await page.getByLabel('Email').fill('history.demo@example.com');
  await page.getByLabel('Location').first().fill('Remote');
  await page.getByLabel('Professional headline').fill('Junior Python Engineer');
  await page.getByLabel('Professional summary').fill('Python engineer building tested backend services.');
  await page.getByRole('button', {name: 'Add competency', exact: true}).click();
  await page.getByLabel('Skill').fill('Python');
  await page.getByRole('button', {name: 'Create profile', exact: true}).click();
  await expect(page.getByText('Profile created successfully.')).toBeVisible();
}

async function analyzeJob(
  page: import('@playwright/test').Page,
  company: string,
): Promise<void> {
  await page.getByLabel('Job title').fill('Junior Applied AI Engineer');
  await page.getByLabel('Company', {exact: true}).fill(company);
  await page.getByLabel('Location').last().fill('Remote');
  await page.getByLabel('Job description').fill(
    'Build reliable Python and FastAPI services, write automated tests, maintain PostgreSQL data, and document evidence-grounded AI workflows.',
  );
  await page.getByRole('button', {name: 'Analyze evidence'}).click();
  await expect(page.getByRole('heading', {name: 'Human review required'})).toBeVisible();
}

test('history cards expose distinct job context, score, date, state, and selection', async ({authenticatedPage: page}) => {
  await createCandidate(page);
  await analyzeJob(page, 'Atlas Example One');
  await analyzeJob(page, 'Atlas Example Two');

  const first = page.getByRole('button', {
    name: /Junior Applied AI Engineer at Atlas Example One, Remote, awaiting review, \d+\.\d% coverage, .+ 20\d{2}/,
  });
  const second = page.getByRole('button', {
    name: /Junior Applied AI Engineer at Atlas Example Two, Remote, awaiting review, \d+\.\d% coverage, .+ 20\d{2}/,
  });
  await expect(first).toBeVisible();
  await expect(second).toBeVisible();
  await expect(first).toHaveAttribute('aria-pressed', 'false');
  await expect(second).toHaveAttribute('aria-pressed', 'true');
  await expect(second).toContainText(/\d+\.\d%/);
  await expect(second).toContainText('Awaiting review');

  await first.focus();
  await expect(first).toBeFocused();
  await first.press('Enter');
  await expect(first).toHaveAttribute('aria-pressed', 'true');
  await expect(second).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByText('Atlas Example One').last()).toBeVisible();
});

test('legacy application without a career analysis stays in tracker with a clear message', async ({authenticatedPage: page}) => {
  await createCandidate(page);
  const created = await page.evaluate(async () => {
    const token = localStorage.getItem('careeros_access_token');
    const candidateId = localStorage.getItem('careeros_active_candidate_id');
    const response = await fetch('/api/v1/pipeline/manual', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        candidate_profile_id: candidateId,
        raw_title: 'Legacy Backend Engineer',
        company_name: 'Archive Example Company',
        source_platform: 'other',
        description_text: 'Build and test Python backend services, maintain API documentation, and support PostgreSQL application workflows for an internal engineering team.',
        document_format: 'pdf',
        create_application_record: true,
      }),
    });
    return {ok: response.ok, body: await response.text()};
  });
  expect(created.ok, created.body).toBe(true);

  await page.getByRole('button', {name: 'Applications'}).click();
  await expect(page.getByRole('cell', {name: 'Legacy Backend Engineer', exact: true})).toBeVisible();
  await page.getByRole('button', {
    name: 'View analysis for Legacy Backend Engineer at Archive Example Company',
  }).click();
  await expect(page.getByRole('alert')).toContainText(
    'The complete analysis is not available for this older application record.',
  );
  await expect(page.getByRole('button', {name: 'Applications', exact: true})).toHaveAttribute('aria-current', 'page');
});
