// 画面から呼ばれる入口：画面を開く・下書き・公開

function getBootstrapData(sessionToken) {
  const session = requireSession_(sessionToken);
  // シートを1枚ずつ読むと、画面を開く8秒のうち7秒かかっていた（2026年10月に計測）。まとめて読む
  const lock = LockService.getScriptLock();
  lock.waitLock(SUBMIT_LOCK_WAIT_MS);
  let state, drafts, adminLog;
  try {
    const source = prefetchSheets_([CONTENT_SHEETS.publishedState, CONTENT_SHEETS.changeLog, CONTENT_SHEETS.drafts, CONTENT_SHEETS.adminLog]);
    const publishedInfo = readPublishedState_(source);
    state = readContentState_(source, publishedInfo);
    state.baseVersion = buildContentBaseVersion_(publishedInfo);
    drafts = readDrafts_(source);
    adminLog = readAdminLog_(source);
  } finally {
    lock.releaseLock();
  }
  return sanitizeForClient_({
    viewerEmail: session.email,
    viewerName: session.name || session.email,
    previewUrl: SITE_URL,
    state: state,
    drafts: drafts,
    adminLog: adminLog,
    maintenance: getDriveMaintenanceSummary_(state)
  });
}

// 初期読み込み・保存・公開は、ほかの保存・公開・アップロードが終わるのを30秒まで待つ
const SUBMIT_LOCK_WAIT_MS = 30000;

// 公開のあとの片付けはこの時間で打ち切り、残りは次の公開で続ける
const CLEANUP_BUDGET_MS = 20000;

function saveDraft(sessionToken, payload) {
  const session = requireSession_(sessionToken);
  const lock = LockService.getScriptLock();
  lock.waitLock(SUBMIT_LOCK_WAIT_MS);
  try {
    const normalized = normalizePayload_(payload, readContentState_(), { allowIncomplete: true });
    saveDraftRecord_(normalized, session.name || session.email, session.email);
    return { ok: true, message: '下書きを保存しました。' };
  } finally {
    lock.releaseLock();
  }
}

function loadDraft(sessionToken, draftId) {
  requireSession_(sessionToken);
  const drafts = readDrafts_();
  const match = drafts.find((item) => item.draftId === draftId);
  if (!match) throw new Error('指定した下書きが見つかりません。');
  return Object.assign(contentLists_(match.payload), { manualChangeNote: match.payload.manualChangeNote || '', baseVersion: match.payload.baseVersion || '' });
}

function previewSiteHistory(sessionToken, payload) {
  requireSession_(sessionToken);
  const currentState = readContentState_();
  const normalized = normalizePayload_(payload, currentState, { allowIncomplete: true });
  const publishedInfo = readPublishedState_();
  const publicSnapshot = buildPublicSnapshot_(normalized);
  const log = currentState.changeLog || [];
  const pending = buildChangeLogRows_(publishedInfo.payload || {}, publicSnapshot, normalized.manualChangeNote, log)
    .map((row) => Object.assign({ timestamp: isoNow_() }, row));
  const currentEntries = deriveSiteHistoryEntries_(log, buildChangeLogTitles_(publishedInfo.payload, publicSnapshot));
  const nextEntries = deriveSiteHistoryEntries_(pending.concat(log), buildChangeLogTitles_(publicSnapshot));
  return sanitizeForClient_({
    compared: buildSiteHistoryComparison_(currentEntries, nextEntries)
  });
}

function publishState(sessionToken, payload) {
  const session = requireSession_(sessionToken);
  // 段階ごとの開始からの秒数。_AdminLog の timings の列に書く（GAS の「実行数」の画面では、
  // ウェブアプリから呼ばれた処理のログを見られないため）
  const started = Date.now();
  const timings = [];
  const mark = (label) => timings.push(label + ' ' + ((Date.now() - started) / 1000).toFixed(1) + 's');
  const driveStats = {};
  let adminLogRow = 0;
  let cleanupReport = '';
  const lock = LockService.getScriptLock();
  lock.waitLock(SUBMIT_LOCK_WAIT_MS);
  mark('lock');
  try {
    const publishedInfo = readPublishedState_();
    requireContentBaseVersion_(payload, publishedInfo);
    const currentState = readContentState_(undefined, publishedInfo);
    const normalized = normalizePayload_(payload, currentState);
    mark('read');
    /* 内容が同じ公開や途中失敗でも、以前の画面・下書きを最新として使い回させない。
       シートの復旧では戻らない場所に記録し、画像を動かす前に確定する。 */
    PropertiesService.getScriptProperties().setProperty(CONTENT_EDIT_GENERATION_PROPERTY, Utilities.getUuid());
    const emptyExhibitionFolders = finalizeManagedFolders_(normalized, publishedInfo.payload, driveStats);
    mark('drive (' + Object.keys(driveStats).map((kind) => kind + ' ' + driveStats[kind].processed + '/' + driveStats[kind].total).join(', ') + ')');
    const currentPayloadJson = stableStringify_(buildPublicSnapshot_(normalized));
    const currentHash = sha256Hex_(currentPayloadJson);

    // 内容の置き場所なので先に書く。このあと更新履歴の書き込みに失敗しても、やり直しでは「変更なし」になる。
    // サイトは正しく、その1行が欠けるだけで済む
    let changeSummary = '内容を更新しました。';
    const publicSnapshot = buildPublicSnapshot_(normalized);
    if (publishedInfo.sha256 !== currentHash) {
      writePublishedState_(currentPayloadJson, currentHash);
      mark('sheets');
      const changeRows = buildChangeLogRows_(publishedInfo.payload, publicSnapshot, normalized.manualChangeNote, currentState.changeLog);
      if (changeRows.length) {
        appendChangeLog_(currentState.changeLog, session.name || session.email, changeRows);
        const titles = buildChangeLogTitles_(publicSnapshot);
        changeSummary = changeRows.map((row) => changeLogText_(row, titles)).join('\n');
      }
    }

    mark('history');
    emptyExhibitionFolders.forEach(trashFolderIfEmpty_);
    clearDrafts_();
    mark('drafts');
    cleanupUnreferencedDraftFolders_(normalized);
    mark('cleanup');
    adminLogRow = appendAdminLog_(session.name || session.email, session.email, 'published', buildAdminDiffSummary_(publishedInfo.payload, publicSnapshot, normalized.manualChangeNote));
    mark('adminlog');
    compactContentSheetGrids_();
    // サイトのビルドが _PublishedState と ChangeLog を読むので、書き込みを確定させてから起動する
    SpreadsheetApp.flush();
    mark('compact');
    const dispatchInfo = dispatchGithubWorkflow_();
    mark('github');
    // サイトの更新は始まったので、公開は成功。片付けで失敗しても公開のエラーにはしない
    try {
      const trash = getConfig_().CLEANUP_MODE === 'trash';
      cleanupReport = formatCleanupReport_(collectGarbage_(normalized, { trash, budgetMs: CLEANUP_BUDGET_MS, publishStartedAt: started }), trash);
    } catch (error) {
      cleanupReport = '片付けの途中でエラーが起きました（次の公開でやり直します）: ' + (error && error.message ? error.message : error);
    }
    mark('gc');
    return {
      ok: true,
      message: '公開を開始しました。',
      changeSummary: changeSummary,
      actionsUrl: dispatchInfo.actionsUrl
    };
  } finally {
    lock.releaseLock();
    console.log('publishState timings: ' + timings.join(', '));
    if (adminLogRow) {
      try {
        writeAdminLogCell_(adminLogRow, 'timings', timings.join(', '));
        if (cleanupReport) writeAdminLogCell_(adminLogRow, 'cleanup', cleanupReport);
      } catch (error) {
        console.warn('公開の所要時間や片付けの内容を記録できませんでした', error);
      }
    }
  }
}

function sanitizeForClient_(value) {
  if (value === undefined) return '';
  if (value === null) return null;
  if (Object.prototype.toString.call(value) === '[object Date]') {
    if (isNaN(value.getTime())) return '';
    return Utilities.formatDate(value, getConfig_().TIMEZONE || 'Asia/Tokyo', 'yyyy-MM-dd');
  }
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeForClient_(item));
  }
  if (typeof value === 'object') {
    const out = {};
    Object.keys(value).forEach((key) => {
      out[key] = sanitizeForClient_(value[key]);
    });
    return out;
  }
  if (typeof value === 'number' && !isFinite(value)) return '';
  return value;
}
