const state = {
  report: null,
  keyword: 'all',
  query: ''
};

const dateSelect = document.getElementById('date-select');
const keywordSelect = document.getElementById('keyword-select');
const searchInput = document.getElementById('search-input');
const summaryEl = document.getElementById('summary');
const papersEl = document.getElementById('papers');
const trendsEl = document.getElementById('trends');

const statDate = document.getElementById('stat-date');
const statTotal = document.getElementById('stat-total');
const statMatched = document.getElementById('stat-matched');
const footerDate = document.getElementById('footer-date');

// Debounce utility
function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

// Loading state
function showLoading(element, message = '加载中...') {
  element.innerHTML = `<div class="loading-state"><span class="loading-spinner"></span>${message}</div>`;
}

async function fetchDates() {
  const res = await fetch('/api/dates');
  if (!res.ok) return [];
  return await res.json();
}

async function fetchReport(date) {
  const url = date ? `/api/report?date=${date}` : '/api/report';
  const res = await fetch(url);
  if (!res.ok) return null;
  return await res.json();
}

function updateStats(report) {
  statDate.textContent = report.date || '-';
  statTotal.textContent = report.total_papers ?? '-';
  statMatched.textContent = report.matched_papers ?? '-';
  footerDate.textContent = report.date ? `更新于 ${report.date}` : '';
}

function updateSummary(report) {
  const keyword = state.keyword;
  const keywords = report.keywords || [];
  const summary = report.summaries || {};

  if (keyword === 'all') {
    summaryEl.innerHTML = `
      <h2>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -3px; margin-right: 8px;">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
          <line x1="16" y1="17" x2="8" y2="17"></line>
          <polyline points="10 9 9 9 8 9"></polyline>
        </svg>
        今日总览
      </h2>
      <p>共抓取 <strong>${report.total_papers || 0}</strong> 篇论文，匹配 <strong>${report.matched_papers || 0}</strong> 篇，完成深度分析 <strong>${report.analyzed_papers || 0}</strong> 篇。</p>
      <p>请选择领域查看对应总结，或使用搜索框定位具体论文。</p>
    `;
    return;
  }

  const content = summary[keyword] || '今日该领域暂无相关论文更新。';
  const linkedContent = linkifyPaperRefsHtml(renderMarkdown(content), keyword);
  summaryEl.innerHTML = `
    <h2>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -3px; margin-right: 8px;">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
      </svg>
      ${keyword}
    </h2>
    <div class="markdown">${linkedContent}</div>
  `;
}

function collectUniquePapers(report) {
  const map = new Map();
  for (const list of Object.values(report.papers_by_keyword || {})) {
    for (const paper of list || []) {
      const key = paper.id || paper.arxiv_id || paper.title;
      if (!map.has(key)) {
        map.set(key, paper);
      }
    }
  }
  return Array.from(map.values());
}

function updateTrends(report) {
  const keywords = report.keywords || [];
  const counts = keywords.map((kw) => ({
    name: kw,
    count: (report.papers_by_keyword?.[kw] || []).length,
  }));
  counts.sort((a, b) => b.count - a.count);
  const topKeywords = counts.slice(0, 6);

  const uniquePapers = collectUniquePapers(report);
  let arxivCount = 0;
  let journalCount = 0;
  uniquePapers.forEach((paper) => {
    if (paper.source === 'journal') {
      journalCount += 1;
    } else {
      arxivCount += 1;
    }
  });

  trendsEl.innerHTML = `
    <div class="trend-card">
      <div class="trend-head">
        <h3>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -2px; margin-right: 6px;">
            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline>
            <polyline points="17 6 23 6 23 12"></polyline>
          </svg>
          今日主题趋势
        </h3>
        <span class="trend-sub">按论文数量排序</span>
      </div>
      <div class="trend-tags">
        ${topKeywords
          .map(
            (item) =>
              `<span class="trend-tag"><strong>${item.count}</strong> ${item.name}</span>`
          )
          .join('')}
      </div>
    </div>
    <div class="trend-card">
      <div class="trend-head">
        <h3>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -2px; margin-right: 6px;">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
          </svg>
          来源覆盖
        </h3>
        <span class="trend-sub">去重后的论文来源分布</span>
      </div>
      <div class="trend-metrics">
        <div>
          <span class="trend-label">arXiv</span>
          <span class="trend-value">${arxivCount}</span>
        </div>
        <div>
          <span class="trend-label">期刊</span>
          <span class="trend-value">${journalCount}</span>
        </div>
      </div>
    </div>
  `;
}

function getFilteredPapers(report) {
  const keyword = state.keyword;
  const query = state.query.trim().toLowerCase();
  let papers = [];

  if (keyword === 'all') {
    for (const list of Object.values(report.papers_by_keyword || {})) {
      papers = papers.concat(list);
    }
  } else {
    papers = report.papers_by_keyword?.[keyword] || [];
  }

  // Filter by search query
  if (query) {
    papers = papers.filter((paper) => {
      const haystack = [
        paper.title,
        paper.tldr,
        paper.methodology,
        paper.experiments,
        paper.authors?.join(' '),
        paper.affiliations?.join(' '),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(query);
    });
  }

  // Sort by quality score (descending)
  papers.sort((a, b) => (b.quality_score || 0) - (a.quality_score || 0));

  return papers;
}

function renderInfoCard(label, content, icon) {
  const safeContent = content ? renderMarkdown(content) : '<p class="empty-hint">未明确说明</p>';
  return `
    <div class="paper-info-item">
      <div class="paper-info-label">${icon}${label}</div>
      <div class="markdown">${safeContent}</div>
    </div>
  `;
}

function renderPapers(report) {
  const papers = getFilteredPapers(report);

  if (!papers.length) {
    papersEl.innerHTML = `
      <div class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <p>暂无匹配结果</p>
      </div>
    `;
    return;
  }

  const keyword = state.keyword;
  const keywordSlug = keyword === 'all' ? '' : slugify(keyword);

  papersEl.innerHTML = papers
    .map((paper, index) => {
      const tags = (paper.matched_keywords || []).map((tag) => `<span class="tag">${tag}</span>`).join('');
      const source = paper.source === 'journal' ? `期刊 · ${paper.primary_category || 'Journal'}` : 'arXiv';
      const authors = paper.authors?.slice(0, 4).join(', ') || '';
      const abstractText = paper.summary || '';
      const abstractUrl = paper.abstract_url || paper.pdf_url || '';
      const cardId =
        keyword === 'all'
          ? `paper-${paper.id || paper.arxiv_id || Math.random().toString(36).slice(2)}`
          : `paper-${keywordSlug}-${index + 1}`;
      const numberBadge =
        keyword === 'all'
          ? ''
          : `<span class="paper-number">${index + 1}</span>`;
      const contributions = Array.isArray(paper.contributions)
        ? paper.contributions.map((c) => `- ${c}`).join('\n')
        : '';
      const innovations = Array.isArray(paper.innovations)
        ? paper.innovations.map((c) => `- ${c}`).join('\n')
        : '';
      const limitations = Array.isArray(paper.limitations)
        ? paper.limitations.map((c) => `- ${c}`).join('\n')
        : '';
      const methodText = paper.methodology || '';
      const expText = paper.experiments || '';
      const dataText = paper.dataset_info || '';
      const codeText = paper.code_url ? `[代码仓库](${paper.code_url})` : '';

      const methodIcon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: -1px; margin-right: 4px;"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>';
      const expIcon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: -1px; margin-right: 4px;"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>';
      const contribIcon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: -1px; margin-right: 4px;"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>';
      const dataIcon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: -1px; margin-right: 4px;"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>';
      const limitIcon = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: -1px; margin-right: 4px;"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';

      const infoItems = [
        renderInfoCard('方法', methodText, methodIcon),
        renderInfoCard('实验', expText, expIcon),
        renderInfoCard('贡献', contributions || innovations, contribIcon),
        renderInfoCard('数据 / 代码', [dataText, codeText].filter(Boolean).join('\n\n'), dataIcon),
        renderInfoCard('局限', limitations, limitIcon),
      ];

      const tldrText = paper.tldr || '';
      const tldrHtml = tldrText
        ? `<div class="paper-tldr">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink: 0;">
              <circle cx="12" cy="12" r="10"></circle>
              <path d="M12 16v-4"></path>
              <path d="M12 8h.01"></path>
            </svg>
            <div class="paper-tldr-content markdown">${renderMarkdown(tldrText)}</div>
          </div>`
        : '';

      // Quality score badge
      const score = paper.quality_score || 0;
      const scoreReason = paper.score_reason || '';
      const scoreClass = score >= 8 ? 'score-high' : score >= 6 ? 'score-medium' : 'score-low';
      const scoreHtml = score > 0
        ? `<div class="paper-score ${scoreClass}" title="${escapeHtml(scoreReason)}">
            <span class="score-value">${score}</span>
            <span class="score-label">/ 10</span>
          </div>`
        : '';

      return `
        <article class="paper-card" id="${cardId}">
          <div class="paper-head">
            <div>
              <p class="paper-source">${source}</p>
              <h3>${numberBadge}${paper.title || 'Untitled'}</h3>
            </div>
            <div class="paper-head-right">
              ${scoreHtml}
              <div class="paper-date">${paper.published || ''}</div>
            </div>
          </div>
          <div class="paper-meta">${authors}</div>
          ${tldrHtml}
          ${scoreReason ? `<div class="paper-score-reason"><span class="score-reason-label">评分理由：</span>${escapeHtml(scoreReason)}</div>` : ''}
          <div class="paper-info-list">
            ${infoItems.join('')}
          </div>
          <div class="paper-english" id="${cardId}-abstract" data-open="false">
            <div class="paper-english-label">英文摘要</div>
            <div class="markdown">${renderMarkdown(abstractText || '暂无摘要。')}</div>
          </div>
          <div class="paper-meta">${tags}</div>
          <div class="paper-actions">
            <button class="paper-toggle" data-target="${cardId}-abstract">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: -2px; margin-right: 4px;">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
              </svg>
              摘要
            </button>
            <a class="secondary" href="${abstractUrl}" target="_blank" rel="noreferrer">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: -2px; margin-right: 4px;">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                <polyline points="15 3 21 3 21 9"></polyline>
                <line x1="10" y1="14" x2="21" y2="3"></line>
              </svg>
              原文
            </a>
          </div>
        </article>
      `;
    })
    .join('');
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function linkifyPaperRefsHtml(html, keyword) {
  if (!html || keyword === 'all') return html;
  const slug = slugify(keyword);
  return html.replace(/论文\s*([0-9]+)/g, (match, num) => {
    return `<a href="#paper-${slug}-${num}" class="paper-ref">论文${num}</a>`;
  });
}

function renderMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);

  // Headings
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

  // Bold & italic
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');

  // Lists
  html = html.replace(/^\s*[-*] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (match) => `<ul>${match}</ul>`);

  // Paragraphs / line breaks
  html = html.replace(/\n{2,}/g, '</p><p>');
  html = `<p>${html.replace(/\n/g, '<br>')}</p>`;

  return html;
}

function highlightCardById(targetId) {
  if (!targetId) return;
  const card = document.getElementById(targetId);
  if (!card) return;
  card.classList.remove('paper-highlight');
  void card.offsetWidth;
  card.classList.add('paper-highlight');
  setTimeout(() => {
    card.classList.remove('paper-highlight');
  }, 1200);
}

function fillKeywordOptions(report) {
  const keywords = report.keywords || [];
  keywordSelect.innerHTML = '<option value="all">全部</option>';
  keywords.forEach((kw) => {
    const option = document.createElement('option');
    option.value = kw;
    option.textContent = kw;
    keywordSelect.appendChild(option);
  });
}

async function init() {
  showLoading(summaryEl, '加载报告中...');
  showLoading(papersEl, '');

  const dates = await fetchDates();
  if (dates.length) {
    dateSelect.innerHTML = dates.map((date) => `<option value="${date}">${date}</option>`).join('');
  }

  const report = await fetchReport(dates[0]);
  if (!report) {
    summaryEl.innerHTML = '<div class="empty-state"><p>暂无报告数据</p></div>';
    papersEl.innerHTML = '';
    return;
  }

  state.report = report;
  updateStats(report);
  updateTrends(report);
  fillKeywordOptions(report);
  updateSummary(report);
  renderPapers(report);
}

dateSelect.addEventListener('change', async (event) => {
  showLoading(papersEl, '加载中...');
  const report = await fetchReport(event.target.value);
  if (!report) return;
  state.report = report;
  state.keyword = 'all';
  state.query = '';
  keywordSelect.value = 'all';
  searchInput.value = '';
  updateStats(report);
  updateTrends(report);
  fillKeywordOptions(report);
  updateSummary(report);
  renderPapers(report);
});

keywordSelect.addEventListener('change', (event) => {
  state.keyword = event.target.value;
  updateSummary(state.report);
  renderPapers(state.report);
});

const debouncedSearch = debounce(() => {
  renderPapers(state.report);
}, 200);

searchInput.addEventListener('input', (event) => {
  state.query = event.target.value;
  debouncedSearch();
});

summaryEl.addEventListener('click', (event) => {
  const link = event.target.closest('a[href^="#paper-"]');
  if (!link) return;
  const targetId = link.getAttribute('href').slice(1);
  setTimeout(() => highlightCardById(targetId), 100);
});

window.addEventListener('hashchange', () => {
  const targetId = window.location.hash.replace('#', '');
  highlightCardById(targetId);
});

papersEl.addEventListener('click', (event) => {
  const btn = event.target.closest('.paper-toggle');
  if (!btn) return;
  const targetId = btn.getAttribute('data-target');
  const panel = document.getElementById(targetId);
  if (!panel) return;
  const isOpen = panel.getAttribute('data-open') === 'true';

  document.querySelectorAll('.paper-english.open').forEach((openPanel) => {
    if (openPanel.id !== targetId) {
      openPanel.classList.remove('open');
      openPanel.setAttribute('data-open', 'false');
      const relatedBtn = document.querySelector(`.paper-toggle[data-target="${openPanel.id}"]`);
      if (relatedBtn) {
        relatedBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: -2px; margin-right: 4px;">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
          </svg>
          摘要
        `;
      }
    }
  });

  panel.setAttribute('data-open', isOpen ? 'false' : 'true');
  panel.classList.toggle('open', !isOpen);
  btn.innerHTML = isOpen
    ? `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: -2px; margin-right: 4px;">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
      </svg>
      摘要`
    : `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: -2px; margin-right: 4px;">
        <polyline points="18 15 12 9 6 15"></polyline>
      </svg>
      收起`;
});

init();
