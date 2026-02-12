/**
 * Blue Book Analysis Tool - Frontend Logic
 *
 * Handles form submission, API calls to /analyze,
 * and rendering of Claude's analysis results.
 */

// Character counter
const textarea = document.getElementById('medical-input');
const charCount = document.getElementById('char-count');

textarea.addEventListener('input', () => {
    charCount.textContent = `${textarea.value.length} characters`;
});

/**
 * Main function: send medical findings to the API and display results.
 */
async function analyzeFindings() {
    const input = textarea.value.trim();
    if (!input) {
        showError('Please enter the client\'s medical findings before analyzing.');
        return;
    }

    if (input.length < 20) {
        showError('Please provide more detailed medical findings (at least a few sentences).');
        return;
    }

    const btn = document.getElementById('analyze-btn');
    btn.disabled = true;
    btn.textContent = 'Analyzing...';

    showLoading();
    hideError();
    hideResults();

    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ medical_findings: input }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || `Server error (${response.status})`);
        }

        const data = await response.json();
        renderResults(data);
    } catch (error) {
        showError(error.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Analyze';
        hideLoading();
    }
}

/**
 * Render the analysis results from the API response.
 */
function renderResults(data) {
    // Show matched listing badges
    const badgesEl = document.getElementById('matched-badges');
    badgesEl.innerHTML = '';
    if (data.matched_listings && data.matched_listings.length > 0) {
        data.matched_listings.forEach(listing => {
            const badge = document.createElement('span');
            badge.className = 'badge';
            badge.textContent = `Listing ${listing}`;
            badgesEl.appendChild(badge);
        });
    }

    // Show meta info
    document.getElementById('listing-count').textContent =
        `${data.matched_listings ? data.matched_listings.length : 0} listings matched`;
    document.getElementById('doc-count').textContent =
        `${data.retrieved_count} documents searched`;

    // Render the analysis text with formatting
    const contentEl = document.getElementById('results-content');
    contentEl.innerHTML = formatAnalysis(data.analysis);

    // Render source links for verification
    const sourcesEl = document.getElementById('sources-list');
    sourcesEl.innerHTML = '';
    if (data.sources && Object.keys(data.sources).length > 0) {
        Object.values(data.sources).forEach(src => {
            const li = document.createElement('li');
            const a = document.createElement('a');
            a.href = src.source_url;
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            a.textContent = `Listing ${src.listing_number} - ${src.body_system}`;
            li.appendChild(a);
            li.appendChild(document.createTextNode(' — SSA Blue Book'));
            sourcesEl.appendChild(li);
        });
        document.getElementById('sources').classList.remove('hidden');
    } else {
        document.getElementById('sources').classList.add('hidden');
    }

    showResults();
}

/**
 * Convert Claude's markdown-like analysis text into styled HTML.
 */
function formatAnalysis(text) {
    if (!text) return '<p>No analysis available.</p>';

    let html = escapeHtml(text);

    // Convert ## headers to <h3>
    html = html.replace(/^##\s+(.+)$/gm, '<h3>$1</h3>');
    // Convert # headers to <h3> as well
    html = html.replace(/^#\s+(.+)$/gm, '<h3>$1</h3>');

    // Convert numbered section headers (1. TITLE, 2. TITLE, etc.)
    html = html.replace(
        /^(\d+)\.\s+((?:POTENTIALLY|CRITERIA|EVIDENCE|STRENGTH)[A-Z\s]+)/gm,
        '<h3>$1. $2</h3>'
    );

    // Style status markers
    html = html.replace(/✅\s*MET/g, '<span class="status-met">&#x2705; MET</span>');
    html = html.replace(/❓\s*UNCLEAR/g, '<span class="status-unclear">&#x2753; UNCLEAR</span>');
    html = html.replace(/❌\s*MISSING/g, '<span class="status-missing">&#x274C; MISSING</span>');

    // Also handle standalone emoji markers
    html = html.replace(/✅/g, '<span class="status-met">&#x2705;</span>');
    html = html.replace(/❓/g, '<span class="status-unclear">&#x2753;</span>');
    html = html.replace(/❌/g, '<span class="status-missing">&#x274C;</span>');

    // Style strength assessments
    html = html.replace(/\bSTRONG\b/g, '<span class="strength-strong">STRONG</span>');
    html = html.replace(/\bMODERATE\b/g, '<span class="strength-moderate">MODERATE</span>');
    html = html.replace(/\bWEAK\b/g, '<span class="strength-weak">WEAK</span>');

    // Convert **bold** to <strong>
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Convert --- or === horizontal rules to <hr>
    html = html.replace(/^[-=]{3,}$/gm, '<hr>');

    return html;
}

/**
 * Escape HTML special characters to prevent XSS.
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// --- UI State Helpers ---

function showLoading() {
    document.getElementById('loading').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
}

function showError(message) {
    document.getElementById('error-message').textContent = message;
    document.getElementById('error').classList.remove('hidden');
}

function hideError() {
    document.getElementById('error').classList.add('hidden');
}

function showResults() {
    document.getElementById('results').classList.remove('hidden');
}

function hideResults() {
    document.getElementById('results').classList.add('hidden');
}

// Allow Ctrl+Enter to submit
textarea.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
        analyzeFindings();
    }
});
