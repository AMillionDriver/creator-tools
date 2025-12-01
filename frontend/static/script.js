document.addEventListener('DOMContentLoaded', () => {
    const preloader = document.getElementById('preloader');
    const mainContainer = document.querySelector('.main-container');

    const urlInput = document.getElementById('url-input');
    const getInfoBtn = document.getElementById('download-btn');
    const loader = document.getElementById('loader');
    const errorMessage = document.getElementById('error-message');
    const resultsSection = document.getElementById('results-section');
    const thumbnail = document.getElementById('thumbnail');
    const videoTitle = document.getElementById('video-title');
    const videoAuthor = document.getElementById('video-author');
    const formatLinks = document.getElementById('format-links');
    
    // Stats Elements
    const statRevenue = document.getElementById('stat-revenue');
    const statCpm = document.getElementById('stat-cpm');
    const statViews = document.getElementById('stat-views');
    const statLikes = document.getElementById('stat-likes');
    const statComments = document.getElementById('stat-comments');
    // Engagement element removed from main grid, moved to chart or insights if needed
    // Or we can keep it if we adjust grid.
    // Let's assume user removed engagement card or we handle it. 
    // Actually, in previous step index.html, I replaced the whole grid structure, so engagement card is gone from HTML.
    // Let's just focus on Revenue, Views, Likes, Comments.

    let myChart = null; // Chart instance
    let ageChartInstance = null;
    let genderChartInstance = null;

    const API_BASE = '/api'; // In Vercel, this will be proxied to Backend
    let csrfToken = null;
    let recaptchaWidgetId = null;

    // Initialize
    initApp();

    async function initApp() {
        try {
            // Fetch Config (CSRF + Site Key)
            const res = await fetch(`${API_BASE}/handshake`);
            if (!res.ok) throw new Error('Failed to connect to backend');
            
            const config = await res.json();
            csrfToken = config.csrf_token;
            
            // Initialize ReCAPTCHA
            if (config.recaptcha_site_key && window.grecaptcha) {
                 grecaptcha.ready(function() {
                    try {
                        recaptchaWidgetId = grecaptcha.render('recaptcha-container', {
                            'sitekey': config.recaptcha_site_key
                        });
                    } catch(e) { console.log("Captcha render error (maybe already rendered):", e); }
                });
            }

            // Hide Preloader
            if (preloader) preloader.style.display = 'none';
            if (mainContainer) mainContainer.style.display = 'block';

        } catch (err) {
            console.error("Init Error:", err);
            showError("Could not connect to server. Please try again later.");
             // Still hide preloader so user sees error
            if (preloader) preloader.style.display = 'none';
        }
    }

    getInfoBtn.textContent = 'Get Video Info';
    getInfoBtn.addEventListener('click', handleGetInfo);
    urlInput.addEventListener('keyup', (e) => { if (e.key === 'Enter') handleGetInfo(); });

    async function handleGetInfo() {
        const url = urlInput.value.trim();
        if (!url) return showError('Please paste a URL first.');
        
        // Refetch CSRF if missing (expired?) - simplistic approach
        if (!csrfToken) await initApp();

        resetUI();
        loader.style.display = 'block';

        try {
            const res = await fetch(`${API_BASE}/download`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ url })
            });
            const data = await res.json();

            if (!res.ok) throw new Error(data.error || 'Failed to fetch info');

            displayResults(data, url);
        } catch (err) {
            showError(err.message);
        } finally {
            loader.style.display = 'none';
        }
    }

    function formatNumber(num) {
        if (!num) return '0';
        return new Intl.NumberFormat('en-US', { notation: "compact", compactDisplay: "short" }).format(num);
    }

    function displayResults(data, url) {
        if (!data.formats || data.formats.length === 0) return showError('No formats found.');

        videoTitle.textContent = data.title;
        videoAuthor.textContent = data.uploader || 'Unknown Creator';
        thumbnail.src = data.thumbnail;
        
        // Populate Stats
        const views = data.view_count || 0;
        const likes = data.like_count || 0;
        const comments = data.comment_count || 0;
        
        statViews.textContent = formatNumber(views);
        statLikes.textContent = formatNumber(likes);
        statComments.textContent = formatNumber(comments);
        
        // --- Revenue Calculation ---
        const category = (data.categories && data.categories.length > 0) ? data.categories[0] : 'General';
        let cpm = 2.50; // Default CPM ($)

        const catLower = category.toLowerCase();
        if (catLower.includes('finance') || catLower.includes('money') || catLower.includes('business') || catLower.includes('tech')) {
            cpm = 12.00; // High CPM
        } else if (catLower.includes('education') || catLower.includes('news') || catLower.includes('auto')) {
            cpm = 6.50;  // Mid-High CPM
        } else if (catLower.includes('gaming') || catLower.includes('game')) {
            cpm = 1.50;  // Low CPM
        } else if (catLower.includes('music') || catLower.includes('dance')) {
            cpm = 1.20;  // Lowest CPM
        } else if (catLower.includes('beauty') || catLower.includes('vlog') || catLower.includes('entertainment')) {
            cpm = 3.00;  // Average
        }

        // Calculate Revenue: (Views / 1000) * CPM
        let estimatedRevenue = 0;
        if (views > 0) {
            estimatedRevenue = (views / 1000) * cpm;
        }

        // Format Currency
        const currencyFormatter = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
        statRevenue.textContent = currencyFormatter.format(estimatedRevenue);
        statCpm.textContent = `CPM: ${cpm.toFixed(2)}`;

        // Render Charts
        renderChart(views, likes, comments);
        
        // Generate Audience Insights based on Category + Metrics
        generateAudienceInsights(category, data.title, data.duration, views, likes, comments);

        formatLinks.innerHTML = '';

        data.formats.forEach(format => {
            const div = document.createElement('div');
            div.className = 'format-item';
            
            // Format text description
            let infoText = format.ext.toUpperCase();
            if (format.resolution) infoText += ` - ${format.resolution}`;
            if (format.note) infoText += ` (${format.note})`;

            const label = document.createElement('span');
            label.className = 'format-label';
            label.textContent = infoText;

            const btn = document.createElement('button');
            btn.className = 'download-format-btn';
            btn.textContent = 'Download';
            
            // Progress Bar Container
            const progressContainer = document.createElement('div');
            progressContainer.className = 'progress-container';
            progressContainer.style.display = 'none';
            progressContainer.style.marginTop = '5px';
            progressContainer.style.width = '100%';
            progressContainer.style.backgroundColor = '#e0e0e0';
            progressContainer.style.borderRadius = '4px';
            
            const progressBar = document.createElement('div');
            progressBar.style.width = '0%';
            progressBar.style.height = '10px';
            progressBar.style.backgroundColor = '#4caf50'; // Green
            progressBar.style.borderRadius = '4px';
            progressBar.style.transition = 'width 0.3s';
            
            progressContainer.appendChild(progressBar);

            const statusText = document.createElement('span');
            statusText.className = 'download-status';
            statusText.style.fontSize = '0.8rem';
            statusText.style.marginLeft = '10px';

            btn.addEventListener('click', () => {
                startBackendDownload(url, format.format_id, btn, statusText, progressBar, progressContainer);
            });

            div.appendChild(label);
            div.appendChild(btn);
            div.appendChild(statusText);
            div.appendChild(progressContainer);
            formatLinks.appendChild(div);
        });

        resultsSection.style.display = 'block';
    }
    
    function renderChart(views, likes, comments) {
        const ctx = document.getElementById('analyticsChart').getContext('2d');
        if (myChart) myChart.destroy();
        
        myChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Likes', 'Comments'],
                datasets: [{
                    label: 'Count',
                    data: [likes, comments],
                    backgroundColor: ['rgba(46, 213, 115, 0.6)', 'rgba(67, 97, 238, 0.6)'],
                    borderColor: ['rgba(46, 213, 115, 1)', 'rgba(67, 97, 238, 1)'],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, grid: { color: 'rgba(255, 255, 255, 0.1)' }, ticks: { color: '#b0b0b0' } },
                    x: { grid: { display: false }, ticks: { color: '#b0b0b0' } }
                },
                plugins: { legend: { display: false } }
            }
        });
    }

    function generateAudienceInsights(category, title, duration, views, likes, comments) {
        // 1. Base Profile (Category Based)
        // Format Age: [13-17, 18-24, 25-34, 35+]
        // Format Gender: [Male, Female]
        
        let ageWeights = [25, 35, 25, 15]; // Default Balanced
        let genderWeights = [50, 50];      // Default Balanced
        
        const cat = category.toLowerCase();
        const tit = title.toLowerCase();
        
        // --- Base Category Logic ---
        if (cat.includes('gaming') || cat.includes('game')) {
            ageWeights = [35, 40, 20, 5];
            genderWeights = [80, 20];
        } else if (cat.includes('beauty') || cat.includes('style') || cat.includes('makeup')) {
            ageWeights = [20, 45, 25, 10];
            genderWeights = [10, 90];
        } else if (cat.includes('tech') || cat.includes('science') || cat.includes('gadget')) {
            ageWeights = [15, 35, 40, 10];
            genderWeights = [85, 15];
        } else if (cat.includes('news') || cat.includes('politics') || cat.includes('finance')) {
            ageWeights = [5, 15, 35, 45];
            genderWeights = [60, 40];
        } else if (cat.includes('kids') || cat.includes('cartoon') || cat.includes('animation')) {
            ageWeights = [60, 20, 10, 10]; // Parents viewing for kids count as kids demographic usually
            genderWeights = [50, 50];
        } else if (cat.includes('music')) {
             ageWeights = [20, 30, 30, 20];
        }

        // --- 2. Duration Modifier (Attention Span Logic) ---
        // Short videos (< 3 mins) attract younger audiences (TikTok Gen)
        // Long videos (> 15 mins) attract older audiences (Podcast/Docu fans)
        if (duration > 0) {
            if (duration < 180) { // < 3 mins
                ageWeights[0] += 15; // Boost 13-17
                ageWeights[1] += 10; // Boost 18-24
                ageWeights[3] -= 10; // Reduce 35+
            } else if (duration > 900) { // > 15 mins
                ageWeights[0] -= 10;
                ageWeights[2] += 10; // Boost 25-34
                ageWeights[3] += 10; // Boost 35+
            }
        }

        // --- 3. Engagement Modifier (Passion Logic) ---
        // High engagement rate usually means younger, more active community (Gen Z)
        let engagementRate = 0;
        if (views > 0) engagementRate = ((likes + comments) / views);
        
        if (engagementRate > 0.05) { // > 5% is very high
            ageWeights[0] += 10; 
            ageWeights[1] += 10;
        } else if (engagementRate < 0.01) { // < 1% is passive
            ageWeights[2] += 5;
            ageWeights[3] += 10;
        }

        // --- 4. Title Keyword Modifier (Content Specifics) ---
        if (tit.includes('tutorial') || tit.includes('how to') || tit.includes('guide')) {
             // Tutorials are slightly more male dominated or older
             ageWeights[2] += 5;
             genderWeights[0] += 5;
        } else if (tit.includes('asmr') || tit.includes('routine') || tit.includes('haul')) {
             genderWeights[1] += 15; // Shift Female
        } else if (tit.includes('football') || tit.includes('soccer') || tit.includes('fight') || tit.includes('boxing')) {
             genderWeights[0] += 20; // Shift Male
        }

        // --- 5. Normalization (Make sure sums to 100) ---
        const normalize = (arr) => {
            const sum = arr.reduce((a, b) => a + b, 0);
            return arr.map(val => Math.round((val / sum) * 100));
        };

        // Apply Softmax-like normalization logic simply (clamping negative values first)
        ageWeights = ageWeights.map(v => Math.max(v, 1)); // Ensure no negative
        genderWeights = genderWeights.map(v => Math.max(v, 1));

        ageWeights = normalize(ageWeights);
        genderWeights = normalize(genderWeights);


        // Render Age Chart
        const ctxAge = document.getElementById('ageChart').getContext('2d');
        if (ageChartInstance) ageChartInstance.destroy();

        ageChartInstance = new Chart(ctxAge, {
            type: 'bar',
            data: {
                labels: ['13-17', '18-24', '25-34', '35+'],
                datasets: [{
                    label: '% Est.',
                    data: ageWeights,
                    backgroundColor: [
                        'rgba(255, 159, 67, 0.8)',
                        'rgba(254, 202, 87, 0.8)',
                        'rgba(255, 107, 107, 0.8)',
                        'rgba(84, 160, 255, 0.8)' 
                    ],
                    borderRadius: 4,
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { display: false, max: 100 },
                    x: { ticks: { color: '#b0b0b0', font: {size: 10} }, grid: {display: false} }
                },
                plugins: { 
                    legend: { display: false },
                    tooltip: { callbacks: { label: (c) => `${c.raw}% (Est)` } }
                }
            }
        });

        // Render Gender Chart
        const ctxGender = document.getElementById('genderChart').getContext('2d');
        if (genderChartInstance) genderChartInstance.destroy();

        genderChartInstance = new Chart(ctxGender, {
            type: 'doughnut',
            data: {
                labels: ['Male', 'Female'],
                datasets: [{
                    data: genderWeights,
                    backgroundColor: ['#54a0ff', '#ff9ff3'],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: { 
                    legend: { position: 'right', labels: { color: '#fff', font: {size: 11}, boxWidth: 10, padding: 10 } } 
                }
            }
        });
    }

    async function startBackendDownload(url, formatId, btn, statusText, progressBar, progressContainer) {
        // Check Captcha
        let captchaToken = null;
        if (typeof grecaptcha !== 'undefined') {
            captchaToken = grecaptcha.getResponse();
            if (!captchaToken) {
                alert("Please check the 'I'm not a robot' box.");
                return;
            }
        }

        btn.disabled = true;
        statusText.textContent = 'Starting...';
        progressContainer.style.display = 'block'; // Show progress bar
        progressBar.style.width = '0%';

        try {
            const res = await fetch(`${API_BASE}/process-video`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ 
                    url, 
                    format_id: formatId,
                    'g-recaptcha-response': captchaToken 
                })
            });
            const data = await res.json();

            if (!res.ok) throw new Error(data.error);

            // Start polling
            pollStatus(data.task_id, btn, statusText, progressBar);

        } catch (err) {
            statusText.textContent = 'Error: ' + err.message;
            btn.disabled = false;
        }
    }

    function pollStatus(taskId, btn, statusText, progressBar) {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE}/status/${taskId}`);
                if (!res.ok) {
                    clearInterval(interval);
                    throw new Error('Connection lost');
                }
                const data = await res.json();

                // Update Progress Bar
                if (data.percentage) {
                    progressBar.style.width = `${data.percentage}%`;
                    statusText.textContent = `${data.percentage}% - ${data.status}`;
                } else {
                    statusText.textContent = data.status;
                }

                if (data.status === 'Completed') {
                    clearInterval(interval);
                    statusText.innerHTML = `<a href="${data.download_link}" class="download-ready" download>Save File</a>`;
                    btn.textContent = 'Done';
                    // Keep button disabled or enable if you want allow re-download logic
                } else if (data.status === 'Failed') {
                    clearInterval(interval);
                    statusText.textContent = 'Failed: ' + data.message;
                    progressBar.style.backgroundColor = '#f44336'; // Red
                    btn.disabled = false;
                }

            } catch (err) {
                clearInterval(interval);
                statusText.textContent = 'Error polling: ' + err.message;
                btn.disabled = false;
            }
        }, 1000); // Poll every 1 second
    }

    function resetUI() {
        resultsSection.style.display = 'none';
        errorMessage.style.display = 'none';
        formatLinks.innerHTML = '';
    }

    function showError(msg) {
        errorMessage.textContent = msg;
        errorMessage.style.display = 'block';
    }
});
