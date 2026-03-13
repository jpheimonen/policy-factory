/**
 * Playwright global teardown: restores the original database after E2E tests.
 *
 * Copies the backup created by global-setup.ts back into place so the
 * developer's real data is not lost.
 */

import { copyFileSync, existsSync, unlinkSync } from "node:fs";
import { resolve } from "node:path";

const DB_PATH =
  process.env.POLICY_FACTORY_DB_PATH ||
  resolve(process.env.HOME || "~", ".policy-factory", "store.db");

const BACKUP_PATH = `${DB_PATH}.e2e-backup`;

export default function globalTeardown() {
  if (!existsSync(BACKUP_PATH)) {
    return;
  }

  // Restore the original database
  copyFileSync(BACKUP_PATH, DB_PATH);

  // Remove the backup file
  unlinkSync(BACKUP_PATH);
}
