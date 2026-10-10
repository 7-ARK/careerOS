import {test as base, expect} from '@playwright/test';
import type {Page} from '@playwright/test';

import {register} from './acceptance-helpers';

export interface IsolatedUser {
  email: string;
  password: string;
  fullName: string;
}

interface TestFixtures {
  /** A uniquely-named test account that avoids collisions with other tests. */
  isolatedUser: IsolatedUser;
  /** A page that has already registered and logged in as `isolatedUser`. */
  authenticatedPage: Page;
}

/**
 * Generate a deterministic but unique email for the current test.
 * Combines worker index, a timestamp, and a random suffix so parallel workers
 * never collide even when tests retry.
 */
function generateUniqueEmail(workerIndex: number): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).slice(2, 8);
  return `browser-test-w${workerIndex}-${timestamp}-${random}@example.com`;
}

export const test = base.extend<TestFixtures>({
  isolatedUser: [
    async ({}, use) => {
      const user: IsolatedUser = {
        email: generateUniqueEmail(test.info().workerIndex),
        password: 'TestPassword123!',
        fullName: 'Browser Test User',
      };
      await use(user);
    },
    {scope: 'test'},
  ],

  authenticatedPage: async ({page, isolatedUser}, use) => {
    await page.goto('/');
    await register(page, isolatedUser);
    await use(page);
  },
});

export {expect};
