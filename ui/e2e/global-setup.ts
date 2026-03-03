/**
 * Playwright global setup: prepares a clean database for E2E tests.
 *
 * Strategy:
 * 1. Back up the existing SQLite database file.
 * 2. Clear the `users` table so the registration endpoint reopens.
 *    (The app allows registration only when zero users exist.)
 * 3. Clear other user-generated data to avoid state leakage.
 *
 * The backup is restored by global-teardown.ts after the test run.
 */

import { execSync } from "node:child_process";
import { copyFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const DB_PATH =
  process.env.POLICY_FACTORY_DB_PATH ||
  resolve(process.env.HOME || "~", ".policy-factory", "store.db");

const BACKUP_PATH = `${DB_PATH}.e2e-backup`;

export default function globalSetup() {
  if (!existsSync(DB_PATH)) {
    // No database yet — nothing to do; the server will create one on demand.
    return;
  }

  // 1. Back up the original database
  copyFileSync(DB_PATH, BACKUP_PATH);

  // 2. Clear users (and other volatile data) so registration reopens.
  //    Uses Python's built-in sqlite3 module (always available) instead
  //    of the sqlite3 CLI which may not be installed.
  const tables = ["users", "events", "ideas", "idea_scores", "heartbeat_runs"];
  const deleteStatements = tables
    .map((t) => `c.execute("DELETE FROM ${t}")`)
    .join("; ");

  const pythonScript = `
import sqlite3, sys
conn = sqlite3.connect("${DB_PATH}")
c = conn.cursor()
${deleteStatements}
conn.commit()
conn.close()
`.trim();

  execSync(`python3 -c '${pythonScript}'`, { stdio: "pipe" });
}
