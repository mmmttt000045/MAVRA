//! Shared service and evaluation profiles. Benchmark workloads do not own runtime configuration.

use super::{GuardMode, Maint, MiddleConfig, Scope};

pub(crate) fn profile(mode: &str) -> (MiddleConfig, bool, bool) {
    let mut cfg = MiddleConfig { name: mode.into(), record: true, ..Default::default() };
    let (mut middle_tools, mut metric_tools) = (true, true);
    match mode {
        "direct" => {
            cfg.scope = Scope::Session;
            cfg.singleflight = false;
            cfg.guard = GuardMode::Off;
            cfg.feedback = false;
            cfg.validate_sql = false;
            cfg.result_cache = false;
            middle_tools = false;
            metric_tools = false;
        }
        "middle" | "reforce" | "paper-ace" | "paper-awm" | "paper-gmemory" | "paper-tecod" => metric_tools = false,
        "middle-alone" => {
            cfg.scope = Scope::Task;
            cfg.metric_scope = Scope::Task;
            metric_tools = false;
        }
        "metric-local" => {
            cfg.metric_scope = Scope::Agent;
            cfg.cond_reuse = true;
        }
        "metric-global" => cfg.cond_reuse = true,
        "metric-global-schema" => cfg.metric_maint = Maint::Schema,
        "metric-global-revoke" => cfg.metric_maint = Maint::Revoke,
        "metric-global-def" => cfg.metric_maint = Maint::Definition,
        "metric-global-exref" => {
            cfg.cond_reuse = true;
            cfg.g8_example = true;
        }
        "metric-global-snap"
        | "metric-global-push"
        | "reforce-mavra"
        | "metric-global-opt"
        | "metric-global-full"
        | "metric-global-recheck"
        | "metric-template-schema"
        | "metric-template-revoke"
        | "metric-private" => {
            cfg.cond_reuse = true;
            cfg.g8_example = true;
            cfg.g8_snapshot_db = true;
            cfg.optimize = matches!(mode, "metric-global-opt" | "metric-global-full" | "metric-global-recheck");
            cfg.snapshot_exec = matches!(mode, "metric-global-full" | "metric-global-recheck");
            if mode == "metric-private" {
                cfg.scope = Scope::Agent;
                cfg.metric_scope = Scope::Agent;
            }
            if mode == "metric-global-recheck" {
                cfg.metric_maint = Maint::Definition;
                cfg.cond_reuse = false;
                cfg.repair = false;
            }
            if matches!(mode, "metric-template-schema" | "metric-template-revoke") {
                cfg.metric_maint = if mode == "metric-template-schema" { Maint::Schema } else { Maint::Revoke };
                cfg.cond_reuse = false;
                cfg.repair = false;
                cfg.validate_sql = false;
                cfg.result_cache = false;
            }
        }
        "traj-global" | "traj-verify" | "traj-push" | "reforce-traj" => {
            cfg.traj_memory = true;
            cfg.metric_maint = Maint::Off;
            metric_tools = false;
        }
        m if m.starts_with("mem-") => {
            cfg.scope = Scope::Task;
            cfg.metric_scope = Scope::Task;
            cfg.metric_maint = Maint::Off;
            metric_tools = false;
        }
        "reforce-static" => {
            cfg.metric_maint = Maint::Off;
            cfg.g8_example = true;
            cfg.g8_snapshot_db = true;
        }
        "relbench-mavra" => {
            cfg.cond_reuse = true;
            cfg.feature_memory = true;
            metric_tools = false;
        }
        _ => cfg.metric_maint = Maint::Off,
    }
    (cfg, middle_tools, metric_tools)
}
