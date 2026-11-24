const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const test = require("node:test");
const vm = require("node:vm");

const template = readFileSync(require("node:path").join(__dirname, "templates/calendar.html"), "utf8");
const script = template.match(/<script>([\s\S]+?)<\/script>/)[1];

function loadCalendar(storage, { user = "1", minutesUntil = 10, blocked = false, holiday = false } = {}) {
    const now = new Date(2026, 10, 24, 12).getTime();
    const date = new Date(now + minutesUntil * 60000);
    const sound = {};
    const leadTime = {};
    let attempts = 0;
    let change;
    let tick;
    const elements = {
        reminderPreferences: {
            dataset: { userId: user },
            addEventListener: (name, handler) => { change = handler; },
        },
        enableNotifications: sound,
        reminderMinutes: leadTime,
        eventNotification: { play: async () => {
            attempts++;
            if (blocked) throw new Error("Playback blocked");
        } },
    };
    const row = {
        dataset: holiday ? { profile: "holidays" } : {
            eventId: "123",
            eventDate: "2026-11-24",
            eventTime: date.toTimeString().slice(0, 8),
        },
    };

    vm.runInNewContext(script, {
        document: {
            getElementById: id => elements[id],
            querySelectorAll: () => [row],
            addEventListener: () => {},
        },
        localStorage: {
            getItem: key => storage.get(key) ?? null,
            setItem: (key, value) => storage.set(key, value),
        },
        Date: class extends Date { static now() { return now; } },
        setInterval: handler => { tick = handler; },
    });

    return { sound, leadTime, change, tick, attempts: () => attempts };
}

test("preferences default to off and persist separately for each user", async () => {
    const storage = new Map();
    const page = loadCalendar(storage);
    assert.equal(page.sound.checked, false);
    assert.equal(page.leadTime.value, "60");
    assert.equal(page.attempts(), 0);

    page.sound.checked = true;
    page.leadTime.value = "5";
    page.change();
    const refreshed = loadCalendar(storage);
    assert.equal(refreshed.sound.checked, true);
    assert.equal(refreshed.leadTime.value, "5");
    assert.equal(refreshed.attempts(), 0);
    assert.equal(loadCalendar(storage, { user: "2" }).sound.checked, false);

    refreshed.sound.checked = false;
    refreshed.change();
    const disabled = loadCalendar(storage, { minutesUntil: 4 });
    assert.equal(disabled.sound.checked, false);
    assert.equal(disabled.attempts(), 0);
});

test("all lead times include their boundary and exclude later events", () => {
    for (const minutes of [5, 15, 30, 60]) {
        const storage = new Map([
            ["calendar-reminders:1:preferences", JSON.stringify({ enabled: true, minutes: String(minutes) })],
        ]);
        assert.equal(loadCalendar(storage, { minutesUntil: minutes + 1 }).attempts(), 0);
        assert.equal(loadCalendar(storage, { minutesUntil: minutes }).attempts(), 1);
    }
});

test("successful playback survives refresh and rescheduling makes the event eligible again", async () => {
    const storage = new Map();
    const page = loadCalendar(storage);
    page.sound.checked = true;
    page.change();
    await page.tick();
    assert.equal(page.attempts(), 1);

    const refreshed = loadCalendar(storage);
    await refreshed.tick();
    assert.equal(refreshed.attempts(), 0);
    assert.equal(loadCalendar(storage, { minutesUntil: 11 }).attempts(), 1);
});

test("blocked playback leaves the reminder eligible", async () => {
    const storage = new Map();
    const page = loadCalendar(storage, { blocked: true });
    page.sound.checked = true;
    page.change();
    await page.tick();
    assert.equal(page.attempts(), 1);
    assert.equal(loadCalendar(storage).attempts(), 1);
});

test("a holiday entry never plays sound with reminders enabled", async () => {
    const storage = new Map([
        ["calendar-reminders:1:preferences", JSON.stringify({ enabled: true, minutes: "60" })],
    ]);
    const page = loadCalendar(storage, { holiday: true });
    assert.equal(page.sound.checked, true);
    await page.tick();
    assert.equal(page.attempts(), 0);
    assert.equal(storage.has("calendar-reminders:1:history"), false);
});
