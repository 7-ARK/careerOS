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
  await page.getByRole('button', {name: 'Create profile', exact: true}).click();
  await page.getByLabel('Full name').fill(profile.fullName);

  const skillsSection = page.getByRole('heading', {name: 'Skills', exact: true}).locator('..');
  for (const skill of profile.skills ?? []) {
    await skillsSection.getByRole('button', {name: 'Add', exact: true}).click();
    await page.getByLabel('Skill').last().fill(skill);
  }

  const projectsSection = page.getByRole('heading', {name: 'Projects', exact: true}).locator('..');
  for (const project of profile.projects ?? []) {
    await projectsSection.getByRole('button', {name: 'Add', exact: true}).click();
    await page.getByLabel('Project name').last().fill(project.name);
    await page.getByLabel('Description').last().fill(project.description);
    await page.getByLabel('Technologies (comma separated)').last().fill(project.technologies);
  }

  await page.getByLabel('Full name').locator('xpath=ancestor::form').getByRole(
    'button',
    {name: 'Create profile', exact: true},
  ).click();
  await expect(page.getByRole('heading', {name: profile.fullName, exact: true})).toBeVisible();
  await expect(page.getByLabel('Candidate profile')).toHaveText(profile.fullName);
  return page.getByLabel('Candidate profile').inputValue();
}

/** Submit a manual job entry for the profile selected in the workspace. */
export async function submitManualJob(page: Page, job: ManualJobDetails): Promise<void> {
  await page.getByRole('button', {name: 'Paste job manually', exact: true}).click();
  await page.getByLabel('Job title').fill(job.title);
  await page.getByRole('textbox', {name: 'Company', exact: true}).fill(job.company);
  if (job.location) {
    await page.getByLabel('Location').fill(job.location);
  }
  await page.getByLabel('Source platform').selectOption(job.sourcePlatform ?? 'company');
  await page.getByLabel('Job description').fill(job.description);
  await page.getByRole('button', {name: 'Generate resume', exact: true}).click();
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

