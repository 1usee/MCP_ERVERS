const modelSelect = document.getElementById('modelSelect');
const customModelWrap = document.getElementById('customModelWrap');
const customModel = document.getElementById('customModel');
const apiKeyInput = document.getElementById('apiKey');
const audioFileInput = document.getElementById('audioFile');
const promptInput = document.getElementById('prompt');
const submitBtn = document.getElementById('submitBtn');
const resetBtn = document.getElementById('resetBtn');
const statusBox = document.getElementById('status');
const responseText = document.getElementById('responseText');
const audioPlayer = document.getElementById('audioPlayer');
const downloadLink = document.getElementById('downloadLink');

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

async function callMcpService(payload) {
  const response = await fetch('/api/tts', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
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
  const apiKey = apiKeyInput.value.trim();
  const model = getSelectedModel();
  const prompt = promptInput.value.trim();

  if (!apiKey) {
    setStatus('请输入 API Key。', 'error');
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
      apiKey,
      model,
      prompt,
      audioBase64,
      audioFormat: getAudioFormatFromName(file.name)
    });

    responseText.value = result.text || '模型未返回文字内容。';

    if (result.audio_base64 && result.audio_format) {
      const audioSource = `data:audio/${result.audio_format};base64,${result.audio_base64}`;
      audioPlayer.src = audioSource;
      audioPlayer.load();

      downloadLink.href = audioSource;
      downloadLink.download = `output.${result.audio_format}`;
      downloadLink.classList.remove('hidden');
    } else {
      audioPlayer.removeAttribute('src');
      downloadLink.classList.add('hidden');
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
  apiKeyInput.value = '';
  promptInput.value = '请根据这段音频内容回答，并用自然语音输出。';
  modelSelect.value = 'qwen-omni-turbo';
  customModel.value = '';
  responseText.value = '';
  audioPlayer.removeAttribute('src');
  downloadLink.classList.add('hidden');
  setStatus('');
  toggleCustomModel();
}

modelSelect.addEventListener('change', toggleCustomModel);
submitBtn.addEventListener('click', handleSubmit);
resetBtn.addEventListener('click', handleReset);

toggleCustomModel();
