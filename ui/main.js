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
        dlThumbBtn: document.getElementById('dl-thumb-btn'),
        dlVideoBtn: document.getElementById('dl-video-btn')
    };

    let currentPostData = null;

    // Event Listeners
    elements.scrapePostBtn.addEventListener('click', scrapeSinglePost);
    elements.postUrlInput.addEventListener('keypress', (e) => e.key === 'Enter' && scrapeSinglePost());

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
            if (!response.ok) throw new Error('Proxy returned error');
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
            alert('Download failed. This can happen if Instagram blocks the request.');
        } finally {
            elements.loading.classList.add('hidden');
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
