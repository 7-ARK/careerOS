import {expect, test} from './fixtures';
import {
  authenticatedRequestContext,
  createPrivateProfile,
  login,
  register,
  submitManualJob,
} from './acceptance-helpers';
import type {APIRequestContext, APIResponse, Locator} from '@playwright/test';

const USER_A = {
  email: 'privacy-owner@example.com',
  password: 'TestPassword123!',
  fullName: 'Privacy Owner User',
};
const USER_B = {
  email: 'privacy-other@example.com',
  password: 'TestPassword123!',
  fullName: 'Privacy Other User',
};
const OWNER_PROFILE_NAME = 'Owner Private Candidate';
const OWNER_JOB_TITLE = 'Owner Private Platform Engineer';
const OTHER_PROFILE_NAME = 'Other Private Candidate';
const OTHER_JOB_TITLE = 'Other Private Product Engineer';

async function generateResume(page: import('@playwright/test').Page, title: string): Promise<string> {
  await submitManualJob(page, {
    title,
    company: 'Private Career Company',
    location: 'Remote',
    description: 'Build private React and TypeScript resume workflows with clear communication.',
  });
  await expect(page.getByRole('heading', {name: title, exact: true})).toBeVisible();
  const documentId = await page
    .getByRole('complementary')
    .getByText('Document ID')
    .locator('..')
    .locator('span')
    .last()
    .textContent();
  if (!documentId) {
    throw new Error('The generated document identifier was not rendered.');
  }
  return documentId;
}

async function expectPdfDownload(page: import('@playwright/test').Page): Promise<void> {
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
}

async function expectNoPrivateMarkers(surface: Locator, markers: string[]): Promise<void> {
  for (const marker of markers) {
    await expect(surface).not.toContainText(marker);
  }
}

async function expectSanitizedNotFound(response: APIResponse, markers: string[]): Promise<void> {
  expect(response.status()).toBe(404);
  const body = await response.text();
  expect(body).toBe('{"error":{"code":"not_found","message":"Resource was not found."}}');
  for (const marker of markers) {
    expect(body).not.toContain(marker);
  }
}

test('two users keep profile, pipeline, and document resources private', async ({page}) => {
  let ownerApi: APIRequestContext | undefined;
  let otherApi: APIRequestContext | undefined;

  try {
    await page.goto('/');
    await register(page, USER_A);
    const ownerCandidateId = await createPrivateProfile(page, {
      fullName: OWNER_PROFILE_NAME,
      skills: ['TypeScript'],
      projects: [{
        name: 'Owner Resume Builder',
        description: 'Built a truthful private resume generation workflow.',
        technologies: 'TypeScript, React',
      }],
    });

    // The owner can list and open their candidate through valid same-user paths.
    await expect(page.getByLabel('Candidate profile')).toHaveText(OWNER_PROFILE_NAME);
    await expect(page.getByRole('heading', {name: OWNER_PROFILE_NAME, exact: true})).toBeVisible();
    ownerApi = await authenticatedRequestContext(page);
    const ownerList = await ownerApi.get('/api/v1/candidates');
    expect(ownerList.ok()).toBeTruthy();
    expect(await ownerList.json()).toEqual(expect.arrayContaining([
      expect.objectContaining({id: ownerCandidateId, full_name: OWNER_PROFILE_NAME}),
    ]));
    const ownerProfileBefore = await ownerApi.get(`/api/v1/candidates/${ownerCandidateId}`);
    expect(ownerProfileBefore.ok()).toBeTruthy();
    const ownerProfileBeforeJson = await ownerProfileBefore.json();
    expect(ownerProfileBeforeJson).toMatchObject({id: ownerCandidateId, full_name: OWNER_PROFILE_NAME});

    // The owner can act on the profile and download the generated document.
    const ownerDocumentId = await generateResume(page, OWNER_JOB_TITLE);
    await expectPdfDownload(page);

    await page.getByRole('button', {name: 'Logout'}).click();
    await register(page, USER_B);
    const otherCandidateId = await createPrivateProfile(page, {
      fullName: OTHER_PROFILE_NAME,
      skills: ['React'],
    });
    const otherDocumentId = await generateResume(page, OTHER_JOB_TITLE);

    const privateMarkers = [OWNER_PROFILE_NAME, OWNER_JOB_TITLE, ownerDocumentId];
    // These are component-level accessible surfaces, not a page-wide text check.
    await expectNoPrivateMarkers(page.getByLabel('Candidate profile'), privateMarkers);
    await expectNoPrivateMarkers(
      page.getByRole('heading', {name: OTHER_PROFILE_NAME, exact: true}),
      privateMarkers,
    );
    await expectNoPrivateMarkers(page.getByRole('complementary'), privateMarkers);
    await expect(page.getByRole('complementary')).toContainText(OTHER_JOB_TITLE);
    expect(otherCandidateId).not.toBe(ownerCandidateId);
    expect(otherDocumentId).not.toBe(ownerDocumentId);

    otherApi = await authenticatedRequestContext(page);
    const foreignCandidatePath = `/api/v1/candidates/${ownerCandidateId}`;
    const foreignDocumentPath = `/api/v1/documents/${ownerDocumentId}/download`;
    const foreignPipelinePayload = {
      candidate_profile_id: ownerCandidateId,
      raw_title: 'Rejected foreign pipeline request',
      company_name: 'Private Career Company',
      description_text: 'This action must not access another user candidate profile.',
      create_application_record: false,
    };

    // Every supported identifier substitution fails with the authoritative
    // sanitized not-found contract and never returns owner marker values.
    await expectSanitizedNotFound(await otherApi.get(foreignCandidatePath), privateMarkers);
    await expectSanitizedNotFound(
      await otherApi.patch(foreignCandidatePath, {data: {headline: 'Attempted foreign mutation'}}),
      privateMarkers,
    );
    await expectSanitizedNotFound(await otherApi.delete(foreignCandidatePath), privateMarkers);
    await expectSanitizedNotFound(
      await otherApi.post('/api/v1/pipeline/manual', {data: foreignPipelinePayload}),
      privateMarkers,
    );
    await expectSanitizedNotFound(await otherApi.get(foreignDocumentPath), privateMarkers);

    // Re-read the owner's resources after all rejected requests. The owner data
    // and the generated document remain available and unchanged.
    const ownerProfileAfter = await ownerApi.get(`/api/v1/candidates/${ownerCandidateId}`);
    expect(ownerProfileAfter.ok()).toBeTruthy();
    expect(await ownerProfileAfter.json()).toEqual(ownerProfileBeforeJson);
    const ownerListAfter = await ownerApi.get('/api/v1/candidates');
    expect(ownerListAfter.ok()).toBeTruthy();
    expect(await ownerListAfter.json()).toEqual(expect.arrayContaining([
      expect.objectContaining({id: ownerCandidateId, full_name: OWNER_PROFILE_NAME}),
    ]));
    const ownerDocumentAfter = await ownerApi.get(foreignDocumentPath);
    expect(ownerDocumentAfter.ok()).toBeTruthy();
    const ownerArtifact = await ownerDocumentAfter.body();
    expect(ownerArtifact.length).toBeGreaterThan(0);
    expect(ownerArtifact.subarray(0, 5).toString('ascii')).toBe('%PDF-');

    await page.getByRole('button', {name: 'Logout'}).click();
    await login(page, USER_A);
    await expect(page.getByLabel('Candidate profile')).toHaveText(OWNER_PROFILE_NAME);
    await expect(page.getByRole('heading', {name: OWNER_PROFILE_NAME, exact: true})).toBeVisible();
    await expect(page.getByText('Attempted foreign mutation', {exact: true})).toHaveCount(0);
  } finally {
    await otherApi?.dispose();
    await ownerApi?.dispose();
  }
});
