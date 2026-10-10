import {expect, test} from './fixtures';
import {
  approveCurrentDraft,
  authenticatedRequestContext,
  createPrivateProfile,
  downloadApprovedPdf,
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
  await approveCurrentDraft(page);
  const documentId = await page.evaluate(async (roleTitle) => {
    const token = localStorage.getItem('careeros_access_token');
    const candidateId = localStorage.getItem('careeros_active_candidate_id');
    const response = await fetch(`http://127.0.0.1:8000/api/v1/career-analyses/candidate/${candidateId}`, {
      headers: token ? {Authorization: `Bearer ${token}`} : {},
    });
    if (!response.ok) {
      throw new Error(`Could not read career analyses: ${response.status}`);
    }
    const runs = await response.json() as Array<{
      resume_draft?: {target_role?: string} | null;
      generated_documents?: Array<{id: string; output_format: string}>;
    }>;
    const run = runs.find((item) => item.resume_draft?.target_role === roleTitle);
    const pdf = run?.generated_documents?.find((document) => document.output_format === 'pdf');
    if (!pdf) {
      throw new Error('The approved analysis did not include a PDF document.');
    }
    return pdf.id;
  }, title);
  return documentId;
}

async function expectPdfDownload(page: import('@playwright/test').Page): Promise<void> {
  await downloadApprovedPdf(page);
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
    await expect(page.getByLabel('Candidate profile', {exact: true})).toContainText(OWNER_PROFILE_NAME);
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
    await expectNoPrivateMarkers(page.getByLabel('Candidate profile', {exact: true}), privateMarkers);
    await expectNoPrivateMarkers(
      page.getByRole('heading', {name: OTHER_PROFILE_NAME, exact: true}),
      privateMarkers,
    );
    const results = page.locator('#analysis-results');
    await expectNoPrivateMarkers(results, privateMarkers);
    await expect(results).toContainText(OTHER_JOB_TITLE);
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
    const ownerRuns = await ownerApi.get(`/api/v1/career-analyses/candidate/${ownerCandidateId}`);
    expect(ownerRuns.ok()).toBeTruthy();
    const ownerRunId = (await ownerRuns.json() as Array<{id: string}>)[0]?.id;
    expect(ownerRunId).toBeTruthy();
    await expectSanitizedNotFound(
      await otherApi.get(`/api/v1/career-analyses/candidate/${ownerCandidateId}`),
      privateMarkers,
    );
    await expectSanitizedNotFound(
      await otherApi.get(`/api/v1/career-analyses/${ownerRunId}`),
      privateMarkers,
    );
    await expectSanitizedNotFound(
      await otherApi.post(`/api/v1/career-analyses/${ownerRunId}/review`, {
        data: {decision: 'reject'},
      }),
      privateMarkers,
    );

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
    await expect(page.getByLabel('Candidate profile', {exact: true})).toContainText(OWNER_PROFILE_NAME);
    await expect(page.getByRole('heading', {name: OWNER_PROFILE_NAME, exact: true})).toBeVisible();
    await expect(page.getByText('Attempted foreign mutation', {exact: true})).toHaveCount(0);
  } finally {
    await otherApi?.dispose();
    await ownerApi?.dispose();
  }
});
