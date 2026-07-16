# 模型 API Key 汇总

> 来源：`.env`（智能测试平台主配置）+ `LightRAG\.env`（知识库服务配置）

## 一、智能测试平台（`.env`）

| # | 用途 | 模型 | API URL | API Key |
|---|------|------|---------|---------|
| 1 | **智能体对话推理**（LLM，所有 agent 共用的对话/推理模型） | `deepseek-v4-flash` | —（ChatDeepSeek SDK 内置） | `sk-5840262ccd2a4f4395c18196c0732511` |
| 2 | **PDF 图片/图表解析**（多模态，提取文档中的图片文字和图表信息） | `doubao-seed-2-0-mini-260428` | `https://ark.cn-beijing.volces.com/api/v3` | `62f7c0e3-2ea5-4323-9f30-b9c62c074e37` |

**变量说明：**
- `DEEPSEEK_API_KEY` → 所有 agent 调用大模型进行对话和推理时使用
- `IMAGE_PARSER_API_BASE` / `IMAGE_PARSER_API_KEY` / `IMAGE_PARSER_MODEL` → testcase agent 解析文档中的图片/图表/公式（需 `ENABLE_PDF_MULTIMODAL=true`）
- 图片解析走火山引擎豆包 Vision API，OpenAI 兼容接口格式

---

## 二、LightRAG 知识库（`LightRAG\.env`）

| # | 用途 | 模型 | API URL | API Key |
|---|------|------|---------|---------|
| 3 | **实体/关系提取 + 知识图谱问答**（LightRAG 的核心 LLM） | `deepseek-v4-flash` | `https://api.deepseek.com/v1` | `sk-5840262ccd2a4f4395c18196c0732511` |
| 4 | **文档向量化 / 语义检索**（Embedding） | `text-embedding-v4`（1024 维） | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `sk-855e3a0919b543ffb2f8ccb2e5ea1d53` |
| 5 | **检索结果重排序**（Rerank，提升检索精度） | `gte-rerank-v2` | `https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank` | `sk-855e3a0919b543ffb2f8ccb2e5ea1d53` |
| 6 | **PDF 图片/表格/公式视觉理解**（VLM，多模态文档处理） | `doubao-seed-1-6-vision-250815` | `https://ark.cn-beijing.volces.com/api/v3` | `62f7c0e3-2ea5-4323-9f30-b9c62c074e37` |

**变量说明：**
- `LLM_BINDING` / `LLM_BINDING_HOST` / `LLM_BINDING_API_KEY` / `LLM_MODEL` → LightRAG 从文档中提取实体/关系、构建知识图谱、回答查询问题
- `EMBEDDING_BINDING` / `EMBEDDING_BINDING_HOST` / `EMBEDDING_BINDING_API_KEY` / `EMBEDDING_MODEL` → 将文档分块转为 1024 维向量，用于语义检索（与 Milvus 集合维度绑定，**勿改模型**）
- `RERANK_BINDING` / `RERANK_BINDING_HOST` / `RERANK_BINDING_API_KEY` / `RERANK_MODEL` → 对初步检索结果二次排序，提升相关度
- `VLM_LLM_BINDING` / `VLM_LLM_BINDING_HOST` / `VLM_LLM_BINDING_API_KEY` / `VLM_LLM_MODEL` → PDF 中图片/表格/公式的视觉理解（OCR 之外的深层理解）
- Embedding 和 Rerank 共用一个 DashScope key，均来自阿里云百炼

---

## 三、Key 汇总（去重）

| 平台 | API Key | 使用位置 | 所用模型 |
|------|---------|---------|---------|
| **DeepSeek** | `sk-5840262ccd2a4f4395c18196c0732511` | `.env` + `LightRAG\.env`（共用） | `deepseek-v4-flash`（agent 对话推理 + LightRAG 图谱提取/问答） |
| **阿里云 DashScope** | `sk-855e3a0919b543ffb2f8ccb2e5ea1d53` | `LightRAG\.env` | `text-embedding-v4`（向量化）+ `gte-rerank-v2`（重排序） |
| **火山引擎 (豆包)** | `62f7c0e3-2ea5-4323-9f30-b9c62c074e37` | `.env` + `LightRAG\.env`（共用） | `doubao-seed-2-0-mini-260428`（图片解析）+ `doubao-seed-1-6-vision-250815`（VLM） |

---

## 四、部署时需要替换的 Key（对照 deploy 模板）

| deploy 模板变量 | 对应 Key 行号 | 说明 |
|----------------|--------------|------|
| `DEEPSEEK_API_KEY` | #1 | 平台 LLM |
| `IMAGE_PARSER_API_KEY` | #2 | PDF 图片解析 |
| `lightrag: LLM_BINDING_API_KEY` | #3 | LightRAG LLM |
| `lightrag: EMBEDDING_BINDING_API_KEY` | #4 | 向量化 |
| `lightrag: RERANK_BINDING_API_KEY` | #5 | 重排序（与 #4 同一把） |
| `lightrag: VLM_LLM_BINDING_API_KEY` | #6 | 视觉理解（与 #2 同一把） |
