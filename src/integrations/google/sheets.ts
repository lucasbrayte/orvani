import { google } from "googleapis";

import { getSheetsEnv, type SheetsEnv } from "@/config/env";
import type { SheetReader } from "@/sync/types";

const READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly";

export class GoogleSheetsReader implements SheetReader {
  constructor(private readonly env: SheetsEnv = getSheetsEnv()) {}

  async read(): Promise<string[][]> {
    const auth = new google.auth.GoogleAuth({
      credentials: {
        client_email: this.env.serviceAccountEmail,
        private_key: this.env.privateKey.replace(/\\n/g, "\n"),
      },
      scopes: [READONLY_SCOPE],
    });
    const sheets = google.sheets({ version: "v4", auth });
    const response = await sheets.spreadsheets.values.get({
      spreadsheetId: this.env.spreadsheetId,
      range: this.env.range,
      majorDimension: "ROWS",
    });
    return (response.data.values ?? []).map((row) => row.map((cell) => String(cell)));
  }
}
