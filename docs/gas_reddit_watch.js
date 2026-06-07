/**
 * GitHub의 reddit_watch.csv를 Google Sheets에 누적합니다.
 * Apps Script의 주간 시간 기반 트리거에서 importRedditWatch를 실행하세요.
 * SHEET_ID는 같은 Apps Script 프로젝트의 gas_main.js에서 공유합니다.
 */
const SHEET_NAME = "reddit_watch";
const CSV_URL =
  "https://raw.githubusercontent.com/onepuhch/research/main/data/processed/reddit_watch.csv";

function importRedditWatch() {
  if (!SHEET_ID) {
    throw new Error("SHEET_ID를 Google 스프레드시트 ID로 설정하세요.");
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    const response = UrlFetchApp.fetch(CSV_URL, {
      muteHttpExceptions: true,
      followRedirects: true,
    });
    const statusCode = response.getResponseCode();
    if (statusCode !== 200) {
      throw new Error(`CSV 다운로드 실패: HTTP ${statusCode}`);
    }

    const csvText = response.getContentText("UTF-8").replace(/^\uFEFF/, "");
    const csvRows = Utilities.parseCsv(csvText);
    if (csvRows.length === 0 || csvRows[0].length === 0) {
      throw new Error("CSV에 헤더가 없습니다.");
    }

    const sourceHeader = csvRows[0].map((value) => String(value).trim());
    const dateIndex = sourceHeader.indexOf("날짜");
    const tickerIndex = sourceHeader.indexOf("종목후보");
    if (dateIndex === -1 || tickerIndex === -1) {
      throw new Error("CSV에 '날짜' 또는 '종목후보' 열이 없습니다.");
    }

    const spreadsheet = SpreadsheetApp.openById(SHEET_ID);
    const sheet =
      spreadsheet.getSheetByName(SHEET_NAME) || spreadsheet.insertSheet(SHEET_NAME);

    if (sheet.getLastRow() === 0) {
      sheet.getRange(1, 1, 1, sourceHeader.length).setValues([sourceHeader]);
      sheet.setFrozenRows(1);
    }

    const sheetHeader = sheet
      .getRange(1, 1, 1, sheet.getLastColumn())
      .getDisplayValues()[0]
      .map((value) => String(value).trim());
    if (sheetHeader.join("\u001F") !== sourceHeader.join("\u001F")) {
      throw new Error("시트 헤더가 GitHub CSV 헤더와 일치하지 않습니다.");
    }

    const existingKeys = new Set();
    if (sheet.getLastRow() > 1) {
      const existingRows = sheet
        .getRange(2, 1, sheet.getLastRow() - 1, sourceHeader.length)
        .getValues();
      existingRows.forEach((row) => {
        const key = makeKey(row[dateIndex], row[tickerIndex]);
        if (key) {
          existingKeys.add(key);
        }
      });
    }

    const rowsToAppend = [];
    let skippedCount = 0;

    csvRows.slice(1).forEach((sourceRow) => {
      const row = sourceHeader.map((_, index) => sourceRow[index] || "");
      if (row.every((value) => String(value).trim() === "")) {
        return;
      }

      const key = makeKey(row[dateIndex], row[tickerIndex]);
      if (!key || existingKeys.has(key)) {
        skippedCount += 1;
        return;
      }

      existingKeys.add(key);
      rowsToAppend.push(row);
    });

    if (rowsToAppend.length > 0) {
      sheet
        .getRange(sheet.getLastRow() + 1, 1, rowsToAppend.length, sourceHeader.length)
        .setValues(rowsToAppend);
    }

    console.log(`추가된 행 수: ${rowsToAppend.length}`);
    console.log(`skip된 행 수: ${skippedCount}`);
  } finally {
    lock.releaseLock();
  }
}

function makeKey(dateValue, tickerValue) {
  const dateText = normalizeDate(dateValue);
  const tickerText = String(tickerValue || "").trim().toUpperCase();
  if (!dateText || !tickerText) {
    return "";
  }
  return `${dateText}\u001F${tickerText}`;
}

function normalizeDate(value) {
  if (Object.prototype.toString.call(value) === "[object Date]" && !isNaN(value)) {
    return Utilities.formatDate(value, Session.getScriptTimeZone(), "yyyy-MM-dd");
  }
  return String(value || "").trim();
}
