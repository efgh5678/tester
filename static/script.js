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
    let currentDiscoveryTaskId = null;
    let currentJobsTaskId = null;

    // Polling function for task status
    const pollStatus = async (taskId, progressElement, taskType) => {
        const interval = setInterval(async () => {
            const response = await fetch(`/status/${taskId}`);
            const data = await response.json();
            progressElement.textContent = `Status: ${data.status}, Progress: ${data.progress}/${data.total}`;
            if (data.status === 'completed' || data.status === 'failed' || data.status === 'stopped') {
                clearInterval(interval);
                if (taskType === 'discovery') {
                    stopDiscoveryBtn.style.display = 'none';
                    currentDiscoveryTaskId = null;
                    // Always refresh domains so partial results are visible even on failure/stopped
                    loadDomains();
                } else if (taskType === 'jobs') {
                    stopJobsBtn.style.display = 'none';
                    currentJobsTaskId = null;
                }
            }
        }, 2000);
    };

    // URL Discovery
    discoverForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        console.log('Discovery form submitted');
        
        const startUrl = document.getElementById('start-url').value;
        const targetCount = document.getElementById('target-count').value;
        
        if (!startUrl || !targetCount) {
            alert('Please enter both URL and target count');
            return;
        }
        
        console.log('Starting discovery for:', startUrl, 'target:', targetCount);
        
        try {
            const response = await fetch('/discover', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: startUrl, count: parseInt(targetCount) }),
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            console.log('Discovery started, task_id:', result.task_id);
            
            currentDiscoveryTaskId = result.task_id;
            stopDiscoveryBtn.style.display = 'inline-block';
            pollStatus(result.task_id, discoverProgress, 'discovery');
        } catch (error) {
            console.error('Error starting discovery:', error);
            alert('Failed to start discovery: ' + error.message);
        }
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
        currentJobsTaskId = result.task_id;
        stopJobsBtn.style.display = 'inline-block';
        pollStatus(result.task_id, jobProgress, 'jobs');
    });

    // Stop button event listeners
    stopDiscoveryBtn.addEventListener('click', async () => {
        if (currentDiscoveryTaskId) {
            try {
                await fetch(`/stop/${currentDiscoveryTaskId}`, { method: 'POST' });
                stopDiscoveryBtn.textContent = 'Stopping...';
                stopDiscoveryBtn.disabled = true;
            } catch (error) {
                console.error('Error stopping discovery:', error);
            }
        }
    });

    stopJobsBtn.addEventListener('click', async () => {
        if (currentJobsTaskId) {
            try {
                await fetch(`/stop/${currentJobsTaskId}`, { method: 'POST' });
                stopJobsBtn.textContent = 'Stopping...';
                stopJobsBtn.disabled = true;
            } catch (error) {
                console.error('Error stopping jobs:', error);
            }
        }
    });

    // Initial load
    loadDomains();
});
