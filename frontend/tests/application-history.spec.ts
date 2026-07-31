import {expect, test} from './fixtures';
import {createPrivateProfile, submitManualJob} from './acceptance-helpers';

const FIRST_TITLE = 'Historical Platform Engineer';
const FIRST_COMPANY = 'History Systems One';
const SECOND_TITLE = 'Historical Product Engineer';
const SECOND_COMPANY = 'History Systems Two';

test('shows generated resumes in deterministic history order and downloads an older resume', async ({authenticatedPage: page}) => {
  await createPrivateProfile(page, {
    fullName: 'History Browser Candidate',
    skills: ['TypeScript'],
  });

  await submitManualJob(page, {
    title: FIRST_TITLE,
    company: FIRST_COMPANY,
    location: 'Remote',
    description: 'Build reliable TypeScript systems and communicate clearly with product teams.',
  });
  await expect(page.getByRole('heading', {name: FIRST_TITLE, exact: true})).toBeVisible();

  await submitManualJob(page, {
    title: SECOND_TITLE,
    company: SECOND_COMPANY,
    location: 'Remote',
    description: 'Build trustworthy product workflows using React and TypeScript.',
  });
  await expect(page.getByRole('heading', {name: SECOND_TITLE, exact: true})).toBeVisible();

  const history = page.getByRole('region', {name: 'Resume history'});
  const rows = history.getByRole('listitem');
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toHaveAccessibleName(`${SECOND_TITLE} at ${SECOND_COMPANY}`);
  await expect(rows.nth(1)).toHaveAccessibleName(`${FIRST_TITLE} at ${FIRST_COMPANY}`);
  await expect(rows.nth(0)).toContainText(SECOND_TITLE);
  await expect(rows.nth(0)).toContainText(SECOND_COMPANY);
  await expect(rows.nth(1)).toContainText(FIRST_TITLE);
  await expect(rows.nth(1)).toContainText(FIRST_COMPANY);

  const downloadPromise = page.waitForEvent('download');
  await rows.nth(1).getByRole('button', {name: 'Download historical resume', exact: true}).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  if (!stream) {
    throw new Error('The historic resume download did not provide a readable stream.');
  }
  const chunks: Uint8Array[] = [];
  for await (const chunk of stream) {
    chunks.push(chunk as Uint8Array);
  }
  const artifact = Buffer.concat(chunks);
  expect(artifact.length).toBeGreaterThan(0);
  expect(artifact.subarray(0, 5).toString('ascii')).toBe('%PDF-');
});
