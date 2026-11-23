//! HTTP tool middleware interface for data agents:
//!
//!   GET  /v1/tools              Tool manifest and JSON Schemas (including find_metric, run_metric, and run_sql)
//!   POST /v1/tools/{name}       Invoke tool; body: {"agent": "...", "session": "...", "tables": [...], "args": {...}}
//!   GET  /v1/stats              Middleware validation, sharing, cache, and snapshot counters
//!   GET  /v1/knowledge          Published metric definitions, join paths, and dependency versions
//!   POST /v1/learn_features     Extract and gate point-in-time predictive feature definitions (RelBench)
//!   GET  /v1/features           Published predictive feature definitions and task programs

use crate::llm::Provider;
use crate::middle::{served_tool_specs, Ctx, LearnReq, Middle, Role};
use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::Deserialize;
use serde_json::{json, Value};
use std::sync::{Arc, OnceLock};

/// Extractor LLM provider for `/v1/learn_features` (`serve --extractor`).
static EXTRACTOR: OnceLock<Provider> = OnceLock::new();

#[derive(Deserialize)]
struct CallReq {
    agent: String,
    session: Option<String>,
    task: Option<String>,
    tables: Option<Vec<String>>,
    #[serde(default)]
    args: Value,
}

async fn list_tools(State(mid): State<Arc<Middle>>) -> Json<Value> {
    Json(json!(served_tool_specs(&mid.cfg)))
}

async fn call(State(mid): State<Arc<Middle>>, Path(name): Path<String>, Json(req): Json<CallReq>) -> (StatusCode, Json<Value>) {
    let ctx = Ctx {
        agent: req.agent,
        session: req.session.unwrap_or_else(|| "default".into()),
        task: req.task.unwrap_or_default(),
        role: Role { name: "http".into(), tables: req.tables.map(|t| t.into_iter().collect()) },
    };
    match mid.call_tool(&ctx, &name, &req.args).await {
        Ok(v) => (StatusCode::OK, Json(v)),
        Err(e) => (StatusCode::BAD_REQUEST, Json(json!({"error": format!("{e:#}")}))),
    }
}

#[derive(Deserialize)]
struct LearnHttp {
    agent: String,
    session: Option<String>,
    #[serde(flatten)]
    req: LearnReq,
}

async fn learn_features(State(mid): State<Arc<Middle>>, Json(body): Json<LearnHttp>) -> (StatusCode, Json<Value>) {
    let Some(p) = EXTRACTOR.get() else {
        return (StatusCode::BAD_REQUEST, Json(json!({"error": "serve was started without --extractor"})));
    };
    if !mid.cfg.feature_memory {
        return (StatusCode::BAD_REQUEST, Json(json!({"error": "feature_memory is not enabled in the active profile"})));
    }
    let ctx = Ctx {
        agent: body.agent,
        session: body.session.unwrap_or_else(|| "default".into()),
        task: body.req.task.clone(),
        role: Role { name: "http".into(), tables: None },
    };
    match mid.learn_features(&ctx, p, &body.req).await {
        Ok(v) => (StatusCode::OK, Json(v)),
        Err(e) => (StatusCode::BAD_REQUEST, Json(json!({"error": format!("{e:#}")}))),
    }
}

async fn features(State(mid): State<Arc<Middle>>) -> Json<Value> {
    Json(mid.feature_report())
}

async fn stats(State(mid): State<Arc<Middle>>) -> Json<Value> {
    Json(mid.stats_json())
}

async fn knowledge(State(mid): State<Arc<Middle>>) -> Json<Value> {
    Json(json!(mid.knowledge()))
}

pub async fn serve(mid: Arc<Middle>, extractor: Option<Provider>, addr: &str) -> anyhow::Result<()> {
    if let Some(p) = extractor {
        let _ = EXTRACTOR.set(p);
    }
    let app = Router::new()
        .route("/v1/tools", get(list_tools))
        .route("/v1/tools/:name", post(call))
        .route("/v1/stats", get(stats))
        .route("/v1/knowledge", get(knowledge))
        .route("/v1/learn_features", post(learn_features))
        .route("/v1/features", get(features))
        .with_state(mid);
    let listener = tokio::net::TcpListener::bind(addr).await?;
    eprintln!("MAVRA HTTP server listening on http://{addr}/v1/tools");
    axum::serve(listener, app)
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
        })
        .await?;
    Ok(())
}
