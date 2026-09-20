const modelSelect = document.getElementById('modelSelect');
const customModelWrap = document.getElementById('customModelWrap');
const customModel = document.getElementById('customModel');
const apiKeyInput = document.getElementById('apiKeyInput');
const apiList = document.getElementById('apiList');
const apiStatus = document.getElementById('apiStatus');
const baseUrlInput = document.getElementById('baseUrlInput');
const saveBaseUrlBtn = document.getElementById('saveBaseUrlBtn');
const settingsBtn = document.getElementById('settingsBtn');
const backBtn = document.getElementById('backBtn');
const mainView = document.getElementById('mainView');
const settingsView = document.getElementById('settingsView');
const addApiBtn = document.getElementById('addApiBtn');
const fetchModelsBtn = document.getElementById('fetchModelsBtn');
const audioFileInput = document.getElementById('audioFile');
const promptInput = document.getElementById('prompt');
const submitBtn = document.getElementById('submitBtn');
const resetBtn = document.getElementById('resetBtn');
const statusBox = document.getElementById('status');
const responseText = document.getElementById('responseText');
const downloadLink = document.getElementById('downloadLink');
const audioResultStatus = document.getElementById('audioResultStatus');
const audioFileInfo = document.getElementById('audioFileInfo');
const audioFileName = document.getElementById('audioFileName');
const audioCreatedAt = document.getElementById('audioCreatedAt');
const audioFileSize = document.getElementById('audioFileSize');
const webToken = localStorage.getItem('mcpWebToken') || '';
let apiKeys = [];
let activeApiKeyId = null;
let audioObjectUrl = '';

function setStatus(message, type = '') {
  statusBox.textContent = message;
  statusBox.className = `status ${type}`.trim();
}

function getSelectedModel() {
  if (modelSelect.value === 'custom') {
    return customModel.value.trim();
  }
  return modelSelect.value.trim();
}

function renderApiList() {
  apiList.replaceChildren();

  if (!apiKeys.length) {
    apiList.innerHTML = '<p class="empty-state">还没有 API Key，请在上方添加。</p>';
    return;
  }

  apiKeys.forEach((apiKey) => {
    const row = document.createElement('div');
    row.className = 'api-item';
    row.innerHTML = `
      <label class="api-choice">
        <input type="radio" name="activeApiKey" value="${apiKey.id}" ${apiKey.active ? 'checked' : ''}>
        <span>${apiKey.masked}</span>
      </label>
      <button class="delete-api" type="button" data-api-id="${apiKey.id}">删除</button>
    `;
    apiList.appendChild(row);
  });
}

function showView(view) {
  const isSettings = view === 'settings';
  mainView.classList.toggle('hidden', isSettings);
  settingsView.classList.toggle('hidden', !isSettings);
  settingsBtn.classList.toggle('hidden', isSettings);
  if (isSettings) {
    apiKeyInput.focus();
  }
}

async function addApiKey() {
  const apiKey = apiKeyInput.value.trim();
  if (!apiKey) {
    apiStatus.textContent = '请输入 API Key。';
    apiStatus.className = 'status error';
    return;
  }
  try {
    await updateConfig('/api/config/api-keys', { method: 'POST', body: { api_key: apiKey } });
    apiKeyInput.value = '';
    apiStatus.textContent = 'API Key 添加成功。';
    apiStatus.className = 'status success';
  } catch (error) {
    apiStatus.textContent = error.message;
    apiStatus.className = 'status error';
  }
}

async function removeApiKey(apiId) {
  try {
    await updateConfig(`/api/config/api-keys/${apiId}`, { method: 'DELETE' });
    apiStatus.textContent = 'API Key 已删除。';
    apiStatus.className = 'status success';
  } catch (error) {
    apiStatus.textContent = error.message;
    apiStatus.className = 'status error';
  }
}

async function updateConfig(url, options = {}) {
  const headers = options.body ? { 'Content-Type': 'application/json' } : {};
  if (webToken) headers['X-MCP-Token'] = webToken;
  const response = await fetch(url, {
    method: options.method || 'GET',
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '配置更新失败');
  if (result.api_keys) {
    apiKeys = result.api_keys;
    const active = apiKeys.find((item) => item.active);
    activeApiKeyId = active ? active.id : null;
    renderApiList();
  }
  if (result.base_url) baseUrlInput.value = result.base_url;
  return result;
}

async function loadConfig() {
  await updateConfig('/api/config');
}

function populateModels(models) {
  const customOption = modelSelect.querySelector('option[value="custom"]');
  modelSelect.replaceChildren(new Option('请先获取模型名称', '', true, true));
  modelSelect.options[0].disabled = true;
  models.forEach((model) => {
    modelSelect.add(new Option(model, model));
  });
  modelSelect.add(customOption);
  modelSelect.value = '';
  toggleCustomModel();
}

async function fetchModels() {
  fetchModelsBtn.disabled = true;
  apiStatus.textContent = '正在获取模型名称…';
  apiStatus.className = 'status';
  try {
    const headers = webToken ? { 'X-MCP-Token': webToken } : {};
    const response = await fetch('/api/models', { headers });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '获取模型名称失败');
    if (!Array.isArray(result.models) || !result.models.length) {
      throw new Error('模型接口未返回模型名称');
    }
    populateModels(result.models);
    apiStatus.textContent = `已获取 ${result.models.length} 个模型。`;
    apiStatus.className = 'status success';
  } catch (error) {
    apiStatus.textContent = error.message;
    apiStatus.className = 'status error';
  } finally {
    fetchModelsBtn.disabled = false;
  }
}

async function saveBaseUrl() {
  try {
    await updateConfig('/api/config', {
      method: 'POST',
      body: { base_url: baseUrlInput.value.trim() }
    });
    apiStatus.textContent = 'Base URL 保存成功。';
    apiStatus.className = 'status success';
  } catch (error) {
    apiStatus.textContent = error.message;
    apiStatus.className = 'status error';
  }
}

function toggleCustomModel() {
  const isCustom = modelSelect.value === 'custom';
  customModelWrap.classList.toggle('hidden', !isCustom);
  if (isCustom) {
    customModel.focus();
  }
}

function toBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (!result || typeof result !== 'string') {
        reject(new Error('文件读取失败'));
        return;
      }
      const base64 = result.includes(',') ? result.split(',')[1] : result;
      resolve(base64);
    };
    reader.onerror = () => reject(new Error('读取音频文件失败'));
    reader.readAsDataURL(file);
  });
}

function getAudioFormatFromName(fileName) {
  const extension = fileName.split('.').pop()?.toLowerCase() || 'wav';
  return extension;
}

function getAudioMimeType(audioFormat) {
  const mimeTypes = {
    mp3: 'audio/mpeg',
    m4a: 'audio/mp4',
    ogg: 'audio/ogg',
    flac: 'audio/flac',
    wav: 'audio/wav'
  };
  return mimeTypes[audioFormat.toLowerCase()] || `audio/${audioFormat}`;
}

function createAudioFileName(audioFormat, createdAt) {
  const parts = [
    createdAt.getFullYear(),
    String(createdAt.getMonth() + 1).padStart(2, '0'),
    String(createdAt.getDate()).padStart(2, '0'),
    String(createdAt.getHours()).padStart(2, '0'),
    String(createdAt.getMinutes()).padStart(2, '0'),
    String(createdAt.getSeconds()).padStart(2, '0')
  ];
  return `output-${parts.slice(0, 3).join('')}-${parts.slice(3).join('')}.${audioFormat}`;
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function createAudioBlob(audioBase64, audioFormat) {
  const normalizedBase64 = audioBase64.includes(',')
    ? audioBase64.split(',', 2)[1]
    : audioBase64;
  const binary = atob(normalizedBase64);
  const bytes = new Uint8Array(binary.length);

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }

  return new Blob([bytes], { type: getAudioMimeType(audioFormat) });
}

function clearAudioResult() {
  if (audioObjectUrl) {
    URL.revokeObjectURL(audioObjectUrl);
    audioObjectUrl = '';
  }
  downloadLink.removeAttribute('href');
  audioFileInfo.classList.add('hidden');
  audioResultStatus.textContent = '等待生成';
  audioFileName.textContent = '-';
  audioCreatedAt.textContent = '-';
  audioFileSize.textContent = '-';
}

async function callMcpService(payload) {
  const headers = { 'Content-Type': 'application/json' };
  if (webToken) headers['X-MCP-Token'] = webToken;
  const response = await fetch('/api/tts', {
    method: 'POST',
    headers,
    body: JSON.stringify(payload)
  });

  const text = await response.text();
  let result;
  try {
    result = text ? JSON.parse(text) : {};
  } catch (error) {
    throw new Error(`服务器返回非 JSON：${text.slice(0, 200)}`);
  }

  if (!response.ok) {
    throw new Error(result.error || '请求失败');
  }

  return result;
}

async function handleSubmit(event) {
  event.preventDefault();

  const file = audioFileInput.files[0];
  const model = getSelectedModel();
  const prompt = promptInput.value.trim();

  if (activeApiKeyId === null) {
    setStatus('请先在右上角“API 设置”中添加 API Key。', 'error');
    return;
  }

  if (!model) {
    setStatus('请选择或输入模型名称。', 'error');
    return;
  }

  if (!file) {
    setStatus('请先上传音频文件。', 'error');
    return;
  }

  if (!prompt) {
    setStatus('请输入文本提示词。', 'error');
    return;
  }

  submitBtn.disabled = true;
  setStatus('正在处理音频，请稍候…');

  try {
    const audioBase64 = await toBase64(file);
    const result = await callMcpService({
      model,
      prompt,
      audioBase64,
      audioFormat: getAudioFormatFromName(file.name)
    });

    responseText.value = result.text || '模型未返回文字内容。';

    clearAudioResult();
    if (result.audio_base64 && result.audio_format) {
      const audioBlob = createAudioBlob(result.audio_base64, result.audio_format);
      const createdAt = new Date();
      const fileName = createAudioFileName(result.audio_format, createdAt);
      audioObjectUrl = URL.createObjectURL(audioBlob);
      downloadLink.href = audioObjectUrl;
      downloadLink.download = fileName;
      audioFileName.textContent = fileName;
      audioCreatedAt.textContent = createdAt.toLocaleString('zh-CN');
      audioFileSize.textContent = formatFileSize(audioBlob.size);
      audioFileInfo.classList.remove('hidden');
      audioResultStatus.textContent = '已生成';
    } else {
      audioResultStatus.textContent = '未返回音频文件';
    }

    setStatus('请求完成。', 'success');
  } catch (error) {
    console.error(error);
    setStatus(error.message || '请求失败，请检查参数或服务状态。', 'error');
  } finally {
    submitBtn.disabled = false;
  }
}

function handleReset() {
  audioFileInput.value = '';
  promptInput.value = '请根据这段音频内容回答，并用自然语音输出。';
  modelSelect.value = '';
  customModel.value = '';
  responseText.value = '';
  clearAudioResult();
  setStatus('');
  toggleCustomModel();
}

modelSelect.addEventListener('change', toggleCustomModel);
submitBtn.addEventListener('click', handleSubmit);
resetBtn.addEventListener('click', handleReset);
settingsBtn.addEventListener('click', () => showView('settings'));
backBtn.addEventListener('click', () => showView('main'));
addApiBtn.addEventListener('click', addApiKey);
fetchModelsBtn.addEventListener('click', fetchModels);
apiKeyInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    addApiKey();
  }
});
apiList.addEventListener('change', (event) => {
  if (event.target.name !== 'activeApiKey') return;
  activeApiKeyId = Number(event.target.value);
  updateConfig('/api/config', {
    method: 'POST',
    body: { active_api_key_id: activeApiKeyId }
  }).then(() => {
    apiStatus.textContent = '已切换当前 API Key。';
    apiStatus.className = 'status success';
  }).catch((error) => {
    apiStatus.textContent = error.message;
    apiStatus.className = 'status error';
  });
});
apiList.addEventListener('click', (event) => {
  const deleteButton = event.target.closest('.delete-api');
  if (deleteButton) {
    removeApiKey(deleteButton.dataset.apiId);
  }
});

saveBaseUrlBtn.addEventListener('click', saveBaseUrl);
toggleCustomModel();
loadConfig().catch((error) => {
  apiStatus.textContent = error.message || '无法读取服务器配置。';
  apiStatus.className = 'status error';
});
