//! LLM agent client supporting Anthropic Messages and OpenAI-compatible chat-completion APIs (`openai`, `deepseek`, `zhipu`).
//! Agents interact with PostgreSQL exclusively through MAVRA's tool interface.

use crate::middle::{Ctx, Middle, ToolSpec};
use anyhow::{anyhow, bail, Context, Result};
use serde_json::{json, Value};
use std::io::Write;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

#[derive(Clone, Debug)]
pub struct ToolCall {
    pub id: String,
    pub name: String,
    pub input: Value,
}

/// 与厂商无关的对话记录；各 Provider 自己转换成请求格式。
#[derive(Clone, Debug)]
pub enum Turn {
    User(String),
    /// raw：厂商原样返回的助手消息（Anthropic 为 content 数组，需原样回传，含 thinking 块）
    Assistant {
        raw: Value,
    },
    ToolResults(Vec<(String, String, bool)>),
}

#[derive(Debug, Default)]
pub struct Reply {
    pub raw: Value,
    pub text: String,
    pub calls: Vec<ToolCall>,
    pub input_tokens: u64,
    pub output_tokens: u64,
    /// Actual model identifier reported by the API endpoint (when upstream routing aliases the requested model)
    pub model: Option<String>,
    /// 因回报模型不符而丢弃的回复数及其 token（不计入 input/output_tokens）
    pub discarded: u32,
    pub discarded_tokens: u64,
}

#[derive(Default)]
pub struct OpenAiOptions {
    reasoning_effort: Option<String>,
    thinking: Option<String>,
    preserve_reasoning: bool,
    /// 只接受服务端回报为该模型名的回复（`*_REQUIRE_MODEL`）；不符的丢弃重发
    require_model: Option<String>,
    /// 设置 require_model 时每轮并发发出的相同请求数（`*_HEDGE`，默认 1）
    hedge: usize,
}

/// OpenAi.vendor：报告中的服务名；openai 配置记为 openai-compatible，与旧报告一致
pub enum Provider {
    Anthropic { key: String, base: String, model: String, http: reqwest::Client },
    OpenAi { vendor: &'static str, key: String, base: String, model: String, options: OpenAiOptions, http: reqwest::Client },
}

/// Built-in OpenAI-compatible provider profiles: (profile name, env prefix, default base URL).
const OPENAI_PROFILES: [(&str, &str, &str); 3] = [
    ("openai", "OPENAI", "https://api.openai.com/v1"),
    ("deepseek", "DEEPSEEK", "https://api.deepseek.com"),
    ("zhipu", "ZHIPU", "https://open.bigmodel.cn/api/paas/v4"),
];

/// Per-request timeout of 300s with bounded retries in `post_json`.
fn http() -> reqwest::Client {
    reqwest::Client::builder()
        .timeout(Duration::from_secs(300))
        .user_agent(concat!("mavra/", env!("CARGO_PKG_VERSION")))
        .build()
        .expect("http client")
}

impl Provider {
    pub fn from_env(kind: &str) -> Result<Provider> {
        Self::from_lookup(kind, |k| std::env::var(k).ok().filter(|v| !v.is_empty()))
    }

    fn from_lookup(kind: &str, env: impl Fn(&str) -> Option<String>) -> Result<Provider> {
        if let Some(&(name, prefix, default_base)) = OPENAI_PROFILES.iter().find(|p| p.0 == kind) {
            let var = |k: &str| env(&format!("{prefix}_{k}"));
            let base = var("BASE_URL").unwrap_or_else(|| default_base.into());
            let thinking = var("THINKING");
            anyhow::ensure!(
                thinking.as_deref().is_none_or(|v| matches!(v, "enabled" | "disabled")),
                "{prefix}_THINKING must be enabled or disabled"
            );
            // DeepSeek and Zhipu BigModel thinking modes require echoing reasoning_content within tool-calling turns.
            let preserve_reasoning = std::env::var_os("FIG6_PRESERVE_REASONING").is_some()
                || reqwest::Url::parse(&base).ok().is_some_and(|u| matches!(u.host_str(), Some("api.deepseek.com" | "open.bigmodel.cn")));
            return Ok(Provider::OpenAi {
                vendor: if name == "openai" { "openai-compatible" } else { name },
                key: var("API_KEY").ok_or_else(|| anyhow!("missing {prefix}_API_KEY in environment or .env"))?,
                model: var("MODEL").ok_or_else(|| anyhow!("missing {prefix}_MODEL (e.g., deepseek-flash, glm-4.5-air, gpt-4o)"))?,
                base,
                http: http(),
                options: OpenAiOptions {
                    reasoning_effort: var("REASONING_EFFORT"),
                    thinking,
                    preserve_reasoning,
                    require_model: var("REQUIRE_MODEL"),
                    hedge: var("HEDGE").and_then(|h| h.parse().ok()).unwrap_or(1).clamp(1, 8),
                },
            });
        }
        Ok(match kind {
            "claude" | "anthropic" => Provider::Anthropic {
                key: env("ANTHROPIC_API_KEY").ok_or_else(|| anyhow!("missing ANTHROPIC_API_KEY in environment or .env"))?,
                base: env("ANTHROPIC_BASE_URL").unwrap_or_else(|| "https://api.anthropic.com".into()),
                model: env("ANTHROPIC_MODEL").ok_or_else(|| anyhow!("missing ANTHROPIC_MODEL"))?,
                http: http(),
            },
            _ => bail!("unknown provider: {kind} (expected openai | deepseek | zhipu | anthropic | claude)"),
        })
    }

    pub fn label(&self) -> String {
        match self {
            Provider::Anthropic { model, .. } => format!("anthropic:{model}"),
            Provider::OpenAi { vendor, model, .. } => format!("{vendor}:{model}"),
        }
    }

    /// 报告中记录的模型配置（不含 key）
    pub fn config(&self) -> Value {
        match self {
            Provider::Anthropic { base, model, .. } => json!({"provider": "anthropic", "base_url": base, "model": model}),
            Provider::OpenAi { vendor, base, model, options, .. } => json!({"provider": vendor, "base_url": base, "model": model,
                "reasoning_effort": options.reasoning_effort, "thinking": options.thinking,
                "require_model": options.require_model, "hedge": options.hedge}),
        }
    }

    pub async fn chat(&self, system: &str, turns: &[Turn], tools: &[ToolSpec]) -> Result<Reply> {
        match self {
            Provider::Anthropic { key, base, model, http } => anthropic_chat(http, base, key, model, system, turns, tools).await,
            Provider::OpenAi { key, base, model, options, http, .. } => {
                openai_chat(http, base, key, (model, options), system, turns, tools).await
            }
        }
    }
}

/// Retries transient server/network errors up to 3 times (2, 4, 8s) and HTTP 429 rate limits up to 8 times
/// using `Retry-After` or bounded exponential backoff with jitter.
async fn post_json(req: reqwest::RequestBuilder, body: &Value) -> Result<Value> {
    let (mut failures, mut limited) = (0u32, 0u32);
    loop {
        let resp = req.try_clone().ok_or_else(|| anyhow!("request cannot be cloned for retry"))?.json(body).send().await;
        let wait = match resp {
            Ok(r) => {
                let status = r.status();
                let retry_after = r.headers().get("retry-after").and_then(|v| v.to_str().ok()).and_then(|v| v.trim().parse::<u64>().ok());
                let text = r.text().await.unwrap_or_default();
                let last = format!("HTTP {status}: {}", text.chars().take(500).collect::<String>());
                if status.is_success() {
                    match serde_json::from_str(&text) {
                        Ok(v) => return Ok(v),
                        Err(_) => {
                            failures += 1;
                            if failures > 3 {
                                bail!("non-JSON response after retries: {last}");
                            }
                            tokio::time::sleep(Duration::from_secs(2u64.pow(failures))).await;
                            continue;
                        }
                    }
                }
                if (status.as_u16() == 429 && !futile_429(&text)) || (status.is_server_error() && wrapped_rate_limit(&text).is_some()) {
                    limited += 1;
                    if limited > 8 {
                        bail!("rate-limit retries exhausted (8): {last}");
                    }
                    let secs = retry_after.or(wrapped_rate_limit(&text).flatten()).unwrap_or(5 * 2u64.pow(limited - 1)).min(120);
                    eprintln!("  HTTP 429 rate limit: retrying in {secs}s (attempt {limited})");
                    Duration::from_millis(secs * 1000 + (rand::random::<f64>() * 2000.0) as u64)
                } else if status.as_u16() == 529 || status.is_server_error() {
                    failures += 1;
                    if failures > 3 {
                        bail!("request failed after retries: {last}");
                    }
                    Duration::from_secs(2u64.pow(failures))
                } else {
                    bail!(last);
                }
            }
            Err(e) => {
                let last = e.to_string();
                failures += 1;
                if failures > 3 {
                    bail!("request failed after retries: {last}");
                }
                Duration::from_secs(2u64.pow(failures))
            }
        };
        tokio::time::sleep(wait).await;
    }
}

/// Detects upstream rate-limit errors wrapped in an error body and extracts optional `Retry after Ns`.
fn wrapped_rate_limit(body: &str) -> Option<Option<u64>> {
    let low = body.to_ascii_lowercase();
    if !(low.contains("rate_limit_exceeded") || low.contains("rate limit exceeded")) {
        return None;
    }
    let re = regex::Regex::new(r"(?i)retry after\s+(\d+)\s*s").expect("正则");
    Some(re.captures(body).and_then(|c| c[1].parse::<u64>().ok()))
}

/// 智谱 BigModel 也用 429 表示欠费（1113）、内容审核拦截（1301）和额度用尽（1308 / 1310），重试无效
fn futile_429(body: &str) -> bool {
    let v: Value = serde_json::from_str(body).unwrap_or_default();
    let code = &v["error"]["code"];
    matches!(code.as_str().map_or_else(|| code.to_string(), str::to_string).as_str(), "1113" | "1301" | "1308" | "1310")
}

// ───────────────────────── Anthropic Messages API（原始 HTTP） ─────────────────────────

async fn anthropic_chat(
    http: &reqwest::Client,
    base: &str,
    key: &str,
    model: &str,
    system: &str,
    turns: &[Turn],
    tools: &[ToolSpec],
) -> Result<Reply> {
    let messages: Vec<Value> = turns
        .iter()
        .map(|t| match t {
            Turn::User(s) => json!({"role": "user", "content": s}),
            Turn::Assistant { raw } => json!({"role": "assistant", "content": raw}),
            Turn::ToolResults(rs) => json!({"role": "user", "content": rs.iter().map(|(id, c, err)| json!({
                "type": "tool_result", "tool_use_id": id, "content": c, "is_error": err
            })).collect::<Vec<_>>()}),
        })
        .collect();
    let tools: Vec<Value> = tools.iter().map(|t| json!({"name": t.name, "description": t.description, "input_schema": t.schema})).collect();
    let mut body = json!({"model": model, "max_tokens": 16000, "system": system, "messages": messages});
    if !tools.is_empty() {
        body["tools"] = json!(tools);
    }
    let req = http
        .post(format!("{}/v1/messages", base.trim_end_matches('/')))
        .header("x-api-key", key)
        .header("anthropic-version", "2023-06-01")
        .header("content-type", "application/json");
    let v = post_json(req, &body).await?;
    let stop = v["stop_reason"].as_str().unwrap_or_default();
    if stop == "refusal" {
        bail!("模型拒绝回答：{}", v["stop_details"]);
    }
    let content = v["content"].clone();
    let mut r = Reply {
        raw: content.clone(),
        input_tokens: v["usage"]["input_tokens"].as_u64().unwrap_or(0),
        output_tokens: v["usage"]["output_tokens"].as_u64().unwrap_or(0),
        ..Default::default()
    };
    for b in content.as_array().into_iter().flatten() {
        match b["type"].as_str() {
            Some("text") => r.text.push_str(b["text"].as_str().unwrap_or_default()),
            Some("tool_use") => r.calls.push(ToolCall {
                id: b["id"].as_str().unwrap_or_default().into(),
                name: b["name"].as_str().unwrap_or_default().into(),
                input: b["input"].clone(),
            }),
            _ => {}
        }
    }
    Ok(r)
}

// ───────────────────────── OpenAI 兼容 Chat Completions ─────────────────────────

/// 设置了 require_model 时最多发出的轮数（每轮 hedge 个并发请求）
const MODEL_ROUNDS: u32 = 15;

/// Unwraps nested `data.choices` payloads if returned by an OpenAI-compatible endpoint.
fn completion_payload(mut v: Value) -> Value {
    if v["data"]["choices"].is_array() {
        v["data"].take()
    } else {
        v
    }
}

/// 发出请求；设置了 require_model 时，回报模型不符的回复丢弃，每轮并发 hedge 份，取第一个相符的。
/// 返回 (响应, 丢弃数, 丢弃回复的 token)。
async fn post_model(req: &reqwest::RequestBuilder, body: &Value, options: &OpenAiOptions) -> Result<(Value, u32, u64)> {
    let clone = || req.try_clone().ok_or_else(|| anyhow!("请求无法重试"));
    let Some(want) = &options.require_model else { return Ok((completion_payload(post_json(clone()?, body).await?), 0, 0)) };
    let (mut discarded, mut wasted, mut last) = (0u32, 0u64, String::new());
    for _ in 0..MODEL_ROUNDS {
        let mut pending: futures::stream::FuturesUnordered<_> =
            (0..options.hedge.max(1)).map(|_| clone().map(|r| post_json(r, body))).collect::<Result<_>>()?;
        while let Some(r) = futures::StreamExt::next(&mut pending).await {
            match r.map(completion_payload) {
                Ok(v) if v["model"].as_str() == Some(want.as_str()) => return Ok((v, discarded, wasted)),
                Ok(v) => {
                    discarded += 1;
                    wasted += v["usage"]["total_tokens"].as_u64().unwrap_or(0);
                    last = format!("服务端回报模型 {}", v["model"].as_str().unwrap_or("?"));
                }
                Err(e) => last = format!("{e:#}"),
            }
        }
    }
    bail!("{MODEL_ROUNDS} 轮内没有拿到 {want} 的回复（丢弃 {discarded} 个；最后：{last}）")
}

async fn openai_chat(
    http: &reqwest::Client,
    base: &str,
    key: &str,
    (model, options): (&str, &OpenAiOptions),
    system: &str,
    turns: &[Turn],
    tools: &[ToolSpec],
) -> Result<Reply> {
    let mut messages = vec![json!({"role": "system", "content": system})];
    for t in turns {
        match t {
            Turn::User(s) => messages.push(json!({"role": "user", "content": s})),
            Turn::Assistant { raw } => {
                let mut m = raw.clone();
                if !options.preserve_reasoning {
                    if let Some(o) = m.as_object_mut() {
                        o.remove("reasoning_content");
                    }
                }
                messages.push(m);
            }
            Turn::ToolResults(rs) => {
                for (id, c, _) in rs {
                    messages.push(json!({"role": "tool", "tool_call_id": id, "content": c}));
                }
            }
        }
    }
    let tools: Vec<Value> = tools
        .iter()
        .map(|t| json!({"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.schema}}))
        .collect();
    let mut body = json!({"model": model, "messages": messages});
    if let Some(effort) = &options.reasoning_effort {
        body["reasoning_effort"] = json!(effort);
    }
    if let Some(thinking) = &options.thinking {
        body["thinking"] = json!({"type":thinking});
    }
    if !tools.is_empty() {
        body["tools"] = json!(tools);
    }
    let req = http.post(format!("{}/chat/completions", base.trim_end_matches('/'))).bearer_auth(key);
    let (v, discarded, discarded_tokens) = post_model(&req, &body, options).await?;
    // 智谱 BigModel：输出被内容审核截断或超出上下文窗口时回复不完整，按调用失败处理
    if let Some(r @ ("sensitive" | "model_context_window_exceeded")) = v["choices"][0]["finish_reason"].as_str() {
        bail!("模型回复不完整：finish_reason={r}");
    }
    let msg = v["choices"][0]["message"].clone();
    let mut r = Reply {
        raw: msg.clone(),
        text: msg["content"].as_str().unwrap_or_default().to_string(),
        input_tokens: v["usage"]["prompt_tokens"].as_u64().unwrap_or(0),
        output_tokens: v["usage"]["completion_tokens"].as_u64().unwrap_or(0),
        model: v["model"].as_str().map(str::to_string),
        discarded,
        discarded_tokens,
        ..Default::default()
    };
    for c in msg["tool_calls"].as_array().into_iter().flatten() {
        let args = c["function"]["arguments"].as_str().unwrap_or("{}");
        r.calls.push(ToolCall {
            id: c["id"].as_str().unwrap_or_default().into(),
            name: c["function"]["name"].as_str().unwrap_or_default().into(),
            input: serde_json::from_str(args).unwrap_or(json!({})),
        });
    }
    Ok(r)
}

// ───────────────────────── Agent 循环 ─────────────────────────

pub(crate) const SYSTEM_MIDDLE: &str = "工具由数据中间层提供：join_path 返回两表验证过的关联方式（含需要的行过滤）；\
run_sql 可能拒绝不可靠的写法并说明原因与建议，请按提示修改后重试；返回中的 notices 是中间层对你此前结果的提醒。";

const SYSTEM_BUSINESS_GRAIN: &str = "按题目或已学业务定义的业务键识别事件。其他字段相似、金额相同或结果不同于历史答案，\
不足以证明不同业务键的记录是重复数据。改变统计粒度、时间归属或度量前，需要当前数据与业务定义的依据。";
const SYSTEM_METRIC_USE: &str = "回答已知业务指标时，先用 find_metric 查找定义。已有可用定义时，用 run_metric 按本题的期间和题型执行（题目按维度属性取值、比较或排名时，用它的 slice、slice_diff、rank_by 问法）：\
它返回的结果已在本次查询读取的数据快照上通过该定义全部条件的检查，直接作为答案提交，不要再去重、改变粒度或另写 SQL 复算。\
不可用条目的历史映射仅供修复理解，计算前须核验当前映射；无法可靠恢复时请求澄清。条目原因指出部分事实无法归入期间、\
且数据中无法确定这些事实属于哪个期间时，请求澄清，不要只按能归入期间的事实作答。";

/// `chain`：要求 Agent 给出参与答案的查询编号与算式（指标经验评测用）。
pub fn final_answer_spec(chain: bool) -> ToolSpec {
    let mut schema =
        json!({"type": "object", "properties": {"answer": {"type": "string"}, "sql": {"type": "string"}}, "required": ["answer"]});
    if chain {
        schema["properties"]["used"] = json!({"type": "array", "items": {"type": "string"},
            "description": "参与计算最终答案的查询编号（run_sql 返回的 ref，如 r2）"});
        schema["properties"]["derivation"] = json!({"type": "string",
            "description": "用查询编号写出的最终答案算式，如 r2 - r3；答案直接来自一条查询时写 r2。rN 取第 N 条查询结果第一行第一列的值，\
                            参与计算的查询请把所需的值放在第一列；只写算式，不加说明"});
    }
    ToolSpec { name: "final_answer", description: "提交最终答案。", schema }
}

pub fn clarification_spec() -> ToolSpec {
    ToolSpec {
        name: "ask_clarification",
        description: "题目中的业务口径不明确、且无法从数据或工具得到可靠定义时，请求澄清。调用后任务结束。",
        schema: json!({"type": "object", "properties": {"question": {"type": "string", "description": "需要澄清的内容"}}, "required": ["question"]}),
    }
}

fn parse_used(v: &Value) -> Vec<String> {
    v.as_array()
        .into_iter()
        .flatten()
        .filter_map(|x| match x {
            Value::String(s) => crate::metric::ref_index(s),
            Value::Number(n) => n.as_u64().and_then(|n| usize::try_from(n).ok()),
            _ => None,
        })
        .map(|n| format!("r{n}"))
        .collect()
}

#[derive(Debug, Default, serde::Serialize)]
pub struct AgentRun {
    pub answer: Option<String>,
    pub sql: Option<String>,
    pub steps: usize,
    pub tool_calls: usize,
    pub tool_errors: usize,
    pub rejections: usize,
    pub notices: usize,
    pub input_tokens: u64,
    pub output_tokens: u64,
    pub seconds: f64,
    pub used: Vec<String>,
    pub derivation: Option<String>,
    /// 调用了 ask_clarification（任务随即结束）
    pub clarification: Option<String>,
    /// 服务端回报的实际模型名 → 次数
    pub served_models: std::collections::BTreeMap<String, u32>,
    /// Replies and tokens discarded due to `require_model` mismatch (upstream routing overhead, excluded from session trace)
    pub discarded_replies: u32,
    pub discarded_tokens: u64,
    /// 工具调用与结果（结果截断），供记忆基线在会话结束后写记忆；不进报告
    pub transcript: Vec<Value>,
}

/// JSON Lines 记录（一行一个对象，每行写完即落盘）。`Middle::trace` 设置后，Agent 循环逐次记录工具调用。
#[derive(Debug)]
pub struct Trace(parking_lot::Mutex<std::fs::File>);

impl Trace {
    pub fn create(path: &str) -> Result<Trace> {
        Ok(Trace(parking_lot::Mutex::new(std::fs::File::create(path).with_context(|| format!("创建 {path} 失败"))?)))
    }

    pub fn write(&self, v: &Value) {
        let _ = self.0.lock().write_all(format!("{v}\n").as_bytes());
    }
}

pub fn unix_ms() -> f64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map_or(0.0, |d| d.as_secs_f64() * 1000.0)
}

fn tail(s: &str, n: usize) -> String {
    let k = s.chars().count();
    s.chars().skip(k.saturating_sub(n)).collect()
}

/// 本轮调用工具前的思考与正文末尾，供事后判断每次调用的意图（探查、验证、作答）。
fn thought(r: &Reply) -> Value {
    let reasoning = r.raw["reasoning_content"].as_str().unwrap_or_default();
    json!({"reasoning": tail(reasoning, 800), "text": tail(&r.text, 400)})
}

/// 通用 Agent 循环：由调用方给出系统提示与工具。final_answer 与 ask_clarification 结束任务，其余工具交给中间层。
pub async fn run_agent_with(
    p: &Provider,
    mid: &Middle,
    ctx: &Ctx,
    question: &str,
    system: &str,
    tools: &[ToolSpec],
    max_steps: usize,
) -> Result<AgentRun> {
    let mut system = if std::env::var_os("FIG6_LEGACY_SHARED_PROMPT").is_some() {
        system.to_string()
    } else {
        format!("{system}\n{SYSTEM_BUSINESS_GRAIN}")
    };
    if tools.iter().any(|tool| tool.name == "run_metric") {
        system.push('\n');
        system.push_str(SYSTEM_METRIC_USE);
    }
    let mut turns = vec![Turn::User(question.to_string())];
    let mut run = AgentRun::default();
    let t0 = Instant::now();
    for _ in 0..max_steps {
        let r = crate::timing::measure("llm", p.chat(&system, &turns, tools)).await?;
        crate::timing::reply(r.input_tokens, r.output_tokens, r.discarded_tokens, r.model.as_deref());
        run.steps += 1;
        run.input_tokens += r.input_tokens;
        run.output_tokens += r.output_tokens;
        if let Some(m) = &r.model {
            *run.served_models.entry(m.clone()).or_default() += 1;
        }
        run.discarded_replies += r.discarded;
        run.discarded_tokens += r.discarded_tokens;
        run.transcript.push(json!({"kind":"assistant", "message":r.raw}));
        turns.push(Turn::Assistant { raw: r.raw.clone() });
        if r.calls.is_empty() {
            run.answer = Some(r.text.trim().to_string());
            break;
        }
        let mut results = vec![];
        let mut done = false;
        for (seq, c) in r.calls.iter().enumerate() {
            run.tool_calls += 1;
            let _span = crate::timing::Timer::start(&format!("tool:{}", c.name));
            let (t0, started) = (unix_ms(), Instant::now());
            // (状态, 中间层返回；出错时为错误信息)
            let (status, out) = if c.name == "final_answer" {
                run.answer = c.input["answer"].as_str().map(str::to_string).or_else(|| Some(c.input["answer"].to_string()));
                run.sql = c.input["sql"].as_str().map(str::to_string);
                run.used = parse_used(&c.input["used"]);
                run.derivation = c.input["derivation"].as_str().map(str::trim).filter(|s| !s.is_empty()).map(str::to_string);
                done = true;
                results.push((c.id.clone(), "已记录".to_string(), false));
                ("final", Value::Null)
            } else if c.name == "ask_clarification" {
                run.clarification = Some(c.input["question"].as_str().unwrap_or_default().to_string());
                done = true;
                results.push((c.id.clone(), "已记录；本实验没有人工答复，任务结束。".to_string(), false));
                ("clarify", Value::Null)
            } else {
                match mid.call_tool(ctx, &c.name, &c.input).await {
                    Ok(v) => {
                        let rejected = v["rejected"].as_bool() == Some(true);
                        if rejected {
                            run.rejections += 1;
                        }
                        run.notices += v["notices"].as_array().map_or(0, |a| a.len());
                        let s = v.to_string();
                        results.push((c.id.clone(), s.chars().take(12000).collect(), false));
                        (if rejected { "rejected" } else { "ok" }, v)
                    }
                    Err(e) => {
                        run.tool_errors += 1;
                        let msg = format!("错误：{e:#}");
                        results.push((c.id.clone(), msg.clone(), true));
                        ("error", Value::String(msg))
                    }
                }
            };
            if c.name != "final_answer" && c.name != "ask_clarification" {
                let shown = match &out {
                    Value::String(m) => m.clone(),
                    v => v.to_string(),
                };
                run.transcript.push(json!({"kind":"tool", "call_id":c.id, "status":status, "tool":c.name, "input":c.input, "output":shown.chars().take(12000).collect::<String>()}));
            }
            if c.name == "final_answer" || c.name == "ask_clarification" {
                run.transcript
                    .push(json!({"kind":"tool", "call_id":c.id, "status":status, "tool":c.name, "input":c.input, "output":"recorded"}));
            }
            if let Some(trace) = &mid.trace {
                let result = if out.is_null() { Value::Null } else { Value::String(out.to_string().chars().take(600).collect()) };
                trace.write(&json!({
                    "agent": ctx.agent, "session": ctx.session, "task": ctx.task, "step": run.steps, "seq": seq,
                    "tool": c.name, "args": c.input, "status": status, "t0_ms": t0, "ms": started.elapsed().as_secs_f64() * 1000.0,
                    "rows": out["result"]["row_count"], "ref": out["ref"], "result": result,
                    "thought": if seq == 0 { thought(&r) } else { Value::Null }, "served_model": r.model, "discarded": r.discarded,
                }));
            }
        }
        if done {
            break;
        }
        turns.push(Turn::ToolResults(results));
    }
    run.seconds = t0.elapsed().as_secs_f64();
    Ok(run)
}

#[cfg(test)]
mod provider_tests {
    use super::*;
    use crate::middle::tool_specs_with;
    use axum::{routing::post, Json, Router};

    #[tokio::test]
    async fn request_without_tools_omits_tool_field() {
        let app = Router::new().route(
            "/v1/chat/completions",
            post(|Json(body): Json<Value>| async move {
                assert_eq!(body["model"], "test-model");
                assert_eq!(body["messages"][0]["role"], "system");
                assert!(body.get("tools").is_none());
                Json(json!({"choices": [{"message": {"role": "assistant", "content": "{\"ok\":true}"}}]}))
            }),
        );
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        let server = tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
        let provider = Provider::OpenAi {
            vendor: "openai-compatible",
            key: "test-key".into(),
            base: format!("http://{addr}/v1"),
            model: "test-model".into(),
            options: OpenAiOptions::default(),
            http: reqwest::Client::builder().no_proxy().build().unwrap(),
        };
        let reply = provider.chat("Return JSON", &[Turn::User("aggregate metrics".into())], &[]).await.unwrap();
        assert_eq!(reply.text, r#"{"ok":true}"#);
        assert!(reply.calls.is_empty());
        server.abort();
    }

    #[tokio::test]
    async fn deepseek_max_and_tool_history_are_preserved() {
        let app = Router::new().route(
            "/chat/completions",
            post(|Json(body): Json<Value>| async move {
                assert_eq!(body["model"], "deepseek-flash");
                assert_eq!(body["reasoning_effort"], "max");
                assert_eq!(body["thinking"]["type"], "enabled");
                assert_eq!(body["messages"][2]["reasoning_content"], "test fixture reasoning");
                assert_eq!(body["messages"][3]["tool_call_id"], "call-test");
                assert!(body["tools"].is_array());
                Json(json!({"choices":[{"message":{"role":"assistant","content":"OK"}}]}))
            }),
        );
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        let server = tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
        let provider = Provider::OpenAi {
            vendor: "openai-compatible",
            key: "test-key".into(),
            base: format!("http://{addr}"),
            model: "deepseek-flash".into(),
            options: OpenAiOptions {
                reasoning_effort: Some("max".into()),
                thinking: Some("enabled".into()),
                preserve_reasoning: true,
                ..Default::default()
            },
            http: reqwest::Client::builder().no_proxy().build().unwrap(),
        };
        let turns = vec![
            Turn::User("test".into()),
            Turn::Assistant {
                raw: json!({"role":"assistant","content":null,
            "reasoning_content":"test fixture reasoning","tool_calls":[{"id":"call-test","type":"function",
            "function":{"name":"describe_table","arguments":"{}"}}]}),
            },
            Turn::ToolResults(vec![("call-test".into(), "{}".into(), false)]),
        ];
        let reply = provider.chat("test", &turns, &tool_specs_with(true, false)).await.unwrap();
        assert_eq!(reply.text, "OK");
        server.abort();
    }

    #[tokio::test]
    async fn required_model_handles_plain_and_wrapped_replies() {
        use std::sync::atomic::{AtomicU32, Ordering};
        for wrapped in [false, true] {
            let calls = std::sync::Arc::new(AtomicU32::new(0));
            let app = Router::new().route(
                "/chat/completions",
                post(move || {
                    let calls = calls.clone();
                    async move {
                        let n = calls.fetch_add(1, Ordering::SeqCst);
                        let model = if n < 2 { "old-model" } else { "want-model" };
                        let payload = json!({"model": model, "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
                                            "choices": [{"message": {"role": "assistant", "content": model}}]});
                        Json(if wrapped { json!({"data": payload}) } else { payload })
                    }
                }),
            );
            let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
            let addr = listener.local_addr().unwrap();
            let server = tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
            let provider = Provider::OpenAi {
                vendor: "openai-compatible",
                key: "test-key".into(),
                base: format!("http://{addr}"),
                model: "want-model".into(),
                options: OpenAiOptions { require_model: Some("want-model".into()), hedge: 1, ..Default::default() },
                http: reqwest::Client::builder().no_proxy().build().unwrap(),
            };
            let reply = provider.chat("test", &[Turn::User("test".into())], &[]).await.unwrap();
            assert_eq!((reply.text.as_str(), reply.discarded, reply.discarded_tokens), ("want-model", 2, 12));
            assert_eq!((reply.input_tokens, reply.output_tokens), (5, 1));
            server.abort();
        }
    }

    #[test]
    fn wrapped_rate_limit_extracts_retry_seconds() {
        let wrapped = r#"{"error":"request failed with status 429: {\"error\":{\"message\":\"Rate limit exceeded. Retry after 57s.\",\"type\":\"rate_limit_exceeded\"}}"}"#;
        assert_eq!(wrapped_rate_limit(wrapped), Some(Some(57)));
        assert_eq!(wrapped_rate_limit(r#"{"error":"Internal Server Error"}"#), None);
    }

    #[test]
    fn named_profiles_read_their_own_variables() {
        let vars = std::collections::HashMap::from([
            ("ZHIPU_API_KEY", "zhipu-key"),
            ("ZHIPU_MODEL", "glm-4.5-air"),
            ("OPENAI_API_KEY", "openai-key"),
            ("OPENAI_MODEL", "other"),
        ]);
        let lookup = |k: &str| vars.get(k).map(|v| v.to_string());
        let zhipu = Provider::from_lookup("zhipu", lookup).unwrap();
        assert_eq!(zhipu.label(), "zhipu:glm-4.5-air");
        let Provider::OpenAi { key, base, options, .. } = &zhipu else { panic!("zhipu 应为 OpenAI 兼容") };
        assert_eq!((key.as_str(), base.as_str()), ("zhipu-key", "https://open.bigmodel.cn/api/paas/v4"));
        assert!(options.preserve_reasoning);
        assert_eq!(Provider::from_lookup("openai", lookup).unwrap().label(), "openai-compatible:other");
        assert!(Provider::from_lookup("deepseek", lookup).is_err());
    }

    #[tokio::test]
    async fn zhipu_content_filter_fails_without_retry() {
        use axum::http::StatusCode;
        let app = Router::new().route(
            "/chat/completions",
            post(|Json(body): Json<Value>| async move {
                if body["model"] == "blocked-input" {
                    (StatusCode::TOO_MANY_REQUESTS, Json(json!({"error": {"code": "1301", "message": "test fixture"}})))
                } else {
                    (
                        StatusCode::OK,
                        Json(json!({"choices": [{"finish_reason": "sensitive", "message": {"role": "assistant", "content": ""}}]})),
                    )
                }
            }),
        );
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        let server = tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
        for model in ["blocked-input", "blocked-output"] {
            let provider = Provider::OpenAi {
                vendor: "zhipu",
                key: "test-key".into(),
                base: format!("http://{addr}"),
                model: model.into(),
                options: OpenAiOptions::default(),
                http: reqwest::Client::builder().no_proxy().build().unwrap(),
            };
            let start = Instant::now();
            assert!(provider.chat("test", &[Turn::User("test".into())], &[]).await.is_err());
            assert!(start.elapsed() < Duration::from_secs(2), "{model} 不应重试");
        }
        server.abort();
    }
}
