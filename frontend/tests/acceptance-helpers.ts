import {expect, request} from '@playwright/test';
import type {APIRequestContext, Page} from '@playwright/test';

export interface BrowserUser {
  email: string;
  password: string;
  fullName: string;
}

export interface ManualJobDetails {
  title: string;
  company: string;
  description: string;
  location?: string;
  sourcePlatform?: string;
}

export interface PrivateProfileProject {
  name: string;
  description: string;
  technologies: string;
}

export interface PrivateProfileDetails {
  fullName: string;
  skills?: string[];
  projects?: PrivateProfileProject[];
}

/** Confirm that the unauthenticated authentication screen is displayed. */
export async function expectAuthenticationScreen(page: Page): Promise<void> {
  await expect(page.getByText(/Sign in to manage candidate profiles/)).toBeVisible();
}

/** Register a user through the browser and wait for the authenticated workspace. */
export async function register(page: Page, user: BrowserUser): Promise<void> {
  await page.getByRole('button', {name: 'Register'}).click();
  await page.getByLabel('Full name').fill(user.fullName);
  await page.getByLabel('Email').fill(user.email);
  await page.getByLabel('Password').fill(user.password);
  await page.getByRole('button', {name: 'Create account'}).click();
  await expect(page.getByRole('banner')).toContainText(user.fullName);
  await expect(page.getByRole('heading', {name: 'Tailor a resume for one job posting.'})).toBeVisible();
}

/** Log an existing user in through the browser and wait for their workspace. */
export async function login(page: Page, user: BrowserUser): Promise<void> {
  await page.getByLabel('Email').fill(user.email);
  await page.getByLabel('Password').fill(user.password);
  await page.locator('form').getByRole('button', {name: 'Login'}).click();
  await expect(page.getByRole('banner')).toContainText(user.fullName);
  await expect(page.getByRole('heading', {name: 'Tailor a resume for one job posting.'})).toBeVisible();
}

/** Create a profile visible only to the currently authenticated user. */
export async function createPrivateProfile(page: Page, profile: PrivateProfileDetails): Promise<string> {
  await page.getByRole('button', {name: 'New candidate profile', exact: true}).click();
  await page.getByLabel('Full name').fill(profile.fullName);

  const skillsSection = page.getByRole('heading', {name: 'Skills', exact: true}).locator('..');
  for (const skill of profile.skills ?? []) {
    await skillsSection.getByRole('button', {name: 'Add competency', exact: true}).click();
    await page.getByLabel('Skill').last().fill(skill);
  }

  const projectsSection = page.getByRole('heading', {name: 'Projects', exact: true}).locator('..');
  for (const project of profile.projects ?? []) {
    await projectsSection.getByRole('button', {name: 'Add projects', exact: true}).click();
    await page.getByLabel('Project name', {exact: true}).last().fill(project.name);
    await page.getByLabel('Description', {exact: true}).last().fill(project.description);
    await page.getByLabel('Technologies (comma separated)', {exact: true}).last().fill(project.technologies);
  }

  await page.getByLabel('Full name').locator('xpath=ancestor::form').getByRole(
    'button',
    {name: 'Create profile', exact: true},
  ).click();
  await expect(page.getByRole('heading', {name: profile.fullName, exact: true})).toBeVisible();
  const candidateProfile = page.getByLabel('Candidate profile', {exact: true});
  await expect(candidateProfile).toContainText(profile.fullName);
  return candidateProfile.inputValue();
}

/** Submit a manual job and wait for the human review gate. */
export async function submitManualJob(page: Page, job: ManualJobDetails): Promise<void> {
  const description = job.description.length >= 80
    ? job.description
    : `${job.description} The role also requires careful testing, readable code, and written updates for the team.`;
  await page.getByRole('button', {name: 'Paste job manually', exact: true}).click();
  await page.getByLabel('Job title').fill(job.title);
  await page.getByRole('textbox', {name: 'Company', exact: true}).fill(job.company);
  if (job.location) {
    await page.getByLabel('Location').fill(job.location);
  }
  await page.getByLabel('Source').selectOption(job.sourcePlatform ?? 'company');
  await page.getByLabel('Job description').fill(description);
  await page.getByRole('button', {name: 'Analyze evidence', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Human review required'})).toBeVisible();
}

/** Approve the draft that is waiting for review and wait for export. */
export async function approveCurrentDraft(page: Page): Promise<void> {
  await page.getByRole('button', {name: 'Approve and export', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Approved and saved'})).toBeVisible();
}

/** Download the approved PDF and return its bytes. */
export async function downloadApprovedPdf(page: Page): Promise<Buffer> {
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', {name: 'Download PDF', exact: true}).click();
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
  return artifact;
}

/**
 * Create an API request context carrying the access token established by the
 * current browser session. Callers must dispose the returned context.
 */
export async function authenticatedRequestContext(page: Page): Promise<APIRequestContext> {
  const token = await page.evaluate(() => localStorage.getItem('careeros_access_token'));
  if (!token) {
    throw new Error('The browser session did not contain an access token.');
  }
  const baseURL = (process.env.PLAYWRIGHT_BACKEND_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
  return request.newContext({
    baseURL,
    extraHTTPHeaders: {Authorization: `Bearer ${token}`},
  });
}

