import {expect, test} from './fixtures';
import {createPrivateProfile} from './acceptance-helpers';

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

  await authenticatedPage.getByLabel('Job posting URL').fill(fixtureUrl);
  await authenticatedPage.getByRole('button', {name: 'Extract job', exact: true}).click();

  await expect(authenticatedPage.getByRole('heading', {name: 'Review extracted job details'})).toBeVisible();
  await expect(authenticatedPage.getByLabel('Job title')).toHaveValue(fixtureFields.title);
  await expect(authenticatedPage.getByRole('textbox', {name: 'Company', exact: true})).toHaveValue(fixtureFields.company);
  await expect(authenticatedPage.getByLabel('Job description')).toHaveValue(fixtureFields.description);

  await authenticatedPage.getByLabel('Job title').fill(editedTitle);
  await authenticatedPage.getByRole('button', {name: 'Generate resume', exact: true}).click();

  const resultPanel = authenticatedPage.getByRole('complementary');
  await expect(resultPanel.getByRole('heading', {name: editedTitle, exact: true})).toBeVisible();
  await expect(resultPanel.getByRole('heading', {name: fixtureFields.title, exact: true})).not.toBeVisible();
  await expect(resultPanel.getByText('Python', {exact: true})).toBeVisible();
  await expect(resultPanel.getByText('Automation Portfolio', {exact: true})).toBeVisible();

  const downloadPromise = authenticatedPage.waitForEvent('download');
  await authenticatedPage.getByRole('button', {name: 'Download resume', exact: true}).click();
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

function fixtureValue(markup: string, name: string): string {
  const match = new RegExp(`<[^>]+data-fixture-field="${name}"[^>]*>([\\s\\S]*?)</[^>]+>`).exec(markup);
  if (!match) {
    throw new Error(`Missing ${name} value in the local URL fixture.`);
  }
  return match[1].trim();
}
