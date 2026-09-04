import path from "path";
import fs from "fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

// Locate financial_datasets.db
const candidatePaths = [
  path.resolve(process.cwd(), "../financial_datasets.db"),
  path.resolve(process.cwd(), "financial_datasets.db"),
  path.resolve(process.cwd(), "../../financial_datasets.db"),
];

let dbFile = candidatePaths[0]!;
for (const p of candidatePaths) {
  if (fs.existsSync(p)) {
    dbFile = p;
    break;
  }
}

export interface SqliteDbAdapter {
  queryGet: (sql: string, params?: any[]) => any;
  queryAll: (sql: string, params?: any[]) => any[];
  close: () => void;
}

export function openSqliteDb(filepath = dbFile): SqliteDbAdapter {
  const isBun = typeof (globalThis as any).Bun !== "undefined";

  if (isBun) {
    const { Database } = require("bun:sqlite");
    const db = new Database(filepath, { readonly: true });
    return {
      queryGet: (sql: string, params: any[] = []) => db.query(sql).get(...params),
      queryAll: (sql: string, params: any[] = []) => db.query(sql).all(...params),
      close: () => db.close(),
    };
  } else {
    // Node.js 22 built-in node:sqlite
    const { DatabaseSync } = require("node:sqlite");
    const db = new DatabaseSync(filepath, { readOnly: true });
    return {
      queryGet: (sql: string, params: any[] = []) => {
        const stmt = db.prepare(sql);
        return stmt.get(...params);
      },
      queryAll: (sql: string, params: any[] = []) => {
        const stmt = db.prepare(sql);
        return stmt.all(...params);
      },
      close: () => db.close(),
    };
  }
}
