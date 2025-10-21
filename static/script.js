document.addEventListener('DOMContentLoaded', () => {
    const discoverForm = document.getElementById('discover-form');
    const discoverProgress = document.getElementById('discover-progress');
    const domainSelect = document.getElementById('domain-select');
    const urlList = document.getElementById('url-list');
    const filterInput = document.getElementById('filter-input');
    const sortAscBtn = document.getElementById('sort-asc');
    const sortDescBtn = document.getElementById('sort-desc');
    const selectAllBtn = document.getElementById('select-all');
    const unselectAllBtn = document.getElementById('unselect-all');
    const selectedCountEl = document.getElementById('selected-count');
    const createJobsForm = document.getElementById('create-jobs-form');
    const jobProgress = document.getElementById('job-progress');

    let currentUrls = [];
    let displayedUrls = [];

    // Polling function for task status
    const pollStatus = async (taskId, progressElement) => {
        const interval = setInterval(async () => {
            const response = await fetch(`/status/${taskId}`);
            const data = await response.json();
            progressElement.textContent = `Status: ${data.status}, Progress: ${data.progress}/${data.total}`;
            if (data.status === 'completed' || data.status === 'failed') {
                clearInterval(interval);
                if (data.status === 'completed') {
                    loadDomains();
                }
            }
        }, 2000);
    };

    // URL Discovery
    discoverForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const startUrl = document.getElementById('start-url').value;
        const targetCount = document.getElementById('target-count').value;
        const response = await fetch('/discover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: startUrl, count: parseInt(targetCount) }),
        });
        const result = await response.json();
        pollStatus(result.task_id, discoverProgress);
    });

    // Load domains
    const loadDomains = async () => {
        const response = await fetch('/domains');
        const domains = await response.json();
        domainSelect.innerHTML = domains.map(d => `<option value="${d}">${d}</option>`).join('');
        if (domains.length > 0) {
            loadUrls(domains[0]);
        }
    };

    // Load URLs for a domain
    const loadUrls = async (domain) => {
        const response = await fetch(`/urls/${domain}`);
        currentUrls = await response.json();
        renderUrls(currentUrls);
    };

    // Render URLs
    const renderUrls = (urls) => {
        displayedUrls = urls;
        urlList.innerHTML = urls.map(url => `<div><input type="checkbox" data-url="${url}"> ${url}</div>`).join('');
        updateSelectedCount();
    };

    // Event Listeners
    domainSelect.addEventListener('change', () => loadUrls(domainSelect.value));
    filterInput.addEventListener('input', () => {
        const filterText = filterInput.value.toLowerCase();
        const filteredUrls = currentUrls.filter(url => url.toLowerCase().includes(filterText));
        renderUrls(filteredUrls);
    });
    sortAscBtn.addEventListener('click', () => renderUrls([...displayedUrls].sort()));
    sortDescBtn.addEventListener('click', () => renderUrls([...displayedUrls].sort().reverse()));
    selectAllBtn.addEventListener('click', () => setAllCheckboxes(true));
    unselectAllBtn.addEventListener('click', () => setAllCheckboxes(false));
    urlList.addEventListener('change', updateSelectedCount);

    const setAllCheckboxes = (checked) => {
        urlList.querySelectorAll('input[type="checkbox"]').forEach(checkbox => checkbox.checked = checked);
        updateSelectedCount();
    };

    const updateSelectedCount = () => {
        const selectedCount = urlList.querySelectorAll('input[type="checkbox"]:checked').length;
        selectedCountEl.textContent = `Selected URLs: ${selectedCount}`;
    };

    // Bulk Job Creation
    createJobsForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const selectedUrls = Array.from(urlList.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.dataset.url);
        if (selectedUrls.length === 0) {
            alert('Please select at least one URL.');
            return;
        }
        const targetCount = document.getElementById('job-target-count').value;
        const rateLimit = document.getElementById('rate-limit').value;
        const customParams = document.getElementById('custom-params').value;
        const response = await fetch('/create-jobs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                urls: selectedUrls,
                target_count: parseInt(targetCount),
                rate_limit: parseInt(rateLimit),
                custom_params: customParams
            })
        });
        const result = await response.json();
        pollStatus(result.task_id, jobProgress);
    });

    // Initial load
    loadDomains();
});
