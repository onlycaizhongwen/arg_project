<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleDot,
  Database,
  FileUp,
  Gauge,
  Loader2,
  Play,
  RefreshCw,
  Search,
  Server,
  Shield,
  SlidersHorizontal,
  Sparkles,
} from "lucide-vue-next";
import {
  getDiagnostics,
  getHealth,
  getJob,
  getMetricsText,
  getRerankRuntimeConfig,
  search,
  updateRerankRuntimeConfig,
  uploadFile,
  type DiagnosticsResponse,
  type JobResponse,
  type RerankRuntimeConfig,
  type SearchRequest,
  type SearchResult,
  type SearchResponse,
  type UploadResponse,
} from "./api";

const tenantId = ref("default");
const sourceId = ref("console-demo-source");
const knowledgeBaseId = ref("kb-console-demo");
const permissionTags = ref("public");
const actorId = ref("demo-operator");
const requestSource = ref("demo-console");

const selectedFile = ref<File | null>(null);
const uploadBusy = ref(false);
const searchBusy = ref(false);
const refreshBusy = ref(false);
const rerankConfigBusy = ref(false);
const apiHealth = ref<"checking" | "ok" | "error">("checking");
const errorMessage = ref("");

const latestUpload = ref<UploadResponse | null>(null);
const latestJob = ref<JobResponse | null>(null);
const diagnostics = ref<DiagnosticsResponse | null>(null);
const metricsText = ref("");
const rerankRuntimeConfig = ref<RerankRuntimeConfig>({
  provider: "mock",
  model: "mock-reranker",
  base_url: "",
  timeout_seconds: 5,
});

const query = ref("上传成功但检索不到内容时应该如何排查");
const searchMode = ref<SearchRequest["search_mode"]>("hybrid");
const topK = ref(5);
const recallSize = ref(120);
const preRankSize = ref(40);
const rerankEnabled = ref(false);
const rerankSize = ref(5);
const dedupEnabled = ref(true);
const diversityEnabled = ref(true);
const maxChunksPerDocument = ref(2);
const searchResponse = ref<SearchResponse | null>(null);

const results = computed(() => searchResponse.value?.results || searchResponse.value?.items || []);
const jobStatus = computed(() => latestJob.value?.status || latestUpload.value?.status || "未开始");
const isJobDone = computed(() => ["SUCCEEDED", "FAILED"].includes(jobStatus.value));
const diagnosticTone = computed(() => {
  if (!diagnostics.value) return "muted";
  if (diagnostics.value.status === "ok") return "ok";
  if (diagnostics.value.status === "warning") return "warn";
  return "bad";
});

onMounted(async () => {
  await refreshOverview();
});

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] || null;
}

async function refreshOverview() {
  refreshBusy.value = true;
  errorMessage.value = "";
  try {
    await getHealth();
    apiHealth.value = "ok";
    rerankRuntimeConfig.value = await getRerankRuntimeConfig();
    diagnostics.value = await getDiagnostics(tenantId.value);
    metricsText.value = await getMetricsText(tenantId.value);
    if (latestUpload.value?.job_id && !isJobDone.value) {
      latestJob.value = await getJob(latestUpload.value.job_id);
    }
  } catch (error) {
    apiHealth.value = "error";
    errorMessage.value = toMessage(error);
  } finally {
    refreshBusy.value = false;
  }
}

async function switchRerank(provider: RerankRuntimeConfig["provider"]) {
  rerankConfigBusy.value = true;
  errorMessage.value = "";
  const preset = {
    disabled: {
      provider,
      model: "disabled-reranker",
      base_url: "",
      timeout_seconds: 5,
    },
    mock: {
      provider,
      model: "mock-reranker",
      base_url: "",
      timeout_seconds: 5,
    },
    external: {
      provider,
      model: rerankRuntimeConfig.value.model === "mock-reranker"
        ? "BAAI/bge-reranker-base"
        : rerankRuntimeConfig.value.model,
      base_url: rerankRuntimeConfig.value.base_url || "http://reranker:8010/rerank",
      timeout_seconds: rerankRuntimeConfig.value.timeout_seconds || 30,
    },
  } satisfies Record<RerankRuntimeConfig["provider"], RerankRuntimeConfig>;

  try {
    rerankRuntimeConfig.value = await updateRerankRuntimeConfig(preset[provider]);
    rerankEnabled.value = provider !== "disabled";
    await refreshOverview();
  } catch (error) {
    errorMessage.value = toMessage(error);
  } finally {
    rerankConfigBusy.value = false;
  }
}

async function saveExternalRerankConfig() {
  rerankConfigBusy.value = true;
  errorMessage.value = "";
  try {
    rerankRuntimeConfig.value = await updateRerankRuntimeConfig(rerankRuntimeConfig.value);
    rerankEnabled.value = rerankRuntimeConfig.value.provider !== "disabled";
    await refreshOverview();
  } catch (error) {
    errorMessage.value = toMessage(error);
  } finally {
    rerankConfigBusy.value = false;
  }
}

async function submitUpload() {
  if (!selectedFile.value) {
    errorMessage.value = "请先选择要上传的文件。";
    return;
  }
  uploadBusy.value = true;
  errorMessage.value = "";
  latestJob.value = null;
  try {
    latestUpload.value = await uploadFile({
      file: selectedFile.value,
      tenantId: tenantId.value,
      sourceId: sourceId.value,
      knowledgeBaseId: knowledgeBaseId.value,
      permissionTags: permissionTags.value,
      actorId: actorId.value,
      requestSource: requestSource.value,
    });
    await pollJob(latestUpload.value.job_id);
    await refreshOverview();
  } catch (error) {
    errorMessage.value = toMessage(error);
  } finally {
    uploadBusy.value = false;
  }
}

async function pollJob(jobId: string) {
  for (let index = 0; index < 20; index += 1) {
    latestJob.value = await getJob(jobId);
    if (["SUCCEEDED", "FAILED"].includes(latestJob.value.status)) return;
    await delay(1000);
  }
}

async function runSearch() {
  if (!query.value.trim()) {
    errorMessage.value = "请输入检索问题。";
    return;
  }
  searchBusy.value = true;
  errorMessage.value = "";
  try {
    searchResponse.value = await search(
      {
        query: query.value,
        tenant_id: tenantId.value,
        knowledge_base_ids: splitCsv(knowledgeBaseId.value),
        permission_context: splitCsv(permissionTags.value),
        search_mode: searchMode.value,
        top_k: topK.value,
        recall_size: recallSize.value,
        pre_rank_size: preRankSize.value,
        dedup_enabled: dedupEnabled.value,
        diversity_enabled: diversityEnabled.value,
        max_chunks_per_document: maxChunksPerDocument.value,
        rerank_enabled: rerankEnabled.value,
        rerank_size: rerankSize.value,
      },
      {
        tenantId: tenantId.value,
        actorId: actorId.value,
        requestSource: requestSource.value,
        permissionTags: permissionTags.value,
      },
    );
    await refreshOverview();
  } catch (error) {
    errorMessage.value = toMessage(error);
  } finally {
    searchBusy.value = false;
  }
}

function splitCsv(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function metricValue(name: string) {
  const line = metricsText.value
    .split("\n")
    .find((item) => item.startsWith(name));
  return line?.split(" ").at(-1) || "-";
}

function resultText(item: SearchResult) {
  return item.text || item.content || "";
}

function formatScore(value: number | null | undefined) {
  if (typeof value !== "number") return "-";
  return value.toFixed(4);
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function toMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
</script>

<template>
  <main class="console-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">
          <Sparkles :size="20" />
        </div>
        <div>
          <h1>数据清洗与 RAG 演示控制台</h1>
          <p>上传、清洗、检索、重排、诊断</p>
        </div>
      </div>

      <section class="panel compact">
        <div class="section-title">
          <SlidersHorizontal :size="17" />
          <span>演示上下文</span>
        </div>
        <label>
          租户
          <input v-model="tenantId" />
        </label>
        <label>
          知识库
          <input v-model="knowledgeBaseId" />
        </label>
        <label>
          权限标签
          <input v-model="permissionTags" />
        </label>
        <label>
          操作人
          <input v-model="actorId" />
        </label>
        <label>
          请求来源
          <input v-model="requestSource" />
        </label>
      </section>

      <section class="panel compact status-panel">
        <div class="section-title">
          <Activity :size="17" />
          <span>链路状态</span>
          <button class="icon-button" :disabled="refreshBusy" title="刷新" @click="refreshOverview">
            <Loader2 v-if="refreshBusy" :size="16" class="spin" />
            <RefreshCw v-else :size="16" />
          </button>
        </div>
        <div class="status-row">
          <Server :size="16" />
          <span>API</span>
          <strong :class="apiHealth">{{ apiHealth }}</strong>
        </div>
        <div class="status-row">
          <Database :size="16" />
          <span>队列积压</span>
          <strong>{{ diagnostics?.queue_metrics.ready_count ?? "-" }}</strong>
        </div>
        <div class="status-row">
          <Shield :size="16" />
          <span>Rerank</span>
          <strong>{{ rerankRuntimeConfig.provider || diagnostics?.rerank_metrics.provider || "-" }}</strong>
        </div>
        <div class="status-row">
          <Gauge :size="16" />
          <span>失败率</span>
          <strong>{{ diagnostics ? `${(diagnostics.job_metrics.failure_rate * 100).toFixed(1)}%` : "-" }}</strong>
        </div>
      </section>

      <section class="panel compact rerank-switch">
        <div class="section-title">
          <Shield :size="17" />
          <span>Rerank 切换</span>
        </div>
        <div class="segmented">
          <button
            :class="{ active: rerankRuntimeConfig.provider === 'disabled' }"
            :disabled="rerankConfigBusy"
            @click="switchRerank('disabled')"
          >
            关闭
          </button>
          <button
            :class="{ active: rerankRuntimeConfig.provider === 'mock' }"
            :disabled="rerankConfigBusy"
            @click="switchRerank('mock')"
          >
            Mock
          </button>
          <button
            :class="{ active: rerankRuntimeConfig.provider === 'external' }"
            :disabled="rerankConfigBusy"
            @click="switchRerank('external')"
          >
            BGE
          </button>
        </div>
        <label>
          模型
          <input v-model="rerankRuntimeConfig.model" />
        </label>
        <label>
          服务地址
          <input v-model="rerankRuntimeConfig.base_url" placeholder="http://reranker:8010/rerank" />
        </label>
        <label>
          超时秒数
          <input v-model.number="rerankRuntimeConfig.timeout_seconds" type="number" min="1" />
        </label>
        <button class="secondary-button" :disabled="rerankConfigBusy" @click="saveExternalRerankConfig">
          <Loader2 v-if="rerankConfigBusy" :size="16" class="spin" />
          <RefreshCw v-else :size="16" />
          应用配置
        </button>
        <p class="hint">切到 BGE 前需启动 reranker 服务。</p>
      </section>
    </aside>

    <section class="workspace">
      <header class="topbar">
        <div>
          <p class="eyebrow">MVP Console</p>
          <h2>端到端演示链路</h2>
        </div>
        <div class="health-badges">
          <span class="badge" :class="diagnosticTone">
            <CircleDot :size="14" />
            {{ diagnostics?.status || "checking" }}
          </span>
          <span class="badge">
            <CheckCircle2 :size="14" />
            {{ jobStatus }}
          </span>
        </div>
      </header>

      <div v-if="errorMessage" class="alert">
        <AlertTriangle :size="18" />
        <span>{{ errorMessage }}</span>
      </div>

      <section class="flow-grid">
        <div class="panel upload-panel">
          <div class="section-title">
            <FileUp :size="18" />
            <span>1. 文档上传</span>
          </div>
          <div class="upload-strip">
            <label class="file-picker">
              <input type="file" accept=".txt,.md,.csv,.pdf" @change="onFileChange" />
              <span>{{ selectedFile?.name || "选择 TXT / MD / CSV / PDF" }}</span>
            </label>
            <button class="primary-button" :disabled="uploadBusy" @click="submitUpload">
              <Loader2 v-if="uploadBusy" :size="17" class="spin" />
              <Play v-else :size="17" />
              上传并轮询
            </button>
          </div>
          <div class="facts">
            <div>
              <span>任务</span>
              <strong>{{ latestUpload?.job_id || "-" }}</strong>
            </div>
            <div>
              <span>文档</span>
              <strong>{{ latestUpload?.document_id || "-" }}</strong>
            </div>
            <div>
              <span>状态</span>
              <strong>{{ latestJob?.status || latestUpload?.status || "-" }}</strong>
            </div>
          </div>
        </div>

        <div class="panel search-panel">
          <div class="section-title">
            <Search :size="18" />
            <span>2. 检索与重排</span>
          </div>
          <textarea v-model="query" rows="3" />
          <div class="control-grid">
            <label>
              模式
              <select v-model="searchMode">
                <option value="hybrid">hybrid</option>
                <option value="semantic">semantic</option>
                <option value="keyword">keyword</option>
              </select>
            </label>
            <label>
              Top K
              <input v-model.number="topK" type="number" min="1" max="20" />
            </label>
            <label>
              Recall
              <input v-model.number="recallSize" type="number" min="10" max="1000" />
            </label>
            <label>
              粗排
              <input v-model.number="preRankSize" type="number" min="5" max="200" />
            </label>
          </div>
          <div class="toggles">
            <label><input v-model="dedupEnabled" type="checkbox" /> 去重</label>
            <label><input v-model="diversityEnabled" type="checkbox" /> 打散</label>
            <label><input v-model="rerankEnabled" type="checkbox" /> Rerank</label>
            <label>
              Rerank 数
              <input v-model.number="rerankSize" type="number" min="1" max="100" />
            </label>
            <label>
              单文档上限
              <input v-model.number="maxChunksPerDocument" type="number" min="1" max="10" />
            </label>
          </div>
          <button class="primary-button" :disabled="searchBusy" @click="runSearch">
            <Loader2 v-if="searchBusy" :size="17" class="spin" />
            <Search v-else :size="17" />
            执行检索
          </button>
        </div>
      </section>

      <section class="results-layout">
        <div class="panel results-panel">
          <div class="section-title">
            <Sparkles :size="18" />
            <span>3. 命中片段</span>
            <span class="count">{{ results.length }}</span>
          </div>
          <div v-if="!results.length" class="empty">暂无检索结果</div>
          <article v-for="(item, index) in results" :key="item.chunk_id || index" class="result-item">
            <div class="result-meta">
              <strong>#{{ index + 1 }}</strong>
              <span>score {{ formatScore(item.score) }}</span>
              <span>pre {{ formatScore(item.pre_rank_score) }}</span>
              <span>rerank {{ formatScore(item.rerank_score) }}</span>
              <span>{{ item.recall_sources?.join(",") || "recall" }}</span>
            </div>
            <p>{{ resultText(item) }}</p>
          </article>
        </div>

        <div class="panel diagnostics-panel">
          <div class="section-title">
            <Gauge :size="18" />
            <span>4. 诊断摘要</span>
          </div>
          <div class="metric-grid">
            <div>
              <span>近期任务</span>
              <strong>{{ diagnostics?.job_metrics.total_recent_count ?? "-" }}</strong>
            </div>
            <div>
              <span>失败任务</span>
              <strong>{{ diagnostics?.job_metrics.failed_recent_count ?? "-" }}</strong>
            </div>
            <div>
              <span>消费者</span>
              <strong>{{ diagnostics?.queue_metrics.consumer_count ?? "-" }}</strong>
            </div>
            <div>
              <span>滞留锁</span>
              <strong>{{ diagnostics?.lock_metrics.stale_count ?? "-" }}</strong>
            </div>
            <div>
              <span>重排降级</span>
              <strong>{{ diagnostics?.rerank_metrics.degraded_recent_count ?? "-" }}</strong>
            </div>
            <div>
              <span>请求计数</span>
              <strong>{{ metricValue("rag_api_request_total") }}</strong>
            </div>
          </div>
          <pre class="plan-json">{{ JSON.stringify(searchResponse?.search_plan || diagnostics?.signals || [], null, 2) }}</pre>
        </div>
      </section>
    </section>
  </main>
</template>
