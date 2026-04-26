document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const elements = {
        statCpu: document.getElementById('stat-cpu'),
        statRam: document.getElementById('stat-ram'),
        statStatus: document.getElementById('stat-status'),
        activeCount: document.getElementById('active-count'),
        activeList: document.getElementById('active-list'),
        upcomingCount: document.getElementById('upcoming-count'),
        upcomingList: document.getElementById('upcoming-list'),
        nodesContainer: document.getElementById('nodes-container'),
        libraryStats: document.getElementById('library-stats'),
        recentList: document.getElementById('recent-list'),
        refreshBtn: document.getElementById('refresh-btn'),
        rescanBtn: document.getElementById('rescan-btn'),
        loadingOverlay: document.getElementById('loading-overlay'),
        
        // Pipeline elements
        pipelineUrl: document.getElementById('pipeline-url'),
        flowSelect: document.getElementById('flow-select'),
        triggerPipelineBtn: document.getElementById('trigger-pipeline-btn'),
        pipelineStatus: document.getElementById('pipeline-status'),

        // New elements
        tabs: document.querySelectorAll('.tab-btn'),
        tabContents: document.querySelectorAll('.tab-content'),
        libraryFilesBody: document.getElementById('library-files-body'),
        templatesGrid: document.getElementById('templates-grid'),
        
        // Instagram elements
        igUrl: document.getElementById('ig-url'),
        igFetchBtn: document.getElementById('ig-fetch-btn'),
        igDownloadBtn: document.getElementById('ig-download-btn'),
        igStatus: document.getElementById('ig-status'),
        igResultCard: document.getElementById('ig-result-card')
    };

    // Auto-refresh interval (10 seconds)
    const REFRESH_INTERVAL = 10000;
    let refreshTimer = null;

    // Initialize
    init();

    function init() {
        setupTabs();
        refreshAll();
        fetchFlows();
        fetchTemplates();
        fetchLibraryFiles();
        startAutoRefresh();
        
        elements.refreshBtn.addEventListener('click', () => {
            const activeTab = document.querySelector('.tab-btn.active').dataset.tab;
            if (activeTab === 'tab-overview') refreshAll(true);
            else if (activeTab === 'tab-library') fetchLibraryFiles();
            else if (activeTab === 'tab-templates') fetchTemplates();
        });

        elements.rescanBtn.addEventListener('click', async () => {
            if (confirm('Are you sure you want to trigger a full library rescan?')) {
                try {
                    const res = await fetch('/api/fileflows/rescan', { method: 'POST' });
                    const data = await res.json();
                    alert(data.status === 'success' ? 'Rescan triggered!' : 'Failed to trigger rescan.');
                } catch (err) {
                    console.error('Rescan error:', err);
                }
            }
        });

        elements.triggerPipelineBtn.addEventListener('click', triggerPipeline);
        
        elements.igFetchBtn.addEventListener('click', fetchInstagramInfo);
        elements.igDownloadBtn.addEventListener('click', downloadInstagramMedia);
    }

    function setupTabs() {
        elements.tabs.forEach(btn => {
            btn.addEventListener('click', () => {
                const target = btn.dataset.tab;
                
                // Toggle buttons
                elements.tabs.forEach(b => b.classList.toggle('active', b === btn));
                
                // Toggle contents
                elements.tabContents.forEach(content => {
                    content.classList.toggle('active', content.id === target);
                });

                // Load data for specific tabs
                if (target === 'tab-library') fetchLibraryFiles();
                else if (target === 'tab-templates') fetchTemplates();
            });
        });
    }

    async function triggerPipeline() {
        const url = elements.pipelineUrl.value.trim();
        const flowUid = elements.flowSelect.value;

        if (!url || !flowUid) {
            showPipelineStatus('Please enter a URL and select a flow', 'error');
            return;
        }

        elements.triggerPipelineBtn.disabled = true;
        showPipelineStatus('Triggering pipeline...', 'info');

        try {
            const res = await fetch('/api/fileflows/trigger', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, flow_uid: flowUid })
            });
            const data = await res.json();
            
            if (data.status === 'success') {
                showPipelineStatus('✅ Pipeline executed successfully!', 'success');
                elements.pipelineUrl.value = '';
                setTimeout(() => refreshAll(true), 1500);
            } else {
                showPipelineStatus('❌ Pipeline failed: ' + (data.detail || 'Unknown error'), 'error');
            }
        } catch (err) {
            showPipelineStatus('❌ Connection error', 'error');
        } finally {
            elements.triggerPipelineBtn.disabled = false;
        }
    }

    function showPipelineStatus(msg, type) {
        elements.pipelineStatus.textContent = msg;
        elements.pipelineStatus.className = `pipeline-status ${type}`;
        elements.pipelineStatus.classList.remove('hidden');
        if (type === 'success') {
            setTimeout(() => elements.pipelineStatus.classList.add('hidden'), 5000);
        }
    }

    // --- INSTAGRAM FUNCTIONS ---

    async function fetchInstagramInfo() {
        const urlOrUsername = elements.igUrl.value.trim();
        if (!urlOrUsername) {
            showIgStatus('Please enter a URL or username', 'error');
            return;
        }

        let username = urlOrUsername;
        if (urlOrUsername.includes('instagram.com/')) {
            const parts = urlOrUsername.split('/');
            const index = parts.findIndex(p => p === 'p' || p === 'reels' || p === 'reel');
            if (index > -1) {
                // It's a post, not a profile. We can fetch media info.
                // For simplicity, let's just try to get the user from the profile URL if possible.
            } else {
                username = parts[parts.length - 1] || parts[parts.length - 2];
            }
        }

        showIgStatus('Fetching Instagram data...', 'info');
        elements.igFetchBtn.disabled = true;

        try {
            const res = await fetch(`/api/instagram/user/${username}`);
            if (!res.ok) throw new Error('User not found or API error');
            const data = await res.json();
            
            renderIgResult(data);
            showIgStatus('✅ Data fetched!', 'success');
        } catch (err) {
            showIgStatus('❌ Error: ' + err.message, 'error');
            elements.igResultCard.innerHTML = `<div class="empty-state">Failed to fetch data for ${username}</div>`;
        } finally {
            elements.igFetchBtn.disabled = false;
        }
    }

    async function downloadInstagramMedia() {
        const url = elements.igUrl.value.trim();
        if (!url || !url.includes('instagram.com/p/')) {
            showIgStatus('Please enter a valid Instagram post URL', 'error');
            return;
        }

        showIgStatus('Starting download...', 'info');
        elements.igDownloadBtn.disabled = true;

        try {
            const res = await fetch('/api/instagram/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            const data = await res.json();
            
            if (data.status === 'success') {
                showIgStatus('✅ Downloaded to ' + data.path, 'success');
            } else {
                showIgStatus('❌ Download failed', 'error');
            }
        } catch (err) {
            showIgStatus('❌ Connection error', 'error');
        } finally {
            elements.igDownloadBtn.disabled = false;
        }
    }

    function renderIgResult(user) {
        elements.igResultCard.innerHTML = `
            <div style="display: flex; flex-direction: column; gap: 1rem;">
                <div style="display: flex; align-items: center; gap: 1rem;">
                    <img src="${user.profile_pic_url}" style="width: 64px; height: 64px; border-radius: 50%; border: 2px solid var(--accent);">
                    <div>
                        <h4 style="margin: 0;">${user.full_name}</h4>
                        <span style="color: var(--text-dim); font-size: 0.8rem;">@${user.username}</span>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; text-align: center;">
                    <div class="glass" style="padding: 0.5rem;">
                        <div style="font-size: 0.7rem; color: var(--text-dim);">POSTS</div>
                        <div style="font-weight: 700;">${user.media_count}</div>
                    </div>
                    <div class="glass" style="padding: 0.5rem;">
                        <div style="font-size: 0.7rem; color: var(--text-dim);">FOLLOWERS</div>
                        <div style="font-weight: 700;">${formatNumber(user.follower_count)}</div>
                    </div>
                    <div class="glass" style="padding: 0.5rem;">
                        <div style="font-size: 0.7rem; color: var(--text-dim);">FOLLOWING</div>
                        <div style="font-weight: 700;">${formatNumber(user.following_count)}</div>
                    </div>
                </div>
                <div class="glass" style="padding: 1rem; font-size: 0.85rem;">
                    ${user.biography || 'No biography'}
                </div>
            </div>
        `;
    }

    function showIgStatus(msg, type) {
        elements.igStatus.textContent = msg;
        elements.igStatus.className = `pipeline-status ${type}`;
        elements.igStatus.classList.remove('hidden');
    }

    function formatNumber(num) {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num;
    }

    async function fetchFlows() {
        try {
            const res = await fetch('/api/fileflows/flows');
            const data = await res.json();
            
            if (!data || data.length === 0) {
                elements.flowSelect.innerHTML = '<option value="">No flows found</option>';
                return;
            }

            // Group flows by type if available
            const groups = {};
            data.forEach(flow => {
                const fType = flow.Type !== undefined ? flow.Type : flow.type;
                const typeLabel = fType === 1 ? 'Video' : fType === 2 ? 'Audio' : fType === 3 ? 'Image' : 'Other';
                if (!groups[typeLabel]) groups[typeLabel] = [];
                groups[typeLabel].push(flow);
            });

            let html = '<option value="">-- Select Automation Flow --</option>';
            for (const [type, flows] of Object.entries(groups)) {
                html += `<optgroup label="${type} Flows">`;
                html += flows.map(flow => {
                    const uid = flow.Uid || flow.uid;
                    const name = flow.Name || flow.name;
                    return `<option value="${uid}">${name}</option>`;
                }).join('');
                html += `</optgroup>`;
            }
            elements.flowSelect.innerHTML = html;
        } catch (err) {
            console.error('Flows error:', err);
            elements.flowSelect.innerHTML = '<option value="">Error loading flows</option>';
        }
    }

    async function fetchTemplates() {
        try {
            const res = await fetch('/api/fileflows/flow-templates');
            const data = await res.json();
            
            elements.templatesGrid.innerHTML = data.map(tpl => `
                <div class="file-card glass">
                    <div class="file-icon">📋</div>
                    <div class="file-info">
                        <span class="file-name">${tpl.Name || tpl.name}</span>
                        <span class="file-meta">${tpl.Description || 'No description'}</span>
                    </div>
                </div>
            `).join('') || '<div class="empty-state">No templates found</div>';
        } catch (err) {
            console.error('Templates error:', err);
        }
    }

    async function fetchLibraryFiles() {
        try {
            const res = await fetch('/api/fileflows/library-files?page=0&pageSize=50');
            const data = await res.json();
            
            elements.libraryFilesBody.innerHTML = data.map(file => `
                <tr>
                    <td><div class="file-cell" title="${file.Name}">${file.Name.split('/').pop()}</div></td>
                    <td><span class="status-tag status-${file.Status}">${getStatusLabel(file.Status)}</span></td>
                    <td>${file.LibraryName}</td>
                    <td>${formatSize(file.FinalSize || file.OriginalSize)}</td>
                    <td>${formatDate(file.DateCreated)}</td>
                </tr>
            `).join('') || '<tr><td colspan="5" class="empty-state">No library files found</td></tr>';
        } catch (err) {
            console.error('Library error:', err);
        }
    }

    function getStatusLabel(status) {
        const labels = {
            0: 'Unprocessed',
            1: 'Processed',
            2: 'Processing',
            3: 'Failed',
            4: 'Duplicate',
            5: 'Mapping Error'
        };
        return labels[status] || 'Unknown';
    }

    function formatDate(dateStr) {
        if (!dateStr) return 'N/A';
        const date = new Date(dateStr);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    async function refreshAll(manual = false) {
        if (manual) elements.loadingOverlay.classList.remove('hidden');
        
        try {
            await Promise.all([
                fetchSystemInfo(),
                fetchExecutingTasks(),
                fetchUpcomingTasks(),
                fetchNodes(),
                fetchLibraryStatus(),
                fetchRecentFiles()
            ]);
            elements.statStatus.textContent = 'ONLINE';
            elements.statStatus.className = 'value status-online';
        } catch (err) {
            console.error('Refresh error:', err);
            elements.statStatus.textContent = 'OFFLINE';
            elements.statStatus.className = 'value status-offline';
        } finally {
            if (manual) elements.loadingOverlay.classList.add('hidden');
        }
    }

    function startAutoRefresh() {
        if (refreshTimer) clearInterval(refreshTimer);
        refreshTimer = setInterval(refreshAll, REFRESH_INTERVAL);
    }

    async function fetchSystemInfo() {
        const res = await fetch('/api/fileflows/info');
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        
        elements.statCpu.textContent = `${Math.round(data.CpuUsage || 0)}%`;
        elements.statRam.textContent = `${(data.MemoryUsage / 1024 / 1024 / 1024).toFixed(1)}GB`;
    }

    async function fetchExecutingTasks() {
        const res = await fetch('/api/fileflows/executing');
        const data = await res.json();
        
        elements.activeCount.textContent = data.length || 0;
        
        if (!data || data.length === 0) {
            elements.activeList.innerHTML = '<div class="empty-state">No files currently processing</div>';
            return;
        }

        elements.activeList.innerHTML = data.map(task => `
            <div class="task-item">
                <div class="task-info">
                    <span class="task-name" title="${task.RelativePath}">${task.RelativePath.split('/').pop()}</span>
                    <span class="task-step">${task.CurrentPartName || 'Processing...'}</span>
                </div>
                <div class="progress-container">
                    <div class="progress-bar" style="width: ${task.WorkingPercent || 0}%"></div>
                    <span class="progress-text">${Math.round(task.WorkingPercent || 0)}%</span>
                </div>
            </div>
        `).join('');
    }

    async function fetchUpcomingTasks() {
        const res = await fetch('/api/fileflows/upcoming');
        const data = await res.json();
        
        elements.upcomingCount.textContent = data.length || 0;
        
        if (!data || data.length === 0) {
            elements.upcomingList.innerHTML = '<div class="empty-state">Queue is empty</div>';
            return;
        }

        elements.upcomingList.innerHTML = data.map(task => `
            <div class="task-item compact">
                <span class="task-name" title="${task.Name}">${task.Name.split('/').pop()}</span>
            </div>
        `).join('');
    }

    async function fetchNodes() {
        const res = await fetch('/api/fileflows/nodes');
        const data = await res.json();
        
        elements.nodesContainer.innerHTML = data.map(node => `
            <div class="node-item">
                <span class="status-dot ${node.Status === 1 ? 'online' : 'offline'}"></span>
                <span class="node-name">${node.Name}</span>
            </div>
        `).join('') || 'No nodes configured';
    }

    async function fetchLibraryStatus() {
        const res = await fetch('/api/fileflows/status');
        const data = await res.json();
        
        // Data is usually an array of status objects
        const total = data.reduce((acc, s) => acc + s.Count, 0);
        const processed = data.find(s => s.Status === 1)?.Count || 0;
        
        elements.libraryStats.innerHTML = `
            <div class="stat-mini">
                <span class="label">Total Files</span>
                <span class="value">${total}</span>
            </div>
            <div class="stat-mini">
                <span class="label">Processed</span>
                <span class="value">${processed}</span>
            </div>
        `;
    }

    async function fetchRecentFiles() {
        const res = await fetch('/api/fileflows/recently-finished');
        const data = await res.json();
        
        if (!data || data.length === 0) {
            elements.recentList.innerHTML = '<div class="empty-state">No recently finished files</div>';
            return;
        }

        elements.recentList.innerHTML = data.map(file => `
            <div class="file-card glass">
                <div class="file-icon">${getFileIcon(file.Name)}</div>
                <div class="file-info">
                    <span class="file-name" title="${file.Name}">${file.Name.split('/').pop()}</span>
                    <span class="file-meta">${file.LibraryName} • ${formatSize(file.FinalSize)}</span>
                </div>
            </div>
        `).join('');
    }

    function getFileIcon(name) {
        const ext = name.split('.').pop().toLowerCase();
        if (['mp4', 'mkv', 'avi', 'mov'].includes(ext)) return '🎬';
        if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) return '🖼️';
        if (['mp3', 'flac', 'wav'].includes(ext)) return '🎵';
        return '📄';
    }

    function formatSize(bytes) {
        if (!bytes) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
});
