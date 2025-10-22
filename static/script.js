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
    const stopDiscoveryBtn = document.getElementById('stop-discovery');
    const stopJobsBtn = document.getElementById('stop-jobs');

    // Debug: Check if elements are found
    console.log('Elements found:', {
        discoverForm: !!discoverForm,
        discoverProgress: !!discoverProgress,
        stopDiscoveryBtn: !!stopDiscoveryBtn
    });

    let currentUrls = [];
    let displayedUrls = [];
    let currentDiscoveryTaskIds = [];
    let currentJobsTaskIds = [];

    // Polling function for task status
    const pollStatus = async (taskId, progressElement, taskType) => {
        const interval = setInterval(async () => {
            const response = await fetch(`/status/${taskId}`);
            const data = await response.json();
            const percentage = data.total > 0 ? (data.progress / data.total) * 100 : 0;
            if (taskType === 'discovery') {
                progressElement.innerHTML = `
                    <div>
                        <span>URL: ${data.url} - Status: ${data.status}</span>
                        <div class="progress-bar-container">
                            <div class="progress-bar" style="width: ${percentage}%;"></div>
                        </div>
                        <span>${data.progress}/${data.total}</span>
                    </div>
                `;
            } else if (taskType === 'jobs') {
                progressElement.innerHTML = `
                    <div>
                        <span>Domain: ${data.domain} - Status: ${data.status}</span>
                        <div class="progress-bar-container">
                            <div class="progress-bar" style="width: ${percentage}%;"></div>
                        </div>
                        <span>${data.progress}/${data.total}</span>
                    </div>
                `;
            }

            if (data.status === 'completed' || data.status === 'failed' || data.status === 'stopped') {
                clearInterval(interval);
                if (taskType === 'discovery') {
                    const index = currentDiscoveryTaskIds.indexOf(taskId);
                    if (index > -1) {
                        currentDiscoveryTaskIds.splice(index, 1);
                    }
                    if (currentDiscoveryTaskIds.length === 0) {
                        stopDiscoveryBtn.style.display = 'none';
                    }
                    loadDomains();
                } else if (taskType === 'jobs') {
                    const index = currentJobsTaskIds.indexOf(taskId);
                    if (index > -1) {
                        currentJobsTaskIds.splice(index, 1);
                    }
                    if (currentJobsTaskIds.length === 0) {
                        stopJobsBtn.style.display = 'none';
                    }
                }
            }
        }, 2000);
    };

    // URL Discovery
    discoverForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const startUrls = document.getElementById('start-urls').value.split('\n').filter(url => url.trim() !== '');
        const targetCount = document.getElementById('target-count').value;
        if (startUrls.length === 0 || !targetCount) {
            alert('Please enter at least one URL and a target count');
            return;
        }

        const response = await fetch('/discover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls: startUrls, count: parseInt(targetCount) }),
        });
        const result = await response.json();
        discoverProgress.innerHTML = '';
        result.task_ids.forEach(taskId => {
            currentDiscoveryTaskIds.push(taskId);
            const progressElement = document.createElement('div');
            progressElement.id = `task-${taskId}`;
            discoverProgress.appendChild(progressElement);
            pollStatus(taskId, progressElement, 'discovery');
        });
        stopDiscoveryBtn.style.display = 'inline-block';
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
        urlList.innerHTML = urls.map((url, index) => `<div><input type="checkbox" id="url-${index}" data-url="${url}"> ${url}</div>`).join('');
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
        displayedUrls.forEach((url, index) => {
            const checkbox = document.getElementById(`url-${index}`);
            if (checkbox) {
                checkbox.checked = checked;
            }
        });
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
        jobProgress.innerHTML = '';
        result.task_ids.forEach(taskId => {
            currentJobsTaskIds.push(taskId);
            const progressElement = document.createElement('div');
            progressElement.id = `task-${taskId}`;
            jobProgress.appendChild(progressElement);
            pollStatus(taskId, progressElement, 'jobs');
        });
        stopJobsBtn.style.display = 'inline-block';
    });

    // Stop button event listeners
    stopDiscoveryBtn.addEventListener('click', async () => {
        currentDiscoveryTaskIds.forEach(async (taskId) => {
            await fetch(`/stop/${taskId}`, { method: 'POST' });
        });
        stopDiscoveryBtn.textContent = 'Stopping...';
        stopDiscoveryBtn.disabled = true;
    });

    stopJobsBtn.addEventListener('click', async () => {
        currentJobsTaskIds.forEach(async (taskId) => {
            await fetch(`/stop/${taskId}`, { method: 'POST' });
        });
        stopJobsBtn.textContent = 'Stopping...';
        stopJobsBtn.disabled = true;
    });

    // Initial load
    loadDomains();
});
