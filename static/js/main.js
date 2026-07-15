// ==================== 全局变量 ====================

let currentTaskId = null;
let websocket = null;
let subtitles = [];

// ==================== 页面初始化 ====================

document.addEventListener('DOMContentLoaded', () => {
    initUploadArea();
    checkSystemStatus();
});

// ==================== 上传功能 ====================

function initUploadArea() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');

    // 点击上传
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });

    // 文件选择
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    // 拖拽上传
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');

        if (e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });
}

async function handleFile(file) {
    // 验证文件类型
    const allowedTypes = [
        'video/mp4', 'video/avi', 'video/x-matroska',
        'video/quicktime', 'video/x-ms-wmv', 'video/x-flv',
        'video/webm'
    ];

    const allowedExtensions = [
        '.mp4', '.avi', '.mkv', '.mov',
        '.wmv', '.flv', '.webm', '.m4v'
    ];

    const extension = '.' + file.name.split('.').pop().toLowerCase();

    if (!allowedExtensions.includes(extension)) {
        showError('不支持的文件格式，请上传视频文件');
        return;
    }

    // 验证文件大小 (2GB)
    if (file.size > 2 * 1024 * 1024 * 1024) {
        showError('文件大小超过限制 (最大 2GB)');
        return;
    }

    // 上传文件
    showLoading('正在上传文件...');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '上传失败');
        }

        const result = await response.json();

        // 更新界面
        currentTaskId = result.task_id;
        document.getElementById('fileName').textContent = result.filename;
        document.getElementById('taskId').textContent = result.task_id;
        updateStatus('pending', '等待处理');

        // 显示任务区域，隐藏上传区域
        document.getElementById('uploadSection').style.display = 'none';
        document.getElementById('taskSection').style.display = 'block';

        hideLoading();

    } catch (error) {
        hideLoading();
        showError(error.message);
    }
}

function resetUpload() {
    currentTaskId = null;
    subtitles = [];

    // 重置界面
    document.getElementById('uploadSection').style.display = 'block';
    document.getElementById('taskSection').style.display = 'none';
    document.getElementById('progressSection').style.display = 'none';
    document.getElementById('resultSection').style.display = 'none';
    document.getElementById('fileInput').value = '';

    // 关闭 WebSocket
    if (websocket) {
        websocket.close();
        websocket = null;
    }
}

// ==================== 处理视频 ====================

async function startProcessing() {
    if (!currentTaskId) {
        showError('请先上传视频文件');
        return;
    }

    const processBtn = document.getElementById('processBtn');
    processBtn.disabled = true;
    processBtn.textContent = '⏳ 处理中...';

    // 显示进度区域
    document.getElementById('progressSection').style.display = 'block';

    // 连接 WebSocket
    connectWebSocket(currentTaskId);

    try {
        const response = await fetch(`/api/process/${currentTaskId}`, {
            method: 'POST'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '处理失败');
        }

        // 开始轮询状态
        pollStatus(currentTaskId);

    } catch (error) {
        showError(error.message);
        processBtn.disabled = false;
        processBtn.textContent = '🚀 开始生成字幕';
    }
}

// 轮询任务状态
async function pollStatus(taskId) {
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${taskId}`);
            const data = await response.json();

            // 更新进度
            if (data.progress !== undefined) {
                document.getElementById('progressBar').style.width = `${data.progress}%`;
                document.getElementById('progressText').textContent = data.message;
            }

            updateStatus(data.status, data.message);

            // 处理完成
            if (data.status === 'completed' && data.segments) {
                clearInterval(pollInterval);
                subtitles = data.segments;
                showResults(data.segments);
            }

            // 处理失败
            if (data.status === 'failed') {
                clearInterval(pollInterval);
                showError(data.error || data.message);
                document.getElementById('processBtn').disabled = false;
                document.getElementById('processBtn').textContent = '🚀 开始生成字幕';
            }
        } catch (error) {
            console.error('轮询状态失败:', error);
        }
    }, 1000); // 每秒轮询一次
}

// ==================== WebSocket 连接 ====================

function connectWebSocket(taskId) {
    // 关闭现有连接
    if (websocket) {
        websocket.close();
    }

    // 建立新连接
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    websocket = new WebSocket(`${protocol}//${window.location.host}/ws/${taskId}`);

    websocket.onopen = () => {
        console.log('WebSocket 连接已建立');
    };

    websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleStatusUpdate(data);
    };

    websocket.onerror = (error) => {
        console.error('WebSocket 错误:', error);
    };

    websocket.onclose = () => {
        console.log('WebSocket 连接已关闭');
    };
}

function handleStatusUpdate(data) {
    // 更新状态
    updateStatus(data.status, data.message);

    // 更新进度条
    if (data.progress !== undefined) {
        document.getElementById('progressBar').style.width = `${data.progress}%`;
        document.getElementById('progressText').textContent = data.message;
    }

    // 处理完成
    if (data.status === 'completed' && data.segments) {
        subtitles = data.segments;
        showResults(data.segments);
    }

    // 处理失败
    if (data.status === 'failed') {
        showError(data.error || data.message);
        document.getElementById('processBtn').disabled = false;
        document.getElementById('processBtn').textContent = '🚀 开始生成字幕';
    }
}

// ==================== 状态更新 ====================

function updateStatus(status, message) {
    const statusElement = document.getElementById('taskStatus');
    statusElement.textContent = message;
    statusElement.className = `status-badge ${status}`;
}

async function checkSystemStatus() {
    try {
        const response = await fetch('/api/info');
        const info = await response.json();

        // Whisper 状态
        const whisperStatus = document.getElementById('whisperStatus');
        if (info.whisper.gpu_available) {
            whisperStatus.textContent = `${info.whisper.model} (GPU)`;
            whisperStatus.className = 'ok';
        } else {
            whisperStatus.textContent = `${info.whisper.model} (CPU)`;
            whisperStatus.className = 'ok';
        }

        // Ollama 状态
        const ollamaStatus = document.getElementById('ollamaStatus');
        ollamaStatus.textContent = info.ollama.model;
        ollamaStatus.className = 'ok';

        // GPU 状态
        const gpuStatus = document.getElementById('gpuStatus');
        if (info.whisper.gpu_available) {
            gpuStatus.textContent = info.whisper.gpu_name || '可用';
            gpuStatus.className = 'ok';
        } else {
            gpuStatus.textContent = '不可用';
            gpuStatus.className = 'error';
        }

    } catch (error) {
        console.error('获取系统信息失败:', error);
        document.getElementById('whisperStatus').textContent = '未连接';
        document.getElementById('ollamaStatus').textContent = '未连接';
        document.getElementById('gpuStatus').textContent = '未知';
    }
}

// ==================== 结果显示 ====================

function showResults(segments) {
    document.getElementById('resultSection').style.display = 'block';
    document.getElementById('processBtn').disabled = false;
    document.getElementById('processBtn').textContent = '🚀 重新生成';

    const tbody = document.getElementById('subtitleBody');
    tbody.innerHTML = '';

    segments.forEach((seg, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${formatTime(seg.start)} → ${formatTime(seg.end)}</td>
            <td>${escapeHtml(seg.text)}</td>
        `;
        tbody.appendChild(row);
    });
}

function formatTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);

    return `${padZero(h)}:${padZero(m)}:${padZero(s)}.${padZero(ms, 3)}`;
}

function padZero(num, length = 2) {
    return String(num).padStart(length, '0');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== 翻译功能 ====================

async function translateSubtitles() {
    if (!currentTaskId) {
        showError('没有可翻译的字幕');
        return;
    }

    const sourceLang = document.getElementById('sourceLang').value;
    const targetLang = document.getElementById('targetLang').value;
    const optimize = document.getElementById('optimizeCheck').checked;

    if (sourceLang === targetLang) {
        showError('源语言和目标语言不能相同');
        return;
    }

    showLoading('正在翻译字幕...');

    try {
        const response = await fetch('/api/translate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                task_id: currentTaskId,
                source_lang: sourceLang,
                target_lang: targetLang,
                optimize: optimize
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '翻译失败');
        }

        const result = await response.json();

        // 更新字幕显示
        subtitles = result.segments;
        showResults(result.segments);

        hideLoading();
        showSuccess('翻译完成');

    } catch (error) {
        hideLoading();
        showError(error.message);
    }
}

// ==================== 下载功能 ====================

async function downloadSubtitle() {
    if (!currentTaskId) {
        showError('没有可下载的字幕');
        return;
    }

    const format = document.getElementById('downloadFormat').value;

    try {
        const response = await fetch(`/api/download/${currentTaskId}?format=${format}`);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '下载失败');
        }

        // 获取文件名
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `subtitle.${format}`;
        if (contentDisposition) {
            const matches = contentDisposition.match(/filename=(.+)/);
            if (matches) {
                filename = matches[1];
            }
        }

        // 下载文件
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

    } catch (error) {
        showError(error.message);
    }
}

// ==================== 烧录字幕功能 ====================

async function burnSubtitles() {
    if (!currentTaskId) {
        showError('没有可烧录的字幕');
        return;
    }

    showLoading('正在烧录字幕到视频...（可能需要几分钟）');

    try {
        const response = await fetch(`/api/burn-subtitles/${currentTaskId}`, {
            method: 'POST'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '烧录失败');
        }

        // 获取烧录时间
        const burnTime = response.headers.get('X-Burn-Time');
        const burnTimeText = burnTime ? `耗时 ${burnTime}秒` : '';

        // 获取文件名
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'video_subtitled.mp4';
        if (contentDisposition) {
            const matches = contentDisposition.match(/filename=(.+)/);
            if (matches) {
                filename = matches[1];
            }
        }

        // 下载视频文件
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        hideLoading();
        showSuccess(`字幕烧录完成！${burnTimeText}`);

    } catch (error) {
        hideLoading();
        showError(error.message);
    }
}

// ==================== UI 辅助函数 ====================

function showLoading(text = '处理中...') {
    document.getElementById('loadingText').textContent = text;
    document.getElementById('loadingOverlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loadingOverlay').style.display = 'none';
}

function showError(message) {
    // 简单的错误提示（可以替换为更好的 UI 组件）
    alert(`❌ 错误: ${message}`);
}

function showSuccess(message) {
    // 简单的成功提示（可以替换为更好的 UI 组件）
    alert(`✅ ${message}`);
}
