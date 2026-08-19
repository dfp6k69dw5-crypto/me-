import { test, expect } from '@playwright/test';
import fs from 'node:fs';

const BASE = 'http://127.0.0.1:4173';
const RELAY = 'https://room-live-mirror.dfp6k69dw5.workers.dev/api/feed';
const RAW_FEED = 'https://raw.githubusercontent.com/maaronfanberg-lab/me-/main/room/feed.json';
const API_FEED = 'https://api.github.com/repos/maaronfanberg-lab/me-/contents/room/feed.json';
const RAW_HISTORY = 'https://raw.githubusercontent.com/maaronfanberg-lab/me-/main/room/conversation.json';

function iso(offsetSeconds = 0) {
  return new Date(Date.now() + offsetSeconds * 1000).toISOString();
}

function beatMessages(beat) {
  const speakers = ['sarah', 'mara', 'owen', 'jules'];
  return speakers.map((speaker, i) => ({
    id: `sim-beat-${beat}-${speaker}`,
    speaker,
    text: `SIM BEAT ${beat} ${speaker.toUpperCase()}`,
    at: iso(beat - 100 + i * 0.01),
    beat_id: `sim-beat-${beat}`,
  }));
}

function feed(beat, generatedOffsetSeconds = 0) {
  return {
    generated_at: iso(generatedOffsetSeconds),
    state: {
      version: 'room-viewer-simulator',
      cycle: beat,
      last_run: iso(generatedOffsetSeconds),
      beat_message_count: 4,
    },
    minds: {
      entities: {
        sarah: { name: 'Sarah' },
        mara: { name: 'Mara' },
        owen: { name: 'Owen' },
        jules: { name: 'Jules' },
      },
    },
    conversation: beatMessages(beat),
  };
}

function retainedHistory() {
  const list = [];
  for (let i = 1; i <= 996; i++) {
    list.push({
      id: `history-${i}`,
      speaker: ['sarah', 'mara', 'owen', 'jules'][i % 4],
      text: `retained history ${i}`,
      at: new Date(Date.now() - (1200 - i) * 1000).toISOString(),
      beat_id: `history-beat-${Math.floor(i / 4)}`,
    });
  }
  list.push(...beatMessages(100));
  return list;
}

function githubContentsPayload(value) {
  const text = JSON.stringify(value);
  return {
    type: 'file',
    encoding: 'base64',
    content: Buffer.from(text, 'utf8').toString('base64'),
  };
}

test('open Room viewer must advance across live beats when Pages is only a stale snapshot', async ({ page }) => {
  const errors = [];
  page.on('pageerror', e => errors.push(`pageerror: ${e.message}`));
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`console: ${msg.text()}`);
  });

  const history = retainedHistory();
  const staticPagesFeed = feed(100, -300);
  let apiBeat = 100;
  let apiCalls = 0;
  let relayCalls = 0;
  let rawCalls = 0;
  const observedApiBeats = [];

  await page.route(`${RELAY}*`, async route => {
    relayCalls++;
    await route.abort('failed');
  });

  await page.route(`${RAW_FEED}*`, async route => {
    rawCalls++;
    await route.abort('failed');
  });

  await page.route(`${API_FEED}*`, async route => {
    apiCalls++;
    apiBeat = Math.min(103, apiBeat + 1);
    observedApiBeats.push(apiBeat);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(githubContentsPayload(feed(apiBeat, 0))),
    });
  });

  await page.route(`${RAW_HISTORY}*`, async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(history),
    });
  });

  await page.route(`${BASE}/room/conversation.json*`, async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(history),
    });
  });

  await page.route(`${BASE}/room/feed.json*`, async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(staticPagesFeed),
    });
  });

  await page.goto(`${BASE}/room/?viewer-simulator=1`, { waitUntil: 'domcontentloaded' });

  await expect(page.locator('.msg')).toHaveCount(1000, { timeout: 12000 });
  await expect(page.locator('#status')).toContainText('beat 100', { timeout: 12000 });

  // Keep the same page open while the independently mocked GitHub API advances.
  // Current broken viewer never consults this source, reproducing the user's
  // "history + last Pages beat + rising age" screenshots.
  await page.waitForTimeout(8500);

  const status = await page.locator('#status').innerText();
  const meta = await page.locator('#meta').innerText();
  const bodyText = await page.locator('#chat').innerText();
  const beatMatch = status.match(/beat\s+(\d+)/i);
  const observedBeat = beatMatch ? Number(beatMatch[1]) : null;
  const messageCount = await page.locator('.msg').count();

  const requiredMarkers = [101, 102, 103].map(n => `SIM BEAT ${n}`);
  const markersPresent = requiredMarkers.map(marker => bodyText.includes(marker));
  const pass = observedBeat !== null && observedBeat >= 103 &&
    markersPresent.every(Boolean) && messageCount >= 1000 && errors.length === 0;

  const diagnostic = {
    checked_at: new Date().toISOString(),
    pass,
    expected_final_beat: 103,
    observed_final_beat: observedBeat,
    status,
    meta,
    retained_message_floor: 1000,
    observed_message_count: messageCount,
    markers_present: Object.fromEntries(requiredMarkers.map((m, i) => [m, markersPresent[i]])),
    relay_calls: relayCalls,
    raw_calls: rawCalls,
    api_calls: apiCalls,
    api_beats_served: observedApiBeats,
    errors,
    invariant: 'already-open viewer advances without reload and never treats static Pages snapshot as live',
  };

  fs.writeFileSync('room/viewer-simulator-diagnostic.json', JSON.stringify(diagnostic, null, 2) + '\n');

  expect(pass, JSON.stringify(diagnostic, null, 2)).toBeTruthy();
});
