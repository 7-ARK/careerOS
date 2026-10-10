import {expect, test} from './fixtures';
import {approveCurrentDraft, createPrivateProfile, downloadApprovedPdf} from './acceptance-helpers';

const fixtureUrl = 'http://127.0.0.1:8011/backend-engineer.html';
const fixtureMarkup = `<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"><title>Fixture Backend Engineer - Platform Labs</title></head>
  <body>
    <main>
      <h1 data-fixture-field="title">Fixture Backend Engineer</h1>
      <p data-fixture-field="company">Platform Labs</p>
      <p data-fixture-field="location">Remote</p>
      <div data-fixture-field="description">Build reliable Python APIs, FastAPI services, PostgreSQL integrations, and automation workflows.</div>
    </main>
  </body>
</html>`;
const editedTitle = 'Edited Fixture Backend Engineer';

test('a local URL import populates editable fields and generates a resume from the edited job', async ({authenticatedPage}) => {
  await authenticatedPage.route('**/*', async (route) => {
    const url = new URL(route.request().url());
    if (url.href === fixtureUrl) {
      await route.fulfill({
        body: fixtureMarkup,
        contentType: 'text/html; charset=utf-8',
        headers: {'access-control-allow-origin': 'http://127.0.0.1:3000'},
      });
      return;
    }
    const isAllowedLoopbackRequest = url.hostname === '127.0.0.1'
      && ['3000', '8000', '8011'].includes(url.port);
    if (!isAllowedLoopbackRequest) {
      await route.abort('blockedbyclient');
      return;
    }
    await route.continue();
  });

  const fixtureMarkupFromBrowser = await authenticatedPage.evaluate(async (url) => {
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Fixture request failed with status ${response.status}.`);
    }
    return response.text();
  }, fixtureUrl);
  const fixtureFields = {
    title: fixtureValue(fixtureMarkupFromBrowser, 'title'),
    company: fixtureValue(fixtureMarkupFromBrowser, 'company'),
    location: fixtureValue(fixtureMarkupFromBrowser, 'location'),
    description: fixtureValue(fixtureMarkupFromBrowser, 'description'),
  };

  await authenticatedPage.route('**/api/v1/pipeline/extract', async (route) => {
    const submittedRequest = JSON.parse(route.request().postData() ?? '{}') as Record<string, unknown>;
    expect(submittedRequest.job_url).toBe(fixtureUrl);
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        job_url: fixtureUrl,
        detected_platform: 'company_site',
        raw_title: fixtureFields.title,
        company_name: fixtureFields.company,
        location: fixtureFields.location,
        description_text: fixtureFields.description,
        extraction_confidence: '0.95',
        extraction_warnings: [],
        pipeline_ready: true,
      }),
    });
  });

  await createPrivateProfile(authenticatedPage, {
    fullName: 'URL Import Candidate',
    skills: ['Python'],
    projects: [
      {
        name: 'Automation Portfolio',
        description: 'Built reliable automation workflows.',
        technologies: 'Python, FastAPI',
      },
    ],
  });

  await authenticatedPage.getByRole('button', {name: 'Use job URL', exact: true}).click();
  await authenticatedPage.getByLabel('Job posting URL').fill(fixtureUrl);
  await authenticatedPage.getByRole('button', {name: 'Extract job', exact: true}).click();

  await expect(authenticatedPage.getByRole('heading', {name: 'Review extracted job details'})).toBeVisible();
  await expect(authenticatedPage.getByLabel('Job title')).toHaveValue(fixtureFields.title);
  await expect(authenticatedPage.getByRole('textbox', {name: 'Company', exact: true})).toHaveValue(fixtureFields.company);
  await expect(authenticatedPage.getByLabel('Job description')).toHaveValue(fixtureFields.description);

  await authenticatedPage.getByLabel('Job title').fill(editedTitle);
  await authenticatedPage.getByRole('button', {name: 'Analyze evidence', exact: true}).click();

  const results = authenticatedPage.locator('#analysis-results');
  await expect(results.getByRole('heading', {name: editedTitle, exact: true})).toBeVisible();
  await expect(results.getByRole('heading', {name: fixtureFields.title, exact: true})).toHaveCount(0);
  await expect(results.getByText('Python', {exact: true}).first()).toBeVisible();
  await expect(results.getByText('Automation Portfolio', {exact: true}).first()).toBeVisible();

  await approveCurrentDraft(authenticatedPage);
  await downloadApprovedPdf(authenticatedPage);
});

test('a malformed URL shows its extraction problem without persisting an application before manual completion', async ({authenticatedPage}) => {
  const malformedUrl = 'http://127.0.0.1:8011/malformed.html';
  const failureMessage = 'We could not read a complete job posting. Paste the job description manually.';

  await authenticatedPage.route('**/api/v1/pipeline/extract', async (route) => {
    const submittedRequest = JSON.parse(route.request().postData() ?? '{}') as Record<string, unknown>;
    expect(submittedRequest.job_url).toBe(malformedUrl);
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        job_url: malformedUrl,
        detected_platform: 'company_site',
        raw_title: null,
        company_name: null,
        location: null,
        description_text: '',
        extraction_confidence: '0',
        extraction_warnings: ['Use manual import fallback.'],
        outcome: 'extraction_failure',
        message: failureMessage,
        pipeline_ready: false,
      }),
    });
  });

  const profileId = await createPrivateProfile(authenticatedPage, {
    fullName: 'Malformed URL Candidate',
    skills: ['Python'],
    projects: [
      {
        name: 'Fallback Portfolio',
        description: 'Built reliable automation workflows.',
        technologies: 'Python, FastAPI',
      },
    ],
  });
  const applicationsBeforeFailure = await applicationRecordCount(authenticatedPage, profileId);

  await authenticatedPage.getByRole('button', {name: 'Use job URL', exact: true}).click();
  await authenticatedPage.getByLabel('Job posting URL').fill(malformedUrl);
  await authenticatedPage.getByRole('button', {name: 'Extract job', exact: true}).click();

  await expect(authenticatedPage.getByText(failureMessage, {exact: true})).toBeVisible();
  await expect(authenticatedPage.getByRole('heading', {name: 'We need the job text.'})).toBeVisible();
  await expect(authenticatedPage.getByText('Traceback', {exact: true})).not.toBeVisible();
  await expect(authenticatedPage.getByLabel('Job URL')).toHaveValue(malformedUrl);
  await expect(authenticatedPage.getByLabel('Job title')).toBeEditable();
  await expect(authenticatedPage.getByRole('textbox', {name: 'Company', exact: true})).toBeEditable();
  await expect(authenticatedPage.getByLabel('Job description')).toBeEditable();
  await expect(authenticatedPage.getByRole('button', {name: 'Analyze evidence', exact: true})).toBeEnabled();
  await expect.poll(() => applicationRecordCount(authenticatedPage, profileId)).toBe(applicationsBeforeFailure);

  await authenticatedPage.getByLabel('Job title').fill('Manual Recovery Engineer');
  await authenticatedPage.getByRole('textbox', {name: 'Company', exact: true}).fill('Fallback Labs');
  await authenticatedPage.getByLabel('Location').fill('Remote');
  await authenticatedPage.getByLabel('Job description').fill(
    'Build reliable Python APIs, FastAPI services, PostgreSQL integrations, and automation workflows.',
  );
  await authenticatedPage.getByRole('button', {name: 'Analyze evidence', exact: true}).click();

  const results = authenticatedPage.locator('#analysis-results');
  await expect(results.getByRole('heading', {name: 'Manual Recovery Engineer', exact: true})).toBeVisible();
  await expect(results.getByText('Fallback Labs', {exact: true})).toBeVisible();
  await expect(results.getByRole('heading', {name: 'Requirement-to-evidence map'})).toBeVisible();

  await approveCurrentDraft(authenticatedPage);
  await downloadApprovedPdf(authenticatedPage);
});

async function applicationRecordCount(page: import('@playwright/test').Page, profileId: string): Promise<number> {
  return page.evaluate(async (candidateProfileId) => {
    const token = localStorage.getItem('careeros_access_token');
    const response = await fetch(`http://127.0.0.1:8000/api/v1/applications/${candidateProfileId}`, {
      headers: token ? {Authorization: `Bearer ${token}`} : {},
    });
    if (!response.ok) {
      throw new Error(`Could not read application records: ${response.status}`);
    }
    const records = await response.json() as unknown[];
    return records.length;
  }, profileId);
}

function fixtureValue(markup: string, name: string): string {
  const match = new RegExp(`<[^>]+data-fixture-field="${name}"[^>]*>([\\s\\S]*?)</[^>]+>`).exec(markup);
  if (!match) {
    throw new Error(`Missing ${name} value in the local URL fixture.`);
  }
  return match[1].trim();
}
