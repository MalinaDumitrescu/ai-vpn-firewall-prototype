// Central API client for the AI VPN Firewall Prototype backend.

export const API_BASE =
  import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8765';

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { Accept: 'application/json' },
    ...options,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body && body.detail) detail = body.detail;
    } catch (_) {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  health: () => request('/health'),
  models: () => request('/models'),
  defaultModel: () => request('/models/default'),
  model: (id) => request(`/models/${encodeURIComponent(id)}`),
  modelPolicy: (id) => request(`/models/${encodeURIComponent(id)}/policy`),
  modelMetrics: (id) => request(`/models/${encodeURIComponent(id)}/metrics`),
  comparison: () => request('/comparison/summary'),
  uiGroups: () => request('/models/ui-groups'),
  mainComparison: () => request('/models/main-comparison'),
  advancedBenchmarks: () => request('/models/advanced-benchmarks'),
  robustnessControls: () => request('/models/robustness-controls'),
  hiddenModels: () => request('/models/hidden'),
  runtimeModels: () => request('/firewall/runtime-models'),
  runtimeRequiredFeatures: () => request('/firewall/runtime-required-features'),
  multimodelDemo: () => request('/firewall/multimodel-demo'),
  analyzeMultimodelCsv: (file, selectedModelIds) => {
    const fd = new FormData();
    fd.append('file', file);
    const qs = selectedModelIds ? `?selected_model_ids=${encodeURIComponent(selectedModelIds)}` : '';
    return request(`/firewall/analyze-csv-multimodel${qs}`, { method: 'POST', body: fd });
  },
  firewallDemo: () => request('/firewall/demo'),
  requiredFeatures: () => request('/firewall/required-features'),
  analyzeCsv: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return request('/firewall/analyze-csv', { method: 'POST', body: fd });
  },
  // live replay
  liveReplayUpload: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return request('/firewall/live-replay/upload', { method: 'POST', body: fd });
  },
  liveReplayStep: (batchSize = 5) =>
    request(`/firewall/live-replay/step?batch_size=${batchSize}`, { method: 'POST' }),
  liveReplayReset: () =>
    request('/firewall/live-replay/reset', { method: 'POST' }),
  liveReplayState: () => request('/firewall/live-replay/state'),
  liveReplayTemplateUrl: () => `${API_BASE}/firewall/live-replay/template`,
  // live ingest (PCAP streamer monitor)
  liveIngestState: () => request('/firewall/live-ingest/state'),
  liveIngestReset: () =>
    request('/firewall/live-ingest/reset', { method: 'POST' }),

  // ---- compatible benchmark (4 audit-approved models, read-only) ----
  benchmarkInfo: () => request('/benchmark/compatible-csv/info'),
  benchmarkBundled: () => request('/benchmark/compatible-csv/bundled'),
  benchmarkUploadCsv: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return request('/benchmark/compatible-csv', { method: 'POST', body: fd });
  },

  // ---- demo runner (local thesis demo only) ----
  demoAllowed: () => request('/demo/allowed'),
  demoJobs:    () => request('/demo/jobs'),
  demoJob:     (jobId) => request(`/demo/jobs/${encodeURIComponent(jobId)}`),
  demoCancel:  (jobId) =>
    request(`/demo/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' }),
  demoRun: (name, { allowConcurrent = false } = {}) =>
    request(`/demo/run/${encodeURIComponent(name)}?allow_concurrent=${allowConcurrent}`, {
      method: 'POST',
    }),
  // ---- legacy benchmark comparison (Model Comparison page) ----
  legacyBenchmarkModels: () => request('/benchmark/legacy/models'),
  legacyBenchmarkBundled: (selectedModelIds) => {
    const qs = selectedModelIds ? `?selected_model_ids=${encodeURIComponent(selectedModelIds)}` : '';
    return request(`/benchmark/legacy/bundled${qs}`);
  },
  legacyBenchmarkUploadCsv: (file, selectedModelIds) => {
    const fd = new FormData();
    fd.append('file', file);
    const qs = selectedModelIds ? `?selected_model_ids=${encodeURIComponent(selectedModelIds)}` : '';
    return request(`/benchmark/compare${qs}`, { method: 'POST', body: fd });
  },

  // ---- frontend model details metadata package ----
  modelDetailsFrontendContent: () => request('/model-details/frontend-content'),
  modelDetailsCards:          () => request('/model-details/cards'),
  modelDetailsFeatures:       () => request('/model-details/features'),
  modelDetailsMetrics:        () => request('/model-details/metrics'),
  modelDetailsBenchmarkCompat:() => request('/model-details/benchmark-compatibility'),
  modelDetailsMissingReport:  async () => {
    const url = `${API_BASE}/model-details/missing-report`;
    const res = await fetch(url, { headers: { Accept: 'text/plain' } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.text();
  },
  // ---- unified benchmark (active model only, unified feature contract v2) ----
  unifiedBenchmarkBundled: () => request('/firewall/multimodel-demo'),
  unifiedBenchmarkUploadCsv: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    return request('/firewall/analyze-csv-multimodel', { method: 'POST', body: fd });
  },
};





