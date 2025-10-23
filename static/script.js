document.addEventListener('DOMContentLoaded', () => {
    const discoverForm = document.getElementById('discover-form');
    const discoverProgress = document.getElementById('discover-progress');
    const domainSearch = document.getElementById('domain-search');
    const domainList = document.getElementById('domain-list');
    const urlList = document.getElementById('url-list');
    const filterInput = document.getElementById('filter-input');
    const sortAscBtn = document.getElementById('sort-asc');
    const sortDescBtn = document.getElementById('sort-desc');
    const selectAllBtn = document.getElementById('select-all');
    const unselectAllBtn = document.getElementById('unselect-all');
    const selectedCountEl = document.getElementById('selected-count');
    const createJobsBtn = document.getElementById('create-jobs-btn');
    const jobProgress = document.getElementById('job-progress');
    const stopDiscoveryBtn = document.getElementById('stop-discovery');
    const stopJobsBtn = document.getElementById('stop-jobs');
    const refreshLogsBtn = document.getElementById('refresh-logs-btn');
    const discoveryLogs = document.getElementById('discovery-logs');
    const viewToggleCheckbox = document.getElementById('view-toggle-checkbox');
    const viewToggleLabel = document.getElementById('view-toggle-label');
    const exportSelectedBtn = document.getElementById('export-selected');
    const exportDomainBtn = document.getElementById('export-domain');

    // Debug: Check if elements are found
    console.log('Elements found:', {
        discoverForm: !!discoverForm,
        discoverProgress: !!discoverProgress,
        stopDiscoveryBtn: !!stopDiscoveryBtn
    });

    let currentUrls = [];
    let displayedUrls = [];
    let selectedUrls = new Set();
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
                    // When discovery is done, reload domains and URLs
                    loadDomains();
                    const selectedDomain = document.querySelector('input[name="domain"]:checked').value;
                    loadUrls(selectedDomain);
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
        const urlRegex = document.getElementById('url-regex').value;
        if (startUrls.length === 0 || !targetCount) {
            alert('Please enter at least one URL and a target count');
            return;
        }

        const response = await fetch('/discover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ urls: startUrls, count: parseInt(targetCount), regex: urlRegex }),
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

        if (result.session_id) {
            // Use history.pushState to change the URL without a full page reload
            history.pushState({sessionId: result.session_id}, `Session ${result.session_id}`, `/${result.session_id}`);
        }
    });

    // Load domains
    const loadDomains = async () => {
        const response = await fetch('/domains');
        const domains = await response.json();
        let domainHTML = '<div><input type="radio" name="domain" value="all" checked> All Domains</div>';
        domainHTML += domains.map(d => `<div><input type="radio" name="domain" value="${d}"> ${d}</div>`).join('');
        domainList.innerHTML = domainHTML;
        loadUrls('all');

        domainList.addEventListener('change', (e) => {
            if (e.target.name === 'domain') {
                loadUrls(e.target.value);
            }
        });

        domainSearch.addEventListener('input', () => {
            const searchText = domainSearch.value.toLowerCase();
            domainList.querySelectorAll('div').forEach(div => {
                const domainName = div.textContent.trim().toLowerCase();
                if (domainName.includes(searchText)) {
                    div.style.display = 'block';
                } else {
                    div.style.display = 'none';
                }
            });
        });
    };

    // Load URLs for a domain
    const loadUrls = async (domain) => {
        const sessionId = window.location.pathname.split('/')[1];
        let url = `/urls/${domain}`;
        if (sessionId) {
            url += `?session_id=${sessionId}`;
        }

        if (domain === 'all') {
            const response = await fetch('/domains');
            const domains = await response.json();
            let allUrls = [];
            for (const d of domains) {
                let domainUrl = `/urls/${d}`;
                if (sessionId) {
                    domainUrl += `?session_id=${sessionId}`;
                }
                const urlsResponse = await fetch(domainUrl);
                const urls = await urlsResponse.json();
                allUrls = allUrls.concat(urls);
            }
            currentUrls = [...new Set(allUrls)];
            renderUrls(currentUrls);
        } else {
            const response = await fetch(url);
            const urls = await response.json();
            currentUrls = [...new Set(urls)];
            renderUrls(currentUrls);
        }
    };

    // Render URLs
    const renderUrls = (urls) => {
        displayedUrls = urls;
        urlList.innerHTML = urls.map((url, index) => {
            const isChecked = selectedUrls.has(url) ? 'checked' : '';
            return `<div><input type="checkbox" id="url-${index}" data-url="${url}" ${isChecked}> ${url}</div>`;
        }).join('');
        updateSelectedCount();
    };

    // Event Listeners
    filterInput.addEventListener('input', () => {
        const filterText = filterInput.value.toLowerCase();
        const filteredUrls = currentUrls.filter(url => url.toLowerCase().includes(filterText));
        renderUrls(filteredUrls);
    });
    sortAscBtn.addEventListener('click', () => renderUrls([...displayedUrls].sort()));
    sortDescBtn.addEventListener('click', () => renderUrls([...displayedUrls].sort().reverse()));
    selectAllBtn.addEventListener('click', () => setAllCheckboxes(true));
    unselectAllBtn.addEventListener('click', () => setAllCheckboxes(false));

    urlList.addEventListener('change', (e) => {
        if (e.target.type === 'checkbox') {
            const url = e.target.dataset.url;
            if (e.target.checked) {
                selectedUrls.add(url);
            } else {
                selectedUrls.delete(url);
            }
            updateSelectedCount();
        }
    });

    const setAllCheckboxes = (checked) => {
        displayedUrls.forEach(url => {
            if (checked) {
                selectedUrls.add(url);
            } else {
                selectedUrls.delete(url);
            }
        });
        renderUrls(displayedUrls);
    };

    const updateSelectedCount = () => {
        selectedCountEl.textContent = `Selected URLs: ${selectedUrls.size}`;
    };

    // Bulk Job Creation
    createJobsBtn.addEventListener('click', async () => {
        console.log('Create jobs button clicked');
        try {
            const urlsToCreate = Array.from(selectedUrls);
            console.log('Selected URLs:', urlsToCreate);
            if (urlsToCreate.length === 0) {
                alert('Please select at least one URL.');
                return;
            }
            const targetCount = document.getElementById('job-target-count').value;
            if (!targetCount) {
                alert('Please enter a target job count.');
                return;
            }
            console.log('Target count:', targetCount);
            const rateLimit = document.getElementById('rate-limit').value;
            const customParams = document.getElementById('custom-params').value;
            const response = await fetch('/create-jobs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    urls: urlsToCreate,
                    target_count: parseInt(targetCount),
                    rate_limit: parseInt(rateLimit),
                    custom_params: customParams
                })
            });
            const result = await response.json();
            console.log('Create jobs response:', result);
            if (result.task_ids) {
                jobProgress.innerHTML = '';
                result.task_ids.forEach(taskId => {
                    currentJobsTaskIds.push(taskId);
                    const progressElement = document.createElement('div');
                    progressElement.id = `task-${taskId}`;
                    jobProgress.appendChild(progressElement);
                    pollStatus(taskId, progressElement, 'jobs');
                });
                stopJobsBtn.style.display = 'inline-block';
            } else {
                alert('Error creating jobs: ' + (result.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error creating jobs:', error);
            alert('Failed to create jobs: ' + error.message);
        }
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

    // Load discovery logs
    const loadDiscoveryLogs = async () => {
        const response = await fetch('/discovery-logs');
        const logs = await response.json();
        discoveryLogs.innerHTML = logs.map(log => `
            <div class="log-entry">
                <span class="timestamp">${log.timestamp}</span>
                <span class="domain">${log.domain}</span>
                <span class="error">${log.error}</span>
            </div>
        `).join('');
    };

    // Event listener for the refresh logs button
    refreshLogsBtn.addEventListener('click', loadDiscoveryLogs);

    // View toggle logic
    viewToggleCheckbox.addEventListener('change', () => {
        const sessionId = window.location.pathname.split('/')[1];
        if (viewToggleCheckbox.checked) {
            viewToggleLabel.textContent = 'Global View';
            loadUrls('all');
        } else {
            viewToggleLabel.textContent = 'Actual View';
            if (sessionId) {
                loadUrlsForSession(sessionId);
            } else {
                urlList.innerHTML = '<div>No active discovery session.</div>';
            }
        }
    });

    const loadUrlsForSession = async (sessionId) => {
        const response = await fetch(`/urls/session/${sessionId}`);
        const urls = await response.json();
        currentUrls = [...new Set(urls)];
        renderUrls(currentUrls);
    };

    // Initial load
    loadDomains();
    loadDiscoveryLogs();

    // Helper function to download content to a file
    const downloadToFile = (content, filename, contentType) => {
        const a = document.createElement('a');
        const file = new Blob([content], { type: contentType });
        a.href = URL.createObjectURL(file);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
    };

    // Event listener for exporting selected URLs
    exportSelectedBtn.addEventListener('click', () => {
        const urlsToExport = Array.from(selectedUrls);
        if (urlsToExport.length === 0) {
            alert('No URLs selected for export.');
            return;
        }
        const fileContent = urlsToExport.join('\n');
        downloadToFile(fileContent, 'selected_urls.txt', 'text/plain');
    });

    // Event listener for exporting domain URLs
    exportDomainBtn.addEventListener('click', async () => {
        const selectedDomainInput = domainList.querySelector('input[name="domain"]:checked');
        if (!selectedDomainInput) {
            alert('Please select a domain.');
            return;
        }
        const domain = selectedDomainInput.value;
        let urlsToExport = [];
        if (domain === 'all') {
            const response = await fetch('/domains');
            const domains = await response.json();
            for (const d of domains) {
                const urlsResponse = await fetch(`/urls/${d}`);
                const urls = await urlsResponse.json();
                urlsToExport = urlsToExport.concat(urls);
            }
            urlsToExport = [...new Set(urlsToExport)];
        } else {
            const response = await fetch(`/urls/${domain}`);
            urlsToExport = await response.json();
        }

        if (urlsToExport.length === 0) {
            alert('No URLs found for the selected domain.');
            return;
        }
        const fileContent = urlsToExport.join('\n');
        downloadToFile(fileContent, `${domain}_urls.txt`, 'text/plain');
    });
});
