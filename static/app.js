/* ═══════════════════════════════════════════════
   POCKETWISE  app.js  v2
   Multi-page · Chart.js · Dark mode · Animations
═══════════════════════════════════════════════ */

'use strict';

/* ── utils ── */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
const money = n => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n || 0);
const dateLabel = s => new Date(s + 'T00:00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
const today = () => new Date().toISOString().slice(0, 10);
const fmtMonth = () => new Intl.DateTimeFormat('en-IN', { month: 'long', year: 'numeric' }).format(new Date());

/* ── state ── */
let data = null;
let activeCharts = {};   // chartId → Chart instance
let toastTimer;
let contributeGoalId = null;

/* ── toast ── */
function toast(msg, type = 'success') {
  const t = $('#toast');
  t.textContent = msg;
  t.className = `toast ${type} show`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3000);
}

/* ── dark mode ── */
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('pw-theme', theme);
}
function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme');
  applyTheme(cur === 'dark' ? 'light' : 'dark');
  // re-render charts with new colours
  if (data) renderCharts();
}
// init from storage
applyTheme(localStorage.getItem('pw-theme') || 'light');

/* ── theme buttons ── */
document.addEventListener('DOMContentLoaded', () => {
  $('#theme-toggle')?.addEventListener('click', toggleTheme);
  $('#theme-toggle-top')?.addEventListener('click', toggleTheme);
});

/* ── sidebar collapse ── */
document.addEventListener('DOMContentLoaded', () => {
  const sb   = $('#sidebar');
  const tBtn = $('#sidebar-toggle');
  const mbBtn= $('#mobile-menu-btn');

  tBtn?.addEventListener('click', () => sb.classList.toggle('collapsed'));
  mbBtn?.addEventListener('click', () => {
    sb.classList.toggle('mobile-open');
    sb.classList.remove('collapsed');
  });
  // close sidebar on outside click (mobile)
  document.addEventListener('click', e => {
    if (window.innerWidth < 768 && sb.classList.contains('mobile-open')) {
      if (!sb.contains(e.target) && !mbBtn.contains(e.target)) {
        sb.classList.remove('mobile-open');
      }
    }
  });
});

/* ── API ── */
async function load() {
  const r = await fetch('/api/data');
  if (!r.ok) throw new Error('Could not reach the API server');
  data = await r.json();
  $('#profile-name').textContent = data.user.name;
  render();
}

async function post(url, obj) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj) });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || 'Something went wrong');
  data = j.data;
  render();
  toast('Saved successfully!');
}

/* ── routing ── */
function route() { return (location.hash.slice(1) || 'overview').split('/')[0]; }

function nav() {
  const r = route();
  $$('.nav-item').forEach(a => a.classList.toggle('active', a.dataset.route === r));
  const names = { overview: 'Overview', transactions: 'Transactions', budgets: 'Budgets', goals: 'Savings Goals', insights: 'Insights' };
  $('#crumb-current').textContent = names[r] || 'Overview';
}

/* ── render dispatcher ── */
function render() {
  nav();
  // destroy old charts
  Object.values(activeCharts).forEach(c => c.destroy());
  activeCharts = {};

  const r = route();
  const pages = { overview, transactions, budgets, goals, insights };
  const fn = pages[r] || overview;
  const content = $('#page-content');
  content.innerHTML = fn();
  content.style.animation = 'none';
  content.offsetHeight; // reflow
  content.style.animation = 'fadeIn .3s ease';

  bindPage();
  animateBars();
  renderCharts();
}

/* ══════════════════════════════════════════
   PAGE: OVERVIEW
══════════════════════════════════════════ */
function overview() {
  const spendItems = Object.entries(data.spend_by)
    .sort((a, b) => b[1] - a[1]).slice(0, 6)
    .map(([name, value]) => ({ name, value }));

  const topBudgets = data.budgets.slice(0, 4);

  return `
<div class="page-heading">
  <div class="page-heading-left">
    <div class="eyebrow">YOUR MONEY AT A GLANCE</div>
    <h1>Good day, ${esc(data.user.name.split(' ')[0])} 👋</h1>
    <p>${fmtMonth()} snapshot — here's how your finances look right now.</p>
  </div>
  <div class="heading-actions">
    <a class="btn btn-primary" href="#transactions">＋ Add transaction</a>
  </div>
</div>

<!-- STATS -->
<div class="stats-grid">
  ${statCard('MONTHLY INCOME',  data.income,  'c-teal',   '↗', `<span class="up">↑</span> Money in this month`)}
  ${statCard('TOTAL SPENDING',  data.expense, 'c-coral',  '↘', `<span class="down">${data.month_transactions.filter(x=>x.kind==='expense').length} expenses</span> recorded`)}
  ${statCard('NET SAVED',       data.saved,   'c-gold',   '◈', `<span class="up">${data.savings_rate}%</span> savings rate`)}
  ${statCard('HEALTH SCORE',    data.score + ' / 100', 'c-violet', '✧', scoreLabelHtml(data.score_label))}
</div>

<div class="overview-grid">
  <!-- Cash flow chart -->
  <div class="card">
    <div class="card-head">
      <div>
        <h2>Cash Flow Trend</h2>
        <div class="card-sub">Monthly income vs spending — 6 months</div>
      </div>
      <div class="chart-legend">
        <span><span class="legend-color" style="background:#0d9488"></span>Income</span>
        <span><span class="legend-color" style="background:#f43f5e"></span>Spending</span>
      </div>
    </div>
    <div class="chart-wrap"><canvas id="trend-chart" height="200"></canvas></div>
  </div>

  <!-- Donut -->
  <div class="card">
    <div class="card-head">
      <div>
        <h2>Where It Goes</h2>
        <div class="card-sub">Spending breakdown this month</div>
      </div>
      <a class="small-link" href="#budgets">View budgets →</a>
    </div>
    <div class="donut-panel">
      <div class="donut-wrap">
        ${donutSVG(spendItems)}
        <div class="donut-center">
          <b>${money(data.expense)}</b>
          <span>spent</span>
        </div>
      </div>
      <div class="donut-legend">
        ${spendItems.map((x, i) => `
          <div class="legend-row">
            <span class="legend-dot" style="background:${DONUT_COLORS[i % DONUT_COLORS.length]}"></span>
            <span>${esc(x.name)}</span>
            <b>${Math.round(x.value / (data.expense || 1) * 100)}%</b>
          </div>`).join('')}
      </div>
    </div>
  </div>
</div>

<div class="lower-grid">
  <!-- Recent transactions -->
  <div class="card">
    <div class="card-head">
      <div>
        <h2>Recent Transactions</h2>
        <div class="card-sub">Your latest money movement</div>
      </div>
      <a class="small-link" href="#transactions">See all →</a>
    </div>
    <div class="table-scroll">
      ${txTable(data.transactions.slice(0, 6))}
    </div>
  </div>

  <!-- Budget pulse -->
  <div class="card">
    <div class="card-head">
      <div>
        <h2>Budget Pulse</h2>
        <div class="card-sub">How this month is tracking</div>
      </div>
      <a class="small-link" href="#budgets">Manage →</a>
    </div>
    <div class="budget-list">
      ${topBudgets.map(b => budgetItem(b)).join('')}
    </div>
    ${data.budgets.some(b => b.percent > 100)
      ? `<div class="trend-banner"><div class="tb-icon" style="background:var(--coral-lt);color:var(--coral)">⚠</div><div><strong style="font-size:12px">A budget needs attention</strong><p style="font-size:11px;color:var(--ink3);margin-top:2px">One or more categories have crossed their limits.</p></div></div>`
      : `<div class="trend-banner"><div class="tb-icon" style="background:var(--green-lt);color:var(--green)">✓</div><div><strong style="font-size:12px">All budgets on track</strong><p style="font-size:11px;color:var(--ink3);margin-top:2px">Great job staying within your limits this month.</p></div></div>`}
  </div>
</div>`;
}

/* ══════════════════════════════════════════
   PAGE: TRANSACTIONS
══════════════════════════════════════════ */
function transactions() {
  const cats = [...new Set(data.transactions.map(x => x.category))].sort();
  return `
<div class="page-heading">
  <div class="page-heading-left">
    <div class="eyebrow">MONEY MOVEMENT</div>
    <h1>Transactions</h1>
    <p>Every rupee, in one clear place. Add income and expenses as they happen.</p>
  </div>
  <div class="heading-actions">
    <a class="btn" href="/api/export.csv">↓ Export CSV</a>
  </div>
</div>

<div class="two-col">
  <!-- Left: list -->
  <div class="card">
    <div class="card-head">
      <div>
        <h2>Transaction History</h2>
        <div class="card-sub">${data.transactions.length} records</div>
      </div>
      <span class="chip">${data.month_transactions.length} this month</span>
    </div>
    <div class="filter-row">
      <input id="tx-search" type="search" placeholder="Search…">
      <select id="tx-kind">
        <option value="all">All types</option>
        <option value="income">Income</option>
        <option value="expense">Expense</option>
      </select>
      <select id="tx-cat">
        <option value="all">All categories</option>
        ${cats.map(c => `<option>${esc(c)}</option>`).join('')}
      </select>
    </div>
    <div class="table-scroll" style="max-height:520px;overflow-y:auto" id="tx-list">
      ${txTable(data.transactions)}
    </div>
  </div>

  <!-- Right: form -->
  <div class="card form-card">
    <h2>Add a Transaction</h2>
    <form id="tx-form">
      <div class="field">
        <label>Transaction type</label>
        <select id="tx-type" name="kind">
          <option value="expense">Expense</option>
          <option value="income">Income</option>
        </select>
      </div>
      <div class="field">
        <label>Amount (₹)</label>
        <input id="tx-amount" name="amount" type="number" min="1" step="1" placeholder="e.g. 850" required>
      </div>
      <div class="field">
        <label>Category</label>
        <select id="tx-category" name="category" required></select>
      </div>
      <div class="field">
        <label>Description</label>
        <input id="tx-desc" name="description" maxlength="80" placeholder="e.g. Lunch with friends" required>
      </div>
      <div class="field">
        <label>Date</label>
        <input id="tx-date" name="date" type="date" value="${today()}" required>
      </div>
      <button class="btn btn-primary" style="width:100%;margin-top:4px">Save Transaction</button>
    </form>
    <p class="form-note">Entries are saved to the local SQLite database and update your dashboard instantly.</p>
  </div>
</div>`;
}

/* ══════════════════════════════════════════
   PAGE: BUDGETS
══════════════════════════════════════════ */
function budgets() {
  const on = data.budgets.filter(b => b.percent <= 100).length;
  return `
<div class="page-heading">
  <div class="page-heading-left">
    <div class="eyebrow">SPEND WITH INTENTION</div>
    <h1>Budgets</h1>
    <p>Set a gentle guardrail for the categories that matter most.</p>
  </div>
  <div class="heading-actions">
    <button class="btn btn-primary" id="focus-budget">＋ Set a budget</button>
  </div>
</div>

<div class="two-col">
  <!-- Budget list -->
  <div class="card">
    <div class="card-head">
      <div>
        <h2>${fmtMonth()} Plan</h2>
        <div class="card-sub">Category spend against monthly limits</div>
      </div>
      <span class="chip ${on < data.budgets.length ? 'warn' : ''}">${on} of ${data.budgets.length} on track</span>
    </div>
    <div class="budget-list">
      ${data.budgets.map(b => budgetItem(b, true)).join('')}
    </div>
    <div class="chart-wrap" style="padding-top:16px">
      <canvas id="budget-chart" height="260"></canvas>
    </div>
  </div>

  <!-- Form + summary -->
  <div>
    <div class="card form-card" id="budget-form-panel">
      <h2>Set Monthly Limit</h2>
      <form id="budget-form">
        <div class="field">
          <label>Expense category</label>
          <select name="category">
            ${data.budgets.map(b => `<option>${esc(b.category)}</option>`).join('')}
          </select>
        </div>
        <div class="field">
          <label>Monthly limit (₹)</label>
          <input name="amount" type="number" min="1" step="100" placeholder="e.g. 5000" required>
        </div>
        <button class="btn btn-primary" style="width:100%">Save Budget</button>
      </form>
      <p class="form-note">Saving a category again updates its current monthly limit.</p>
    </div>

    <div class="card card-pad" style="margin-top:14px">
      <h2 style="font-family:'Sora',sans-serif;font-size:14px;font-weight:700;margin-bottom:12px">Month Summary</h2>
      <div style="display:grid;gap:10px">
        <div style="display:flex;justify-content:space-between;font-size:12px"><span style="color:var(--ink3)">Total planned</span><b>${money(data.budgets.reduce((a, b) => a + b.limit_amount, 0))}</b></div>
        <div style="display:flex;justify-content:space-between;font-size:12px"><span style="color:var(--ink3)">Total spent</span><b style="color:var(--coral)">${money(data.expense)}</b></div>
        <div class="divider"></div>
        <div style="display:flex;justify-content:space-between;font-size:12px"><span style="color:var(--ink3)">Remaining</span><b style="color:var(--green)">${money(Math.max(0, data.budgets.reduce((a, b) => a + b.limit_amount, 0) - data.expense))}</b></div>
      </div>
    </div>
  </div>
</div>`;
}

/* ══════════════════════════════════════════
   PAGE: GOALS
══════════════════════════════════════════ */
function goals() {
  const totalSaved  = data.goals.reduce((a, g) => a + g.saved_amount, 0);
  const totalTarget = data.goals.reduce((a, g) => a + g.target_amount, 0);
  return `
<div class="page-heading">
  <div class="page-heading-left">
    <div class="eyebrow">PLANS WITH PURPOSE</div>
    <h1>Savings Goals</h1>
    <p>Give your future plans a name, a number, and a little momentum.</p>
  </div>
  <div class="heading-actions">
    <button class="btn btn-primary" id="focus-goal">＋ New goal</button>
  </div>
</div>

<div class="two-col">
  <!-- Goal list -->
  <div>
    <div class="card card-pad" style="margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <div>
          <h2 style="font-family:'Sora',sans-serif;font-size:14px;font-weight:700">Your Goals</h2>
          <div class="card-sub">${data.goals.length} active goals</div>
        </div>
        <span class="chip">${money(totalSaved)} saved of ${money(totalTarget)}</span>
      </div>
      <div class="chart-wrap"><canvas id="goals-chart" height="200"></canvas></div>
    </div>

    ${data.goals.length
      ? data.goals.map(g => goalCard(g)).join('')
      : `<div class="card"><div class="empty">No goals yet. Start with a small milestone that matters to you.</div></div>`}
  </div>

  <!-- Form -->
  <div>
    <div class="card form-card" id="goal-form-panel">
      <h2>Start a New Goal</h2>
      <form id="goal-form">
        <div class="field">
          <label>Goal name</label>
          <input name="name" maxlength="50" placeholder="e.g. Emergency fund" required>
        </div>
        <div class="field">
          <label>Target amount (₹)</label>
          <input name="target" type="number" min="1" step="500" placeholder="e.g. 50000" required>
        </div>
        <div class="field">
          <label>Target date</label>
          <input name="date" type="date" min="${today()}" value="${new Date(Date.now() + 180 * 86400000).toISOString().slice(0, 10)}" required>
        </div>
        <button class="btn btn-primary" style="width:100%">Create Goal</button>
      </form>
      <p class="form-note">Goals are personal milestones. Set a pace that feels comfortable.</p>
    </div>

    <div class="card card-pad" style="margin-top:14px">
      <h2 style="font-family:'Sora',sans-serif;font-size:14px;font-weight:700;margin-bottom:8px">Every bit counts</h2>
      <p style="font-size:11px;color:var(--ink3);line-height:1.6">Across your active goals, you've saved <strong style="color:var(--teal)">${money(totalSaved)}</strong> toward <strong style="color:var(--teal)">${money(totalTarget)}</strong> in future plans.</p>
    </div>
  </div>
</div>`;
}

/* ══════════════════════════════════════════
   PAGE: INSIGHTS
══════════════════════════════════════════ */
function insights() {
  const notes = makeInsights();
  return `
<div class="page-heading">
  <div class="page-heading-left">
    <div class="eyebrow">A CLEARER NEXT STEP</div>
    <h1>Insights & Reports</h1>
    <p>Simple rules turn your own activity into useful prompts.</p>
  </div>
  <div class="heading-actions">
    <a class="btn" href="/api/export.csv">↓ Download CSV</a>
    <span class="chip purple">${notes.length} insights</span>
  </div>
</div>

<div class="two-col">
  <div>
    <!-- Insights -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-head">
        <div>
          <h2>Your Monthly Coach Notes</h2>
          <div class="card-sub">Each note comes from a visible rule applied to your records</div>
        </div>
      </div>
      <div class="insight-cards">
        ${notes.map(n => `
          <div class="insight-card">
            <div class="insight-icon ${n.kind}">${n.icon}</div>
            <div>
              <h3>${n.title}</h3>
              <p>${n.body}</p>
            </div>
          </div>`).join('')}
      </div>
    </div>

    <!-- Trend chart -->
    <div class="card">
      <div class="card-head">
        <div>
          <h2>Income & Spending Trend</h2>
          <div class="card-sub">Monthly recorded cash flow</div>
        </div>
        <div class="chart-legend">
          <span><span class="legend-color" style="background:#0d9488"></span>Income</span>
          <span><span class="legend-color" style="background:#f43f5e"></span>Spending</span>
        </div>
      </div>
      <div class="chart-wrap"><canvas id="insights-trend" height="200"></canvas></div>
    </div>
  </div>

  <div>
    <!-- Summary tiles -->
    <div class="card" style="margin-bottom:14px">
      <div class="card-head">
        <div>
          <h2>${fmtMonth()} Summary</h2>
          <div class="card-sub">Snapshot of this month's activity</div>
        </div>
      </div>
      <div class="report-grid">
        <div class="report-tile"><span>Income</span><b class="up">${money(data.income)}</b></div>
        <div class="report-tile"><span>Spent</span><b>${money(data.expense)}</b></div>
        <div class="report-tile"><span>Net saved</span><b class="up">${money(data.saved)}</b></div>
        <div class="report-tile"><span>Savings rate</span><b>${data.savings_rate}%</b></div>
        <div class="report-tile"><span>Expense ratio</span><b>${data.expense_ratio}%</b></div>
        <div class="report-tile"><span>Health score</span><b>${data.score}/100</b></div>
      </div>
      <div style="padding:0 20px 16px;margin-top:8px">
        <a class="btn btn-primary" style="width:100%;justify-content:center;text-decoration:none" href="/api/export.csv">Export CSV Report</a>
      </div>
    </div>

    <!-- Health score -->
    ${healthPanel()}

    <!-- Score guide -->
    <div class="card card-pad" style="margin-top:14px">
      <h2 style="font-family:'Sora',sans-serif;font-size:14px;font-weight:700;margin-bottom:12px">How the score works</h2>
      ${[['Strong · 80–100', 'Good momentum across all tracked indicators.', 'var(--green)'],
         ['Building · 60–79', 'Some healthy habits are taking shape.', 'var(--gold)'],
         ['Needs attention · below 60', 'A prompt to review your plan.', 'var(--coral)']].map(([t, d, c]) => `
        <div style="border-left:3px solid ${c};padding:4px 0 4px 12px;margin-bottom:10px">
          <strong style="font-size:12px">${t}</strong>
          <p style="font-size:11px;color:var(--ink3);margin-top:2px">${d}</p>
        </div>`).join('')}
    </div>
  </div>
</div>`;
}

/* ══════════════════════════════════════════
   HELPERS — HTML snippets
══════════════════════════════════════════ */
const DONUT_COLORS = ['#0d9488','#f59e0b','#3b82f6','#f43f5e','#8b5cf6','#10b981','#ec4899','#f97316'];

function statCard(label, value, color, icon, foot) {
  const display = typeof value === 'number' ? money(value) : value;
  return `
<div class="stat-card ${color}">
  <div class="stat-label">${label}</div>
  <div class="stat-icon-wrap ${color}">${icon}</div>
  <div class="stat-value count-num" data-val="${typeof value === 'number' ? value : ''}">${display}</div>
  <div class="stat-foot">${foot}</div>
</div>`;
}

function scoreLabelHtml(label) {
  const cls = label === 'Strong' ? 'strong' : label === 'Building' ? 'building' : 'weak';
  return `<span class="score-label ${cls}">${label}</span>`;
}

function txTable(rows) {
  if (!rows.length) return `<div class="empty">No transactions match this view.</div>`;
  return `<table class="data-table">
    <thead><tr><th>Date</th><th>Category</th><th>Description</th><th>Type</th><th style="text-align:right">Amount</th></tr></thead>
    <tbody>
    ${rows.map(x => `
      <tr>
        <td>${dateLabel(x.date)}</td>
        <td><div class="cat-cell"><span class="cat-dot" style="background:${x.color}"></span>${esc(x.category)}</div></td>
        <td class="tx-desc">${esc(x.description)}</td>
        <td><span class="kind-chip ${x.kind}">${x.kind === 'income' ? 'Income' : 'Expense'}</span></td>
        <td class="${x.kind === 'income' ? 'amount-in' : 'amount-out'}" style="text-align:right">${x.kind === 'income' ? '+' : '−'}${money(x.amount)}</td>
      </tr>`).join('')}
    </tbody>
  </table>`;
}

function budgetItem(b, full = false) {
  const cls = b.percent > 100 ? 'over' : b.percent >= 80 ? 'warn' : 'ok';
  return `
<div class="budget-item">
  <div class="budget-item-head">
    <b>${esc(b.category)}</b>
    <span class="budget-amt">${money(b.actual)} <span style="color:var(--ink4)">/ ${money(b.limit_amount)}</span></span>
  </div>
  <div class="budget-track">
    <div class="budget-fill ${cls}" data-pct="${Math.min(100, b.percent)}" style="width:0"></div>
  </div>
  <div class="budget-foot">
    <span>${b.percent > 100 ? `<span style="color:var(--coral)">Over by ${money(b.actual - b.limit_amount)}</span>` : `${b.percent}% used`}</span>
    <span>${b.percent > 100 ? '' : money(Math.max(0, b.limit_amount - b.actual)) + ' left'}</span>
  </div>
</div>`;
}

function goalCard(g) {
  return `
<div class="goal-card">
  <div class="goal-top">
    <div>
      <h3>${esc(g.name)}</h3>
      <div class="goal-date">Target · ${dateLabel(g.target_date)}</div>
    </div>
    <div class="goal-pct">${g.percent}%</div>
  </div>
  <div class="goal-vals">
    <span>Saved <b>${money(g.saved_amount)}</b></span>
    <span>Goal <b>${money(g.target_amount)}</b></span>
    <span>Remaining <b>${money(Math.max(0, g.target_amount - g.saved_amount))}</b></span>
  </div>
  <div class="goal-track"><div class="goal-bar" data-pct="${g.percent}" style="width:0"></div></div>
  <div class="goal-actions">
    <span>${money(Math.max(0, g.target_amount - g.saved_amount))} to go</span>
    <button class="btn btn-primary contribute-btn" data-id="${g.id}" data-name="${esc(g.name)}">＋ Add savings</button>
  </div>
</div>`;
}

function donutSVG(items) {
  const total = items.reduce((a, x) => a + x.value, 0) || 1;
  const C = 2 * Math.PI * 42, r = 42;
  let offset = 0;
  const circles = items.map((x, i) => {
    const len = x.value / total * C;
    const s = `<circle cx="50" cy="50" r="${r}" fill="none" stroke="${DONUT_COLORS[i % DONUT_COLORS.length]}" stroke-width="12" stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-offset}" />`;
    offset += len;
    return s;
  }).join('');
  return `<svg viewBox="0 0 100 100" width="130" height="130"><circle cx="50" cy="50" r="${r}" fill="none" stroke="var(--border)" stroke-width="12"/>${circles}</svg>`;
}

function healthPanel() {
  const s  = data.score;
  const p1 = Math.min(100, data.savings_rate / 20 * 100);
  const p2 = Math.max(0, 100 - data.expense_ratio);
  const spent = data.budgets.reduce((a, b) => a + b.actual, 0);
  const plan  = data.budgets.reduce((a, b) => a + b.limit_amount, 0);
  const p3 = Math.max(0, 100 - (spent / Math.max(1, plan)) * 100);
  const C  = 2 * Math.PI * 44;

  return `
<div class="card">
  <div class="card-head">
    <div>
      <h2>Financial Health</h2>
      <div class="card-sub">A simple read on your monthly habits</div>
    </div>
    ${scoreLabelHtml(data.score_label)}
  </div>
  <div class="health-ring-wrap">
    <div class="ring-svg-wrap">
      <svg viewBox="0 0 100 100" width="100" height="100">
        <circle cx="50" cy="50" r="44" fill="none" stroke="var(--border)" stroke-width="8"/>
        <circle cx="50" cy="50" r="44" fill="none" stroke="var(--teal)" stroke-width="8"
          stroke-linecap="round"
          stroke-dasharray="${C * s / 100} ${C}"
          stroke-dashoffset="0"
          style="transition:stroke-dasharray 1.2s cubic-bezier(.4,0,.2,1)"/>
      </svg>
      <div class="ring-center">
        <b>${s}</b>
        <span>/ 100</span>
      </div>
    </div>
    <div class="health-factors">
      ${[['Savings rate', p1], ['Expense ratio', p2], ['Budget use', p3]].map(([lbl, pct]) => `
        <div class="factor-row">
          <div class="factor-label"><span>${lbl}</span><b>${Math.round(pct)}%</b></div>
          <div class="mini-bar"><div class="mini-bar-fill" data-pct="${pct}" style="width:0"></div></div>
        </div>`).join('')}
    </div>
  </div>
</div>`;
}

function makeInsights() {
  const a = [];
  data.budgets.filter(b => b.percent > 100).forEach(b =>
    a.push({ kind: 'danger', icon: '⚠', title: `${b.category} is over its monthly limit`, body: `You've spent ${money(b.actual)} against a ${money(b.limit_amount)} budget. Consider reviewing upcoming spending.` }));
  data.budgets.filter(b => b.percent >= 80 && b.percent <= 100).forEach(b =>
    a.push({ kind: 'warn', icon: '◷', title: `${b.category} is approaching its limit`, body: `You've used ${b.percent}% of your ${money(b.limit_amount)} budget — ${money(b.limit_amount - b.actual)} remaining.` }));
  if (data.savings_rate < 20)
    a.push({ kind: 'info', icon: '↗', title: 'Give your savings rate a small boost', body: `You saved ${data.savings_rate}% of this month's income. The reference target is 20% — even small consistent increases compound over time.` });
  else
    a.push({ kind: 'ok', icon: '✧', title: 'Your savings pace is building resilience', body: `You kept ${data.savings_rate}% of monthly income after expenses. That's a healthy margin — keep it going.` });
  if (!a.length)
    a.push({ kind: 'ok', icon: '✓', title: 'A balanced month so far', body: 'Your recorded spending is within the limits you set. Keep checking in as the month unfolds.' });
  return a;
}

/* ══════════════════════════════════════════
   CHART.JS — RENDERING
══════════════════════════════════════════ */
function chartColors() {
  const dark = document.documentElement.getAttribute('data-theme') === 'dark';
  return {
    grid:   dark ? '#2d3250' : '#e2e8f0',
    text:   dark ? '#7a85a0' : '#94a3b8',
    teal:   '#0d9488',
    coral:  '#f43f5e',
    gold:   '#f59e0b',
    blue:   '#3b82f6',
  };
}

function renderCharts() {
  const r = route();
  const cc = chartColors();

  Chart.defaults.color = cc.text;
  Chart.defaults.borderColor = cc.grid;

  // Trend chart (overview + insights)
  const trendEl = $('#trend-chart') || $('#insights-trend');
  if (trendEl) {
    activeCharts.trend = new Chart(trendEl, {
      type: 'line',
      data: {
        labels: data.trend.map(x => x.month),
        datasets: [
          { label: 'Income',   data: data.trend.map(x => x.income),  borderColor: cc.teal,  backgroundColor: cc.teal + '20', tension: .4, fill: true, pointBackgroundColor: cc.teal,  pointRadius: 4 },
          { label: 'Spending', data: data.trend.map(x => x.expense), borderColor: cc.coral, backgroundColor: cc.coral + '20', tension: .4, fill: true, pointBackgroundColor: cc.coral, pointRadius: 4 },
        ]
      },
      options: {
        responsive: true,
        animation: { duration: 900, easing: 'easeInOutQuart' },
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => ` ${money(ctx.parsed.y)}` } } },
        scales: {
          x: { grid: { color: cc.grid }, ticks: { font: { size: 10 } } },
          y: { grid: { color: cc.grid }, ticks: { font: { size: 10 }, callback: v => '₹' + (v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v) } }
        }
      }
    });
  }

  // Budget bar chart
  const budgetEl = $('#budget-chart');
  if (budgetEl) {
    activeCharts.budget = new Chart(budgetEl, {
      type: 'bar',
      data: {
        labels: data.budgets.map(b => b.category),
        datasets: [
          { label: 'Spent',   data: data.budgets.map(b => b.actual),        backgroundColor: data.budgets.map(b => b.percent > 100 ? cc.coral + 'cc' : cc.teal + 'cc'), borderRadius: 6 },
          { label: 'Budgeted', data: data.budgets.map(b => b.limit_amount), backgroundColor: cc.text + '33', borderRadius: 6 },
        ]
      },
      options: {
        responsive: true,
        animation: { duration: 900 },
        plugins: { legend: { labels: { font: { size: 10 }, boxWidth: 10 } }, tooltip: { callbacks: { label: ctx => ` ${money(ctx.parsed.y)}` } } },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10 }, maxRotation: 35 } },
          y: { grid: { color: cc.grid }, ticks: { font: { size: 10 }, callback: v => '₹' + (v >= 1000 ? v/1000 + 'k' : v) } }
        }
      }
    });
  }

  // Goals doughnut chart
  const goalsEl = $('#goals-chart');
  if (goalsEl) {
    activeCharts.goals = new Chart(goalsEl, {
      type: 'doughnut',
      data: {
        labels: data.goals.map(g => g.name),
        datasets: [{
          data: data.goals.map(g => g.saved_amount),
          backgroundColor: DONUT_COLORS.slice(0, data.goals.length),
          borderWidth: 2,
          borderColor: document.documentElement.getAttribute('data-theme') === 'dark' ? '#1a1d27' : '#fff',
        }]
      },
      options: {
        responsive: true,
        cutout: '65%',
        animation: { animateRotate: true, duration: 1000 },
        plugins: {
          legend: { position: 'right', labels: { font: { size: 11 }, boxWidth: 10, padding: 14 } },
          tooltip: { callbacks: { label: ctx => ` ${money(ctx.parsed)} saved` } }
        }
      }
    });
  }
}

/* ══════════════════════════════════════════
   ANIMATE BARS / COUNTERS
══════════════════════════════════════════ */
function animateBars() {
  // budget bars
  requestAnimationFrame(() => {
    $$('.budget-fill').forEach(el => {
      const pct = parseFloat(el.dataset.pct) || 0;
      setTimeout(() => { el.style.width = pct + '%'; }, 50);
    });
    // goal bars
    $$('.goal-bar').forEach(el => {
      const pct = parseFloat(el.dataset.pct) || 0;
      setTimeout(() => { el.style.width = pct + '%'; }, 80);
    });
    // mini bars
    $$('.mini-bar-fill').forEach(el => {
      const pct = parseFloat(el.dataset.pct) || 0;
      setTimeout(() => { el.style.width = pct + '%'; }, 120);
    });
    // count-up numbers (stat cards)
    $$('.stat-value.count-num').forEach(el => {
      const raw = el.dataset.val;
      if (!raw) return;
      const target = parseFloat(raw);
      if (isNaN(target)) return;
      let start = null;
      const dur = 900;
      const step = ts => {
        if (!start) start = ts;
        const p = Math.min((ts - start) / dur, 1);
        const ease = 1 - Math.pow(1 - p, 3);
        el.textContent = money(target * ease);
        if (p < 1) requestAnimationFrame(step);
        else el.textContent = money(target);
      };
      requestAnimationFrame(step);
    });
  });
}

/* ══════════════════════════════════════════
   BIND PAGE INTERACTIONS
══════════════════════════════════════════ */
function bindPage() {
  const r = route();

  /* ── Transactions page ── */
  if (r === 'transactions') {
    // category options update on type change
    const updateCats = () => {
      const isIncome = $('#tx-type').value === 'income';
      const opts = isIncome ? ['Salary', 'Freelance'] : data.budgets.map(x => x.category);
      $('#tx-category').innerHTML = opts.map(x => `<option>${esc(x)}</option>`).join('');
    };
    $('#tx-type').addEventListener('change', updateCats);
    updateCats();

    // form submit
    $('#tx-form').addEventListener('submit', async e => {
      e.preventDefault();
      const f = new FormData(e.target);
      try {
        await post('/api/transactions', Object.fromEntries(f));
      } catch (err) { toast(err.message, 'error'); }
    });

    // filter
    const filter = () => {
      const q = $('#tx-search').value.toLowerCase();
      const k = $('#tx-kind').value;
      const c = $('#tx-cat').value;
      const rows = data.transactions.filter(x =>
        (k === 'all' || x.kind === k) &&
        (c === 'all' || x.category === c) &&
        (`${x.description} ${x.category}`.toLowerCase().includes(q))
      );
      $('#tx-list').innerHTML = txTable(rows);
    };
    $('#tx-search').addEventListener('input', filter);
    $('#tx-kind').addEventListener('change', filter);
    $('#tx-cat').addEventListener('change', filter);
  }

  /* ── Budgets page ── */
  if (r === 'budgets') {
    $('#budget-form')?.addEventListener('submit', async e => {
      e.preventDefault();
      const f = new FormData(e.target);
      try { await post('/api/budgets', { category: f.get('category'), amount: f.get('amount') }); }
      catch (err) { toast(err.message, 'error'); }
    });
    $('#focus-budget')?.addEventListener('click', () =>
      $('#budget-form-panel')?.scrollIntoView({ behavior: 'smooth', block: 'center' }));
  }

  /* ── Goals page ── */
  if (r === 'goals') {
    $('#goal-form')?.addEventListener('submit', async e => {
      e.preventDefault();
      const f = new FormData(e.target);
      try { await post('/api/goals', Object.fromEntries(f)); }
      catch (err) { toast(err.message, 'error'); }
    });
    $('#focus-goal')?.addEventListener('click', () =>
      $('#goal-form-panel')?.scrollIntoView({ behavior: 'smooth', block: 'center' }));

    $$('.contribute-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        contributeGoalId = btn.dataset.id;
        $('#contribute-label').textContent = `Add savings to "${btn.dataset.name}"`;
        $('#contribute-amount').value = '';
        openModal();
      });
    });
  }
}

/* ── Modal ── */
function openModal() {
  $('#modal-backdrop').classList.add('open');
  $('#contribute-modal').classList.add('open');
  setTimeout(() => $('#contribute-amount').focus(), 50);
}
function closeModal() {
  $('#modal-backdrop').classList.remove('open');
  $('#contribute-modal').classList.remove('open');
  contributeGoalId = null;
}

document.addEventListener('DOMContentLoaded', () => {
  $('#modal-close')?.addEventListener('click', closeModal);
  $('#modal-cancel')?.addEventListener('click', closeModal);
  $('#modal-backdrop')?.addEventListener('click', closeModal);

  $('#modal-confirm')?.addEventListener('click', async () => {
    const amount = $('#contribute-amount').value;
    if (!amount || +amount <= 0) { toast('Enter a positive amount', 'error'); return; }
    try {
      await post(`/api/goals/${contributeGoalId}/contribute`, { amount });
      closeModal();
    } catch (err) { toast(err.message, 'error'); }
  });
});

/* ── Hash navigation ── */
window.addEventListener('hashchange', () => { if (data) render(); });

/* ── Boot ── */
load().catch(err => {
  $('#page-content').innerHTML = `
    <div style="max-width:480px;margin:60px auto">
      <div class="card card-pad">
        <div style="font-size:36px;margin-bottom:14px">⚠️</div>
        <h2 style="font-family:'Sora',sans-serif;font-size:18px;margin-bottom:8px">Could not load the dashboard</h2>
        <p style="color:var(--ink3);font-size:13px;line-height:1.6">${esc(err.message)}. Make sure the Python server is running on <code>http://127.0.0.1:8000</code> and reload.</p>
        <button class="btn btn-primary" style="margin-top:16px" onclick="location.reload()">Retry</button>
      </div>
    </div>`;
});
