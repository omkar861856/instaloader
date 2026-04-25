document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const elements = {
        postUrlInput: document.getElementById('post-url-input'),
        scrapePostBtn: document.getElementById('scrape-post-btn'),
        postPreviewCard: document.getElementById('post-preview-card'),
        loading: document.getElementById('loading'),
        errorMsg: document.getElementById('error-msg'),
        
        // Preview details
        previewMedia: document.getElementById('preview-media'),
        previewUser: document.getElementById('preview-user'),
        previewStats: document.getElementById('preview-stats'),
        previewCaption: document.getElementById('preview-caption'),
        saveToVaultBtn: document.getElementById('save-to-vault-btn'),
        dlThumbBtn: document.getElementById('dl-thumb-btn'),
        dlVideoBtn: document.getElementById('dl-video-btn'),

        // Vault
        vaultGrid: document.getElementById('vault-grid'),
        refreshVaultBtn: document.getElementById('refresh-vault-btn')
    };

    let lastScrapedShortcode = '';
    let currentPostData = null;

    // Initial load
    fetchVault();

    // Event Listeners
    elements.scrapePostBtn.addEventListener('click', scrapeSinglePost);
    elements.postUrlInput.addEventListener('keypress', (e) => e.key === 'Enter' && scrapeSinglePost());
    elements.refreshVaultBtn.addEventListener('click', fetchVault);
    elements.saveToVaultBtn.addEventListener('click', () => saveToVault(lastScrapedShortcode));

    // New Download Logic
    elements.dlThumbBtn.addEventListener('click', () => {
        if (!currentPostData) return;
        const filename = `thumb_${currentPostData.owner_username}_${currentPostData.shortcode}`;
        const proxyUrl = `/api/proxy/download?url=${encodeURIComponent(currentPostData.display_url)}&filename=${filename}&is_video=false`;
        forceDownload(proxyUrl, filename);
    });

    elements.dlVideoBtn.addEventListener('click', () => {
        if (!currentPostData || !currentPostData.video_url) return;
        const filename = `reel_${currentPostData.owner_username}_${currentPostData.shortcode}`;
        const proxyUrl = `/api/proxy/download?url=${encodeURIComponent(currentPostData.video_url)}&filename=${filename}&is_video=true`;
        forceDownload(proxyUrl, filename);
    });

    async function scrapeSinglePost() {
        const url = elements.postUrlInput.value.trim();
        if (!url) return;

        showError(null);
        elements.postPreviewCard.classList.add('hidden');
        elements.loading.classList.remove('hidden');

        try {
            const response = await fetch(`/api/scrape/post?url=${encodeURIComponent(url)}`);
            const post = await response.json();

            if (!response.ok) throw new Error(post.detail || 'Failed to scrape post');

            lastScrapedShortcode = post.shortcode;
            currentPostData = post;
            updatePreviewUI(post);
            
            elements.loading.classList.add('hidden');
            elements.postPreviewCard.classList.remove('hidden');
        } catch (err) {
            elements.loading.classList.add('hidden');
            showError(err.message);
        }
    }

    function updatePreviewUI(post) {
        elements.previewUser.textContent = `@${post.owner_username}`;
        elements.previewStats.textContent = `❤️ ${post.likes.toLocaleString()} | 💬 ${post.comments.toLocaleString()}`;
        elements.previewCaption.textContent = post.caption || 'No caption available.';
        
        // Media rendering
        elements.previewMedia.innerHTML = post.is_video 
            ? `<video src="${post.video_url || post.display_url}" controls referrerpolicy="no-referrer"></video>`
            : `<img src="${post.display_url}" alt="Post Preview" referrerpolicy="no-referrer">`;

        // Toggle Video Button visibility
        elements.dlVideoBtn.style.display = post.is_video ? 'inline-block' : 'none';
    }

    async function forceDownload(url, filename) {
        elements.loading.classList.remove('hidden');
        try {
            const response = await fetch(url);
            const blob = await response.blob();
            const blobUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(blobUrl);
            a.remove();
        } catch (err) {
            alert('Download failed. Try saving to Vault first.');
        } finally {
            elements.loading.classList.add('hidden');
        }
    }

    async function saveToVault(shortcode) {
        if (!shortcode) return;
        try {
            const response = await fetch(`/api/download/post/${shortcode}`, { method: 'POST' });
            const data = await response.json();
            alert(data.message || 'Saved to your Vault!');
            fetchVault();
        } catch (err) {
            alert('Failed to save to vault');
        }
    }

    async function fetchVault() {
        try {
            const response = await fetch('/api/downloads/all');
            const files = await response.json();

            if (!Array.isArray(files) || files.length === 0) {
                elements.vaultGrid.innerHTML = '<p class="empty-vault">No downloads yet.</p>';
                return;
            }

            elements.vaultGrid.innerHTML = '';
            files.slice(0, 10).forEach(file => {
                const item = document.createElement('div');
                item.className = 'vault-item';
                item.innerHTML = `
                    ${file.type === 'video' 
                        ? `<video src="${file.url}" muted></video>` 
                        : `<img src="${file.url}" alt="${file.name}">`
                    }
                    <div class="vault-info">
                        <a href="${file.url}" download="${file.name}">Download</a>
                    </div>
                `;
                elements.vaultGrid.appendChild(item);
            });
        } catch (err) {
            console.error('Failed to fetch vault:', err);
        }
    }

    function showError(msg) {
        if (msg) {
            elements.errorMsg.textContent = msg;
            elements.errorMsg.classList.remove('hidden');
        } else {
            elements.errorMsg.classList.add('hidden');
        }
    }
});
