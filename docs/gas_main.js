/**
 * GitHub의 주요 CSV를 Google Sheets 현황판에 동기화합니다.
 * Apps Script의 매일 시간 기반 트리거에서 runAll을 실행하세요.
 */
const SHEET_ID = "";
const GITHUB_RAW_BASE =
  "https://raw.githubusercontent.com/onepuhch/research/main/data/processed";
const SIGNAL_LOG_SHEET = "signal_log";
const REVIEW_LOG_SHEET = "investment_review_log";

function importSignalLog() {
  return syncCsvToSheet({
    csvUrl: `${GITHUB_RAW_BASE}/signal_log.csv`,
    sheetName: SIGNAL_LOG_SHEET,
    keyColumn: "signal_id",
    upsert: false,
  });
}

function importReviewLog() {
  return syncCsvToSheet({
    csvUrl: `${GITHUB_RAW_BASE}/investment_review_log.csv`,
    sheetName: REVIEW_LOG_SHEET,
    keyColumn: "idea_id",
    upsert: true,
  });
}

function runAll() {
  importSignalLog();
  importReviewLog();
}

function syncCsvToSheet(options) {
  if (!SHEET_ID) {
    throw new Error("SHEET_ID를 Google 스프레드시트 ID로 설정하세요.");
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    const csvRows = fetchCsvRows(options.csvUrl);
    const sourceHeader = csvRows[0].map((value) => String(value).trim());
    const keyIndex = sourceHeader.indexOf(options.keyColumn);
    if (keyIndex === -1) {
      throw new Error(`CSV에 '${options.keyColumn}' 열이 없습니다.`);
    }

    const spreadsheet = SpreadsheetApp.openById(SHEET_ID);
    const sheet =
      spreadsheet.getSheetByName(options.sheetName) ||
      spreadsheet.insertSheet(options.sheetName);
    ensureHeader(sheet, sourceHeader);

    const existingRowByKey = new Map();
    if (sheet.getLastRow() > 1) {
      const existingRows = sheet
        .getRange(2, 1, sheet.getLastRow() - 1, sourceHeader.length)
        .getDisplayValues();
      existingRows.forEach((row, index) => {
        const key = String(row[keyIndex] || "").trim();
        if (key) {
          existingRowByKey.set(key, index + 2);
        }
      });
    }

    const sourceRowByKey = new Map();
    let skippedCount = 0;
    csvRows.slice(1).forEach((sourceRow) => {
      const row = sourceHeader.map((_, index) => sourceRow[index] || "");
      if (row.every((value) => String(value).trim() === "")) {
        return;
      }
      const key = String(row[keyIndex] || "").trim();
      if (!key) {
        skippedCount += 1;
        return;
      }
      sourceRowByKey.set(key, row);
    });

    const rowsToAppend = [];
    let updatedCount = 0;
    sourceRowByKey.forEach((row, key) => {
      const existingRow = existingRowByKey.get(key);
      if (existingRow && options.upsert) {
        sheet.getRange(existingRow, 1, 1, sourceHeader.length).setValues([row]);
        updatedCount += 1;
      } else if (existingRow) {
        skippedCount += 1;
      } else {
        rowsToAppend.push(row);
      }
    });

    if (rowsToAppend.length > 0) {
      sheet
        .getRange(sheet.getLastRow() + 1, 1, rowsToAppend.length, sourceHeader.length)
        .setValues(rowsToAppend);
    }

    console.log(
      `${options.sheetName}: 추가 ${rowsToAppend.length}, 업데이트 ${updatedCount}, skip ${skippedCount}`
    );
    return {
      appended: rowsToAppend.length,
      updated: updatedCount,
      skipped: skippedCount,
    };
  } finally {
    lock.releaseLock();
  }
}

function fetchCsvRows(url) {
  const response = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true,
    followRedirects: true,
  });
  const statusCode = response.getResponseCode();
  if (statusCode !== 200) {
    throw new Error(`CSV 다운로드 실패: HTTP ${statusCode} (${url})`);
  }

  const csvText = response.getContentText("UTF-8").replace(/^\uFEFF/, "");
  const rows = Utilities.parseCsv(csvText);
  if (rows.length === 0 || rows[0].length === 0) {
    throw new Error(`CSV에 헤더가 없습니다: ${url}`);
  }
  return rows;
}

function ensureHeader(sheet, sourceHeader) {
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, sourceHeader.length).setValues([sourceHeader]);
    sheet.setFrozenRows(1);
    return;
  }

  const sheetHeader = sheet
    .getRange(1, 1, 1, sheet.getLastColumn())
    .getDisplayValues()[0]
    .map((value) => String(value).trim());
  if (sheetHeader.join("\u001F") !== sourceHeader.join("\u001F")) {
    throw new Error(`시트 헤더가 GitHub CSV 헤더와 일치하지 않습니다: ${sheet.getName()}`);
  }
}
