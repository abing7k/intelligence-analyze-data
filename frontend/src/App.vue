<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Database,
  Eye,
  FileSpreadsheet,
  FileText,
  History,
  Languages,
  Loader2,
  RefreshCw,
  Send,
  Sparkles,
  Table2,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-vue-next'

const apiBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

const markdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  typographer: true,
})

const defaultLinkOpen = markdown.renderer.rules.link_open || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))
markdown.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  const targetIndex = token.attrIndex('target')
  if (targetIndex < 0) token.attrPush(['target', '_blank'])
  else token.attrs[targetIndex][1] = '_blank'
  const relIndex = token.attrIndex('rel')
  if (relIndex < 0) token.attrPush(['rel', 'noopener noreferrer'])
  else token.attrs[relIndex][1] = 'noopener noreferrer'
  return defaultLinkOpen(tokens, idx, options, env, self)
}

const defaultLanguages = [
  { code: 'en', label: 'English' },
  { code: 'zh', label: '简体中文' },
  { code: 'ms', label: 'Bahasa Melayu' },
]

const defaultModels = [
  {
    id: 'gpt-5.5',
    label: 'GPT-5.5',
    provider: 'sub2api-primary -> api-866646-backup',
    model: 'gpt-5.5',
    api_style: 'chat',
    is_default: true,
  },
]

const messages = {
  en: {
    appTitle: 'Intelligent Data Analysis',
    appSubtitle: 'LangChain analytics workspace',
    close: 'Close',
    language: 'Language',
    apiOnline: 'API online',
    apiOffline: 'API offline',
    llmReady: 'Model ready',
    llmIssue: 'Model unavailable',
    checking: 'Checking',
    provider: 'Provider',
    model: 'Model',
    selectedModel: 'Analysis model',
    defaultModel: 'Default',
    backupModel: 'Backup',
    automaticFailover: 'Automatic fallback',
    modelReady: 'Selected model ready',
    modelUnavailable: 'Selected model unavailable',
    datasets: 'Datasets',
    refresh: 'Refresh',
    uploadDataset: 'Upload dataset',
    uploadHint: 'CSV, XLS, XLSX',
    uploadLimit: 'Up to {size} MB',
    chooseFile: 'Choose file',
    dropFile: 'Drop the file here',
    noDatasets: 'No datasets yet',
    datasetCount: '{count} datasets',
    rows: 'rows',
    columns: 'columns',
    selected: 'Selected',
    deleteDataset: 'Delete dataset',
    confirmDeleteDataset: 'Delete "{name}" and its analysis history?',
    analysis: 'Analysis',
    currentDataset: 'Current dataset',
    noDatasetSelected: 'No dataset selected',
    question: 'Question',
    questionPlaceholder: 'Example: generate a comprehensive data analysis report with quality, correlations, outliers, modeling, and recommendations',
    analyze: 'Analyze',
    analyzing: 'Analyzing',
    running: 'Generating analysis',
    analysisComplete: 'Analysis complete',
    askRequired: 'Enter a question before analyzing.',
    datasetRequired: 'Select or upload a dataset first.',
    sampleQuestions: [
      'Generate a comprehensive analysis report',
      'Analyze data quality, correlations, outliers, and predictive modeling',
      'Find risks, patterns, feature importance, and recommendations',
      'Build a professional report with metrics and charts',
    ],
    result: 'Result',
    reportDocument: 'Report document',
    summary: 'Summary',
    chart: 'Chart',
    resultTable: 'Result table',
    code: 'Code',
    plan: 'Plan',
    noResult: 'No analysis result yet',
    noChart: 'No chart generated',
    exportReport: 'Export report',
    reportMd: 'MD',
    reportPdf: 'PDF',
    exporting: 'Exporting',
    preview: 'Preview',
    profile: 'Profile',
    schema: 'Schema',
    history: 'History',
    openHistory: 'Open history',
    rerun: 'Rerun',
    deleteHistory: 'Delete history',
    confirmDeleteHistory: 'Delete this history record?',
    noHistory: 'No history yet',
    numeric: 'Numeric',
    datetime: 'Datetime',
    categorical: 'Categorical',
    missing: 'Missing',
    dtype: 'Type',
    samples: 'Samples',
    statistics: 'Statistics',
    intent: 'Intent',
    confidence: 'Confidence',
    runtime: 'Runtime',
    mean: 'mean',
    max: 'max',
    noRows: 'No rows available',
    uploaded: 'Dataset uploaded',
    deleted: 'Deleted',
    reportReady: 'Report ready',
  },
  zh: {
    appTitle: '智能数据分析系统',
    appSubtitle: 'LangChain 数据分析工作台',
    close: '关闭',
    language: '语言',
    apiOnline: 'API 在线',
    apiOffline: 'API 离线',
    llmReady: '模型可用',
    llmIssue: '模型不可用',
    checking: '检查中',
    provider: '服务商',
    model: '模型',
    selectedModel: '分析模型',
    defaultModel: '默认',
    backupModel: '备选',
    automaticFailover: '自动切换备用 API',
    modelReady: '所选模型可用',
    modelUnavailable: '所选模型不可用',
    datasets: '数据集',
    refresh: '刷新',
    uploadDataset: '上传数据集',
    uploadHint: 'CSV、XLS、XLSX',
    uploadLimit: '最大 {size} MB',
    chooseFile: '选择文件',
    dropFile: '释放文件',
    noDatasets: '暂无数据集',
    datasetCount: '{count} 个数据集',
    rows: '行',
    columns: '列',
    selected: '已选择',
    deleteDataset: '删除数据集',
    confirmDeleteDataset: '删除“{name}”及其分析历史？',
    analysis: '智能分析',
    currentDataset: '当前数据集',
    noDatasetSelected: '未选择数据集',
    question: '问题',
    questionPlaceholder: '例如：生成一份包含数据质量、相关性、异常值、预测建模和建议的综合分析报告',
    analyze: '开始分析',
    analyzing: '分析中',
    running: '正在生成分析',
    analysisComplete: '分析完成',
    askRequired: '请先输入分析问题。',
    datasetRequired: '请先选择或上传数据集。',
    sampleQuestions: ['生成综合数据分析报告', '分析数据质量、相关性、异常值和预测建模', '找出风险、模式、特征重要性和建议', '生成包含指标和图表的专业报告'],
    result: '分析结果',
    reportDocument: '报告文档',
    summary: '总结',
    chart: '图表',
    resultTable: '结果表',
    code: '代码',
    plan: '计划',
    noResult: '暂无分析结果',
    noChart: '未生成图表',
    exportReport: '导出报告',
    reportMd: 'MD',
    reportPdf: 'PDF',
    exporting: '导出中',
    preview: '预览',
    profile: '概览',
    schema: '字段',
    history: '历史',
    openHistory: '打开历史',
    rerun: '重新运行',
    deleteHistory: '删除历史',
    confirmDeleteHistory: '删除这条历史记录？',
    noHistory: '暂无历史记录',
    numeric: '数值列',
    datetime: '时间列',
    categorical: '类别列',
    missing: '缺失',
    dtype: '类型',
    samples: '样例',
    statistics: '统计',
    intent: '意图',
    confidence: '置信度',
    runtime: '运行时间',
    mean: '均值',
    max: '最大值',
    noRows: '暂无数据',
    uploaded: '数据集已上传',
    deleted: '已删除',
    reportReady: '报告已生成',
  },
  ms: {
    appTitle: 'Sistem Analisis Data Pintar',
    appSubtitle: 'Ruang kerja analitik LangChain',
    close: 'Tutup',
    language: 'Bahasa',
    apiOnline: 'API aktif',
    apiOffline: 'API tidak aktif',
    llmReady: 'Model sedia',
    llmIssue: 'Model tidak tersedia',
    checking: 'Menyemak',
    provider: 'Penyedia',
    model: 'Model',
    selectedModel: 'Model analisis',
    defaultModel: 'Lalai',
    backupModel: 'Sandaran',
    automaticFailover: 'Sandaran automatik',
    modelReady: 'Model dipilih sedia',
    modelUnavailable: 'Model dipilih tidak tersedia',
    datasets: 'Set data',
    refresh: 'Muat semula',
    uploadDataset: 'Muat naik set data',
    uploadHint: 'CSV, XLS, XLSX',
    uploadLimit: 'Hingga {size} MB',
    chooseFile: 'Pilih fail',
    dropFile: 'Lepaskan fail',
    noDatasets: 'Tiada set data',
    datasetCount: '{count} set data',
    rows: 'baris',
    columns: 'lajur',
    selected: 'Dipilih',
    deleteDataset: 'Padam set data',
    confirmDeleteDataset: 'Padam "{name}" dan sejarah analisisnya?',
    analysis: 'Analisis',
    currentDataset: 'Set data semasa',
    noDatasetSelected: 'Tiada set data dipilih',
    question: 'Soalan',
    questionPlaceholder: 'Contoh: jana laporan analisis lengkap dengan kualiti data, korelasi, outlier, pemodelan ramalan dan cadangan',
    analyze: 'Analisis',
    analyzing: 'Menganalisis',
    running: 'Menjana analisis',
    analysisComplete: 'Analisis selesai',
    askRequired: 'Masukkan soalan sebelum analisis.',
    datasetRequired: 'Pilih atau muat naik set data dahulu.',
    sampleQuestions: [
      'Jana laporan analisis lengkap',
      'Analisis kualiti data, korelasi, outlier dan pemodelan ramalan',
      'Cari risiko, corak, kepentingan ciri dan cadangan',
      'Bina laporan profesional dengan metrik dan carta',
    ],
    result: 'Hasil',
    reportDocument: 'Dokumen laporan',
    summary: 'Ringkasan',
    chart: 'Carta',
    resultTable: 'Jadual hasil',
    code: 'Kod',
    plan: 'Pelan',
    noResult: 'Belum ada hasil analisis',
    noChart: 'Tiada carta dijana',
    exportReport: 'Eksport laporan',
    reportMd: 'MD',
    reportPdf: 'PDF',
    exporting: 'Mengeksport',
    preview: 'Pratonton',
    profile: 'Profil',
    schema: 'Skema',
    history: 'Sejarah',
    openHistory: 'Buka sejarah',
    rerun: 'Jalankan semula',
    deleteHistory: 'Padam sejarah',
    confirmDeleteHistory: 'Padam rekod sejarah ini?',
    noHistory: 'Tiada sejarah',
    numeric: 'Numerik',
    datetime: 'Tarikh masa',
    categorical: 'Kategori',
    missing: 'Hilang',
    dtype: 'Jenis',
    samples: 'Sampel',
    statistics: 'Statistik',
    intent: 'Niat',
    confidence: 'Keyakinan',
    runtime: 'Masa jalan',
    mean: 'purata',
    max: 'maks',
    noRows: 'Tiada baris',
    uploaded: 'Set data dimuat naik',
    deleted: 'Dipadam',
    reportReady: 'Laporan sedia',
  },
}

const dataTabs = ['preview', 'profile', 'schema']
const localeMap = { en: 'en-US', zh: 'zh-CN', ms: 'ms-MY' }

const language = ref(localStorage.getItem('iad-language') || 'en')
const fileInput = ref(null)
const dragActive = ref(false)
const datasets = ref([])
const datasetTotal = ref(0)
const selectedDataset = ref(null)
const preview = ref(null)
const schema = ref(null)
const profile = ref(null)
const historyItems = ref([])
const activeResult = ref(null)
const question = ref('')
const selectedModelId = ref(localStorage.getItem('iad-model-id') || '')
const activeDataTab = ref('preview')
const reportFormat = ref('pdf')
const appError = ref('')
const notice = ref('')
const analysisStatus = ref('')

const state = reactive({
  booting: true,
  uploading: false,
  loadingDatasets: false,
  loadingDatasetDetails: false,
  loadingHistory: false,
  checkingModel: false,
  analyzing: false,
  exporting: false,
})

const system = reactive({
  health: null,
  llm: null,
  config: null,
})

let noticeTimer = null

const t = computed(() => messages[language.value] || messages.en)
const languageOptions = computed(() => system.config?.supported_languages?.length ? system.config.supported_languages : defaultLanguages)
const modelOptions = computed(() => system.config?.models?.length ? system.config.models : defaultModels)
const selectedModel = computed(() => {
  return modelOptions.value.find((model) => modelId(model) === selectedModelId.value) || modelOptions.value[0]
})
const selectedModelLabel = computed(() => selectedModel.value?.label || selectedModel.value?.model || selectedModelId.value || '-')
const apiHealthy = computed(() => system.health?.status === 'ok')
const llmStatusText = computed(() => {
  if (state.checkingModel || !system.llm) return t.value.checking
  if (system.llm.available === true) return t.value.modelReady
  if (system.llm.available === false) return t.value.modelUnavailable
  return t.value.checking
})
const maxFileSize = computed(() => system.config?.max_file_size_mb || 25)
const datasetCountText = computed(() => interpolate(t.value.datasetCount, { count: datasetTotal.value }))
const selectedDatasetId = computed(() => selectedDataset.value?.dataset_id || '')
const previewRows = computed(() => preview.value?.preview_rows || [])
const previewColumns = computed(() => preview.value?.columns?.length ? preview.value.columns : tableColumns(previewRows.value))
const schemaColumns = computed(() => schema.value?.columns || [])
const numericColumns = computed(() => profile.value?.numeric_columns || [])
const datetimeColumns = computed(() => profile.value?.datetime_columns || [])
const categoricalColumns = computed(() => profile.value?.categorical_columns || [])
const statisticsEntries = computed(() => Object.entries(profile.value?.statistics || {}))
const reportMarkdown = computed(() => {
  if (!activeResult.value) return ''
  return activeResult.value.markdown_result || buildFallbackMarkdownResult(activeResult.value)
})
const reportHtml = computed(() => renderMarkdown(reportMarkdown.value))
const resultModelText = computed(() => {
  const id = activeResult.value?.model_id
  if (id) return modelLabel(id)
  if (activeResult.value?.model) return activeResult.value.model
  return selectedModelLabel.value
})
const currentDatasetMeta = computed(() => {
  if (!selectedDataset.value) return t.value.noDatasetSelected
  return `${formatNumber(selectedDataset.value.row_count)} ${t.value.rows} / ${formatNumber(selectedDataset.value.column_count)} ${t.value.columns}`
})

watch(language, (code) => {
  localStorage.setItem('iad-language', code)
  document.documentElement.lang = code
}, { immediate: true })

onMounted(async () => {
  await bootstrap()
})

function apiUrl(path) {
  if (!path) return ''
  if (/^https?:\/\//i.test(path)) return path
  return `${apiBase}${path.startsWith('/') ? path : `/${path}`}`
}

async function apiRequest(path, options = {}) {
  const url = apiUrl(path)
  let response
  try {
    response = await fetch(url, options)
  } catch (error) {
    throw new Error(`Cannot reach API: ${error.message || 'network request failed'}`)
  }
  const contentType = response.headers.get('content-type') || ''
  let payload
  try {
    payload = contentType.includes('application/json') ? await response.json() : await response.text()
  } catch (error) {
    payload = ''
  }
  if (!response.ok || payload?.success === false) {
    throw new Error(apiErrorMessage(response, payload))
  }
  return payload?.data ?? payload
}

function apiErrorMessage(response, payload) {
  const status = `HTTP ${response.status}${response.statusText ? ` ${response.statusText}` : ''}`
  const requestId = payload && typeof payload === 'object' && payload.request_id ? ` Request ID: ${payload.request_id}` : ''
  const message = extractApiErrorMessage(payload)
  if (message) return `${message} (${status}.${requestId})`
  return `${status} while requesting the API.${requestId}`
}

function extractApiErrorMessage(payload) {
  if (!payload) return ''
  if (typeof payload === 'string') {
    const text = payload.trim()
    if (!text || /^<!doctype html/i.test(text) || /^<html/i.test(text)) return ''
    return text.slice(0, 500)
  }
  if (payload.error?.message) return payload.error.message
  if (payload.message) return payload.message
  if (payload.detail) return typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail)
  return ''
}

async function postJson(path, body) {
  return apiRequest(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

async function postEventStream(path, body, handlers = {}) {
  const url = apiUrl(path)
  let response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
  } catch (error) {
    throw new Error(`Cannot reach API: ${error.message || 'network request failed'}`)
  }

  if (!response.ok) {
    const payload = await readResponsePayload(response)
    throw new Error(apiErrorMessage(response, payload))
  }
  if (!response.body) {
    throw new Error('Streaming responses are not supported by this browser.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    buffer = processSseBuffer(buffer, handlers)
    if (done) break
  }
  if (buffer.trim()) processSseBuffer(`${buffer}\n\n`, handlers)
}

async function readResponsePayload(response) {
  const contentType = response.headers.get('content-type') || ''
  try {
    return contentType.includes('application/json') ? await response.json() : await response.text()
  } catch (error) {
    return ''
  }
}

function processSseBuffer(buffer, handlers) {
  let nextBuffer = buffer
  let boundary = nextBuffer.indexOf('\n\n')
  while (boundary !== -1) {
    const rawMessage = nextBuffer.slice(0, boundary)
    nextBuffer = nextBuffer.slice(boundary + 2)
    const message = parseSseMessage(rawMessage)
    if (message) handleSseMessage(message, handlers)
    boundary = nextBuffer.indexOf('\n\n')
  }
  return nextBuffer
}

function parseSseMessage(rawMessage) {
  const lines = rawMessage.replace(/\r\n/g, '\n').split('\n')
  let event = 'message'
  const dataLines = []
  for (const line of lines) {
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) event = line.slice(6).trim()
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  if (!dataLines.length && event === 'message') return null
  const dataText = dataLines.join('\n')
  let data = dataText
  if (dataText) {
    try {
      data = JSON.parse(dataText)
    } catch (error) {
      data = dataText
    }
  }
  return { event, data }
}

function handleSseMessage(message, handlers) {
  if (message.event === 'error') {
    throw new Error(streamErrorMessage(message.data))
  }
  handlers[message.event]?.(message.data)
  handlers.message?.(message)
}

function streamErrorMessage(data) {
  if (!data) return 'Analysis stream failed.'
  if (typeof data === 'string') return data
  if (data.message) return data.code ? `${data.message} (${data.code})` : data.message
  return 'Analysis stream failed.'
}

async function bootstrap() {
  state.booting = true
  appError.value = ''
  const [configResult, healthResult] = await Promise.allSettled([
    apiRequest('/api/config/client'),
    apiRequest('/api/health'),
  ])

  if (configResult.status === 'fulfilled') {
    system.config = configResult.value
    initializeSelectedModel()
  } else {
    initializeSelectedModel()
  }
  if (healthResult.status === 'fulfilled') system.health = healthResult.value
  if (healthResult.status === 'rejected') appError.value = healthResult.reason.message
  await checkSelectedModel()

  await refreshDatasets()
  state.booting = false
}

function initializeSelectedModel() {
  const defaultModelId = system.config?.default_model_id || system.config?.model_name || 'gpt-5.5'
  const availableIds = modelOptions.value.map(modelId)
  if (!selectedModelId.value || !availableIds.includes(selectedModelId.value)) {
    selectedModelId.value = availableIds.includes(defaultModelId) ? defaultModelId : availableIds[0]
  }
  localStorage.setItem('iad-model-id', selectedModelId.value)
}

async function onModelChanged() {
  localStorage.setItem('iad-model-id', selectedModelId.value)
  await checkSelectedModel()
}

async function checkSelectedModel() {
  if (!selectedModelId.value) return
  state.checkingModel = true
  try {
    system.llm = await apiRequest(`/api/health/llm?model_id=${encodeURIComponent(selectedModelId.value)}`)
  } catch (error) {
    system.llm = {
      model_id: selectedModelId.value,
      available: false,
      message: error.message,
    }
  } finally {
    state.checkingModel = false
  }
}

async function refreshDatasets(selectFirst = true) {
  state.loadingDatasets = true
  try {
    const data = await apiRequest('/api/datasets?page=1&page_size=50')
    datasets.value = data.items || []
    datasetTotal.value = data.total || datasets.value.length
    if (selectedDataset.value) {
      selectedDataset.value = datasets.value.find((item) => item.dataset_id === selectedDataset.value.dataset_id) || null
    }
    if (selectFirst && !selectedDataset.value && datasets.value.length) {
      await selectDataset(datasets.value[0])
    }
  } catch (error) {
    appError.value = error.message
  } finally {
    state.loadingDatasets = false
  }
}

async function selectDataset(dataset) {
  selectedDataset.value = dataset
  activeResult.value = null
  await Promise.all([loadDatasetDetails(dataset.dataset_id), loadHistory(dataset.dataset_id)])
}

async function loadDatasetDetails(datasetId) {
  state.loadingDatasetDetails = true
  preview.value = null
  schema.value = null
  profile.value = null
  try {
    const [previewResult, schemaResult, profileResult] = await Promise.all([
      apiRequest(`/api/datasets/${datasetId}/preview?limit=20`),
      apiRequest(`/api/datasets/${datasetId}/schema`),
      apiRequest(`/api/datasets/${datasetId}/profile`),
    ])
    preview.value = previewResult
    schema.value = schemaResult
    profile.value = profileResult
  } catch (error) {
    appError.value = error.message
  } finally {
    state.loadingDatasetDetails = false
  }
}

async function loadHistory(datasetId = selectedDatasetId.value) {
  if (!datasetId) {
    historyItems.value = []
    return
  }
  state.loadingHistory = true
  try {
    const data = await apiRequest(`/api/analysis/history?dataset_id=${encodeURIComponent(datasetId)}&page=1&page_size=20`)
    historyItems.value = data.items || []
  } catch (error) {
    appError.value = error.message
  } finally {
    state.loadingHistory = false
  }
}

function openFilePicker() {
  fileInput.value?.click()
}

async function onFileSelected(event) {
  const file = event.target.files?.[0]
  if (file) await uploadFile(file)
  event.target.value = ''
}

async function onDrop(event) {
  dragActive.value = false
  const file = event.dataTransfer.files?.[0]
  if (file) await uploadFile(file)
}

async function uploadFile(file) {
  state.uploading = true
  appError.value = ''
  const formData = new FormData()
  formData.append('file', file)
  try {
    const dataset = await apiRequest('/api/datasets/upload', {
      method: 'POST',
      body: formData,
    })
    showNotice(t.value.uploaded)
    await refreshDatasets(false)
    await selectDataset(dataset)
  } catch (error) {
    appError.value = error.message
  } finally {
    state.uploading = false
  }
}

async function deleteDataset(dataset) {
  if (!window.confirm(interpolate(t.value.confirmDeleteDataset, { name: dataset.file_name }))) return
  try {
    await apiRequest(`/api/datasets/${dataset.dataset_id}`, { method: 'DELETE' })
    if (selectedDataset.value?.dataset_id === dataset.dataset_id) {
      selectedDataset.value = null
      preview.value = null
      schema.value = null
      profile.value = null
      activeResult.value = null
      historyItems.value = []
    }
    showNotice(t.value.deleted)
    await refreshDatasets()
  } catch (error) {
    appError.value = error.message
  }
}

function useSampleQuestion(sample) {
  question.value = sample
}

async function submitAnalysis() {
  if (!selectedDataset.value) {
    appError.value = t.value.datasetRequired
    return
  }
  if (!question.value.trim()) {
    appError.value = t.value.askRequired
    return
  }

  state.analyzing = true
  appError.value = ''
  analysisStatus.value = t.value.running
  try {
    let result = null
    await postEventStream('/api/analysis/query/stream', {
      dataset_id: selectedDataset.value.dataset_id,
      question: question.value.trim(),
      options: {
        language: language.value,
        model_id: selectedModelId.value,
      },
    }, {
      status: (data) => {
        analysisStatus.value = data?.message || t.value.running
      },
      heartbeat: (data) => {
        analysisStatus.value = data?.message || t.value.running
      },
      result: (data) => {
        result = data
      },
    })
    if (!result) throw new Error('Analysis finished without a result.')
    activeResult.value = result
    analysisStatus.value = t.value.analysisComplete
    showNotice(t.value.analysisComplete)
    await loadHistory()
  } catch (error) {
    appError.value = error.message
    analysisStatus.value = ''
  } finally {
    state.analyzing = false
  }
}

async function openHistory(item) {
  try {
    const result = await apiRequest(`/api/analysis/${item.analysis_id}`)
    activeResult.value = result
    question.value = result.question || ''
  } catch (error) {
    appError.value = error.message
  }
}

async function rerunHistory(item) {
  state.analyzing = true
  appError.value = ''
  analysisStatus.value = t.value.running
  try {
    const result = await apiRequest(`/api/analysis/${item.analysis_id}/rerun`, { method: 'POST' })
    activeResult.value = result
    question.value = result.question || question.value
    showNotice(t.value.analysisComplete)
    await loadHistory()
  } catch (error) {
    appError.value = error.message
  } finally {
    state.analyzing = false
  }
}

async function deleteHistory(item) {
  if (!window.confirm(t.value.confirmDeleteHistory)) return
  try {
    await apiRequest(`/api/analysis/history/${item.history_id}`, { method: 'DELETE' })
    if (activeResult.value?.history_id === item.history_id) activeResult.value = null
    showNotice(t.value.deleted)
    await loadHistory()
  } catch (error) {
    appError.value = error.message
  }
}

async function exportReport() {
  if (!activeResult.value?.analysis_id) return
  state.exporting = true
  appError.value = ''
  try {
    const report = await postJson('/api/reports/export', {
      analysis_id: activeResult.value.analysis_id,
      format: reportFormat.value,
    })
    openDownload(report.report_url)
    showNotice(t.value.reportReady)
  } catch (error) {
    appError.value = error.message
  } finally {
    state.exporting = false
  }
}

function openDownload(path) {
  const anchor = document.createElement('a')
  anchor.href = apiUrl(path)
  anchor.target = '_blank'
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}

function modelId(model) {
  return model?.id || model?.model_id || model?.model || ''
}

function modelLabel(id) {
  const model = modelOptions.value.find((item) => modelId(item) === id || item.model === id)
  return model?.label || id || '-'
}

function renderMarkdown(value) {
  return markdown.render(normalizeMarkdownLinks(String(value || '')))
}

function normalizeMarkdownLinks(value) {
  if (!apiBase) return value
  return value.replace(/(\]\()\/api\//g, (_, prefix) => `${prefix}${apiBase}/api/`)
}

function buildFallbackMarkdownResult(result) {
  const parts = [
    '# Analysis Report',
    '',
    '## Question',
    '',
    result.question || '-',
    '',
    '## Summary',
    '',
    result.text_result || '-',
  ]

  if (result.chart_url) {
    parts.push('', '## Chart', '', `![Chart](${result.chart_url})`)
  }

  if (result.table_result?.length) {
    parts.push('', '## Result Table', '', markdownTable(result.table_result))
  }

  if (result.plan && Object.keys(result.plan).length) {
    parts.push('', '## Plan', '', '```json', JSON.stringify(result.plan, null, 2), '```')
  }

  if (result.generated_code) {
    parts.push('', '## Code', '', '```python', result.generated_code, '```')
  }

  parts.push(
    '',
    '## Metadata',
    '',
    `- Analysis ID: ${result.analysis_id || '-'}`,
    `- History ID: ${result.history_id || '-'}`,
    `- Model: ${resultModelText.value}`,
    `- Created: ${result.created_time || '-'}`,
  )

  return parts.join('\n')
}

function markdownTable(rows) {
  const columns = tableColumns(rows)
  if (!columns.length) return ''
  const header = `| ${columns.map(escapeMarkdownCell).join(' |')} |`
  const divider = `| ${columns.map(() => '---').join(' | ')} |`
  const body = rows
    .slice(0, 80)
    .map((row) => `| ${columns.map((column) => escapeMarkdownCell(cellValue(row[column]))).join(' | ')} |`)
  return [header, divider, ...body].join('\n')
}

function escapeMarkdownCell(value) {
  return String(value ?? '-').replaceAll('|', '\\|').replace(/\r?\n/g, '<br>')
}

function tableColumns(rows) {
  if (!rows?.length) return []
  const columns = new Set()
  rows.slice(0, 20).forEach((row) => Object.keys(row || {}).forEach((key) => columns.add(key)))
  return Array.from(columns)
}

function cellValue(value) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function formatNumber(value) {
  if (value === null || value === undefined || value === '') return '0'
  const number = Number(value)
  if (!Number.isFinite(number)) return String(value)
  return new Intl.NumberFormat(localeMap[language.value] || 'en-US').format(number)
}

function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(localeMap[language.value] || 'en-US', {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function interpolate(text, values) {
  return Object.entries(values).reduce((result, [key, value]) => result.replaceAll(`{${key}}`, value), text)
}

function showNotice(message) {
  notice.value = message
  window.clearTimeout(noticeTimer)
  noticeTimer = window.setTimeout(() => {
    notice.value = ''
  }, 3200)
}
</script>

<template>
  <main class="app-shell">
    <header class="topbar">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">
          <Sparkles :size="22" />
        </div>
        <div>
          <h1>{{ t.appTitle }}</h1>
          <p>{{ t.appSubtitle }}</p>
        </div>
      </div>

      <div class="topbar-controls">
        <div class="status-strip" aria-live="polite">
          <span class="status-pill" :class="{ ok: apiHealthy }">
            <CheckCircle2 v-if="apiHealthy" :size="15" />
            <AlertCircle v-else :size="15" />
            {{ apiHealthy ? t.apiOnline : t.apiOffline }}
          </span>
          <span class="status-pill" :class="{ ok: system.llm?.available === true, warn: system.llm?.available === false }">
            <Loader2 v-if="state.checkingModel" class="spin" :size="15" />
            <Activity v-else :size="15" />
            {{ llmStatusText }}
          </span>
        </div>

        <div class="language-control" :aria-label="t.language">
          <Languages :size="17" aria-hidden="true" />
          <button
            v-for="option in languageOptions"
            :key="option.code"
            type="button"
            :class="{ active: language === option.code }"
            @click="language = option.code"
          >
            {{ option.label }}
          </button>
        </div>
      </div>
    </header>

    <section v-if="system.config" class="system-meta">
      <span>{{ t.provider }}: <strong>{{ selectedModel?.provider || system.config.provider }}</strong></span>
      <span>{{ t.model }}: <strong>{{ selectedModelLabel }}</strong></span>
      <span>{{ t.uploadHint }} · {{ interpolate(t.uploadLimit, { size: maxFileSize }) }}</span>
    </section>

    <div v-if="appError || notice" class="message-stack" aria-live="polite">
      <div v-if="appError" class="message error">
        <AlertCircle :size="18" />
        <span>{{ appError }}</span>
        <button type="button" class="icon-button" :title="t.close" @click="appError = ''">
          <X :size="16" />
        </button>
      </div>
      <div v-if="notice" class="message success">
        <CheckCircle2 :size="18" />
        <span>{{ notice }}</span>
      </div>
    </div>

    <div class="workspace-grid">
      <aside class="panel dataset-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">{{ datasetCountText }}</p>
            <h2>{{ t.datasets }}</h2>
          </div>
          <button type="button" class="icon-button" :title="t.refresh" @click="refreshDatasets(false)">
            <RefreshCw :size="18" :class="{ spin: state.loadingDatasets }" />
          </button>
        </div>

        <div
          class="upload-dropzone"
          :class="{ active: dragActive, busy: state.uploading }"
          @dragenter.prevent="dragActive = true"
          @dragover.prevent="dragActive = true"
          @dragleave.prevent="dragActive = false"
          @drop.prevent="onDrop"
        >
          <input ref="fileInput" type="file" accept=".csv,.xls,.xlsx" @change="onFileSelected" />
          <UploadCloud :size="28" aria-hidden="true" />
          <strong>{{ dragActive ? t.dropFile : t.uploadDataset }}</strong>
          <span>{{ t.uploadHint }} · {{ interpolate(t.uploadLimit, { size: maxFileSize }) }}</span>
          <button type="button" class="secondary-button" :disabled="state.uploading" @click="openFilePicker">
            <Loader2 v-if="state.uploading" class="spin" :size="17" />
            <UploadCloud v-else :size="17" />
            {{ t.chooseFile }}
          </button>
        </div>

        <div class="dataset-list">
          <div
            v-for="dataset in datasets"
            :key="dataset.dataset_id"
            class="dataset-row"
            :class="{ active: selectedDatasetId === dataset.dataset_id }"
          >
            <button type="button" class="dataset-main" @click="selectDataset(dataset)">
              <FileSpreadsheet :size="19" aria-hidden="true" />
              <span class="dataset-copy">
                <strong>{{ dataset.file_name }}</strong>
                <small>{{ formatNumber(dataset.row_count) }} {{ t.rows }} · {{ formatNumber(dataset.column_count) }} {{ t.columns }}</small>
              </span>
            </button>
            <span v-if="selectedDatasetId === dataset.dataset_id" class="selected-badge">{{ t.selected }}</span>
            <button
              type="button"
              class="row-delete"
              :title="t.deleteDataset"
              @click="deleteDataset(dataset)"
            >
              <Trash2 :size="16" />
            </button>
          </div>

          <div v-if="!datasets.length && !state.loadingDatasets" class="empty-state">
            <Database :size="22" />
            <span>{{ t.noDatasets }}</span>
          </div>
        </div>
      </aside>

      <section class="panel analysis-panel">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">{{ t.currentDataset }}</p>
            <h2>{{ selectedDataset?.file_name || t.noDatasetSelected }}</h2>
          </div>
          <span class="meta-chip">{{ currentDatasetMeta }}</span>
        </div>

        <div class="question-area">
          <label for="question">{{ t.question }}</label>
          <textarea
            id="question"
            v-model="question"
            rows="5"
            :placeholder="t.questionPlaceholder"
            :disabled="state.analyzing"
          />
        </div>

        <div class="sample-row">
          <button
            v-for="sample in t.sampleQuestions"
            :key="sample"
            type="button"
            class="sample-chip"
            @click="useSampleQuestion(sample)"
          >
            {{ sample }}
          </button>
        </div>

        <div class="analysis-controls">
          <div class="control-group model-control">
            <span>{{ t.selectedModel }}</span>
            <select v-if="modelOptions.length > 1" v-model="selectedModelId" :disabled="state.analyzing" @change="onModelChanged">
              <option v-for="model in modelOptions" :key="modelId(model)" :value="modelId(model)">
                {{ model.label || model.model || modelId(model) }}
              </option>
            </select>
            <strong v-else class="selected-model-text">{{ selectedModelLabel }}</strong>
            <small>
              {{ t.automaticFailover }}
              <template v-if="selectedModel?.api_style"> · {{ selectedModel.api_style }}</template>
            </small>
          </div>

          <button type="button" class="primary-button" :disabled="state.analyzing" @click="submitAnalysis">
            <Loader2 v-if="state.analyzing" class="spin" :size="18" />
            <Send v-else :size="18" />
            {{ state.analyzing ? t.analyzing : t.analyze }}
          </button>
        </div>

        <div v-if="state.analyzing || analysisStatus" class="analysis-status" aria-live="polite">
          <Loader2 v-if="state.analyzing" class="spin" :size="16" />
          <CheckCircle2 v-else :size="16" />
          {{ analysisStatus }}
        </div>

        <div class="result-surface">
          <div class="result-head">
            <div>
              <p class="eyebrow">{{ t.reportDocument }}</p>
              <h2>{{ activeResult?.question || t.noResult }}</h2>
            </div>
            <div class="result-actions">
              <div class="segmented compact">
                <button type="button" :class="{ active: reportFormat === 'pdf' }" @click="reportFormat = 'pdf'">
                  {{ t.reportPdf }}
                </button>
                <button type="button" :class="{ active: reportFormat === 'md' }" @click="reportFormat = 'md'">
                  {{ t.reportMd }}
                </button>
              </div>
              <button type="button" class="secondary-button" :disabled="!activeResult || state.exporting" @click="exportReport">
                <Loader2 v-if="state.exporting" class="spin" :size="16" />
                <FileText v-else :size="16" />
                {{ state.exporting ? t.exporting : t.exportReport }}
              </button>
            </div>
          </div>

          <div v-if="!activeResult" class="empty-result">
            <Sparkles :size="28" />
            <span>{{ t.noResult }}</span>
          </div>

          <div v-else class="result-body report-body">
            <div class="markdown-document">
              <div class="markdown-body" v-html="reportHtml"></div>
            </div>
          </div>
        </div>
      </section>

      <aside class="side-column">
        <section class="panel data-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">{{ selectedDataset?.file_name || t.noDatasetSelected }}</p>
              <h2>{{ t.preview }}</h2>
            </div>
            <Eye :size="19" aria-hidden="true" />
          </div>

          <div class="tabbar" role="tablist">
            <button
              v-for="tab in dataTabs"
              :key="tab"
              type="button"
              :class="{ active: activeDataTab === tab }"
              @click="activeDataTab = tab"
            >
              {{ t[tab] }}
            </button>
          </div>

          <div v-if="state.loadingDatasetDetails" class="loading-row">
            <Loader2 class="spin" :size="18" />
            {{ t.checking }}
          </div>

          <div v-else-if="activeDataTab === 'preview'" class="table-wrap compact-table">
            <table v-if="previewRows.length && previewColumns.length">
              <thead>
                <tr>
                  <th v-for="column in previewColumns" :key="column">{{ column }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rowIndex) in previewRows" :key="rowIndex">
                  <td v-for="column in previewColumns" :key="column">{{ cellValue(row[column]) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="empty-state">
              <Table2 :size="22" />
              <span>{{ t.noRows }}</span>
            </div>
          </div>

          <div v-else-if="activeDataTab === 'profile'" class="profile-stack">
            <div class="profile-grid">
              <div class="metric-tile">
                <span>{{ t.numeric }}</span>
                <strong>{{ numericColumns.length }}</strong>
              </div>
              <div class="metric-tile">
                <span>{{ t.datetime }}</span>
                <strong>{{ datetimeColumns.length }}</strong>
              </div>
              <div class="metric-tile">
                <span>{{ t.categorical }}</span>
                <strong>{{ categoricalColumns.length }}</strong>
              </div>
            </div>

            <div class="stat-list">
              <div v-for="[column, stats] in statisticsEntries.slice(0, 6)" :key="column" class="stat-row">
                <strong>{{ column }}</strong>
                <span>{{ t.mean }} {{ cellValue(stats.mean) }}</span>
                <span>{{ t.max }} {{ cellValue(stats.max) }}</span>
              </div>
              <div v-if="!statisticsEntries.length" class="empty-state">
                <Activity :size="22" />
                <span>{{ t.noRows }}</span>
              </div>
            </div>
          </div>

          <div v-else class="schema-list">
            <div v-for="column in schemaColumns" :key="column.name" class="schema-row">
              <div>
                <strong>{{ column.name }}</strong>
                <small>{{ t.dtype }}: {{ column.dtype }} · {{ t.missing }}: {{ formatNumber(column.missing_count) }}</small>
              </div>
              <span>{{ (column.sample_values || []).slice(0, 2).map(cellValue).join(', ') || '-' }}</span>
            </div>
            <div v-if="!schemaColumns.length" class="empty-state">
              <Database :size="22" />
              <span>{{ t.noRows }}</span>
            </div>
          </div>
        </section>

        <section class="panel history-panel">
          <div class="panel-heading">
            <div>
              <p class="eyebrow">{{ t.history }}</p>
              <h2>{{ historyItems.length }}</h2>
            </div>
            <History :size="20" aria-hidden="true" />
          </div>

          <div class="history-list">
            <article v-for="item in historyItems" :key="item.history_id" class="history-row">
              <button type="button" class="history-main" :title="t.openHistory" @click="openHistory(item)">
                <strong>{{ item.question }}</strong>
                <span>{{ formatDate(item.created_time) }} · {{ item.language }}</span>
              </button>
              <div class="history-actions">
                <button type="button" class="icon-button" :title="t.rerun" @click="rerunHistory(item)">
                  <RefreshCw :size="16" />
                </button>
                <button type="button" class="icon-button" :title="t.deleteHistory" @click="deleteHistory(item)">
                  <Trash2 :size="16" />
                </button>
              </div>
            </article>

            <div v-if="!historyItems.length && !state.loadingHistory" class="empty-state">
              <History :size="22" />
              <span>{{ t.noHistory }}</span>
            </div>
          </div>
        </section>
      </aside>
    </div>
  </main>
</template>
