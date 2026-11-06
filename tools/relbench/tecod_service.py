#!/usr/bin/env python3
"""TeCoD (Jivani, Maheshwari, Sarawagi; SIGMOD 2026, PACMMOD 3(6) Art. 357) template selection as a JSON-lines service
for the RelBench harness.

Follows the released code (SSLab-CSE-IITB/tecod @ 6739e32, MIT; its pdec submodule smitjivani/nlqtosql_common; a local
copy in results/ext/tecod-src) in its API mode with method "sgc" (services/tecod.py generate_with_method: the matched
template and the ICL examples in the prompt, the examples alone when no template matches; method "auto" with an API
model selects a template but leaves it out of the prompt, so it would be plain ICL), with the released models and the
default settings of conf/config.yaml:
- pool: one per database. Each verified (question, SQL) pair is one example with its masked question (nlq_masked) and a
  template, the SQL with its literals masked (pdec/tecod_utils.py convert_sql_string_to_template, here in PostgreSQL's
  dialect); examples with the same template string share one template id (cli/commands.py _create_templates).
- search: Qwen/Qwen3-Embedding-4B, masked questions embedded with the "skeleton" prompt and the question with the
  "query" prompt (services/embedding.py); cosine similarity, top 1000 (vectorsearch_top_k); the first 30 (nli_top_k)
  go to the NLI model.
- NLI: smitxxiv/Qwen3-Re4B-SQL-TeCoD-TMM on (masked question, question) pairs (nli.py, float32). Per template the mean
  entailment and mean cosine (nli.method mean), sorted by both; ties go to the lowest template id, and the released
  code numbers templates in the sorted order of their strings (groupby("template")), so a tie goes to the template string
  that sorts first; its label is the majority label of its examples; the template matches when that label is entailment
  (services/tecod.py _template_selection_with_timing and generate_with_method).
- ICL: the best example per template by cosine, three of them (icl_cnt), the most similar last (pick_icl_example_indices,
  _get_icl_examples).
Not taken over: grammar-constrained decoding (it needs the model's logits, which the API mode does not have); Milvus Lite
(an exact cosine search over the small pool ranks the same way; ties keep the order in which examples were added); the
sqlglot normalisation of an example's SQL before it is stored (cli/commands.py process_data_command): examples keep the
SQL that was validated, because a round trip through sqlglot can change PostgreSQL syntax, and only the template is
built from the normalised SQL. Where sqlglot cannot parse or print a PostgreSQL query, its string and number literals are
masked token by token instead (sql_template). The released code has no synthetic paraphrase step (data-preparation.md: nlq_masked is
supplied with the data); neither does this service. The released pool is built once, offline, from a file of pairs; here
it grows online, one verified pair after each admitted session (harness tecod_add), because RelBench sessions arrive in
order. The harness puts the template and examples into the user message before the task line, in the released order
(schema, template, examples, question); the agent's own system prompt and tools take the place of TeCoD's one-shot
instruction and output format, as for every arm.

Protocol: one JSON request per line on stdin, one JSON reply per line on stdout.
  {"op": "select", "query"}                                -> {"matched", "t_id", "nli_label", "entailment", "cosine",
                                                               "template", "icl": [[question, sql], ...], "seconds"}
  {"op": "add", "text", "nlq_masked", "sql", "tables", "columns"} -> {"t_id", "template", "new_template", "seconds"}
  {"op": "dump"}                                           -> {"examples": [...], "templates": [...]}

  results/ext/venv-tecod/bin/python tools/relbench/tecod_service.py --models results/ext/tecod-models
"""
import argparse
import json
import os
import sys
import time

VECTORSEARCH_TOP_K = 1000  # conf/config.yaml tecod.vectorsearch_top_k
NLI_TOP_K = 30  # tecod.nli_top_k
ICL_CNT = 3  # tecod.icl_cnt
EMB_PROMPTS = {  # services/embedding.py _create_embedding_function
    "query": "Instruct: Given a user query, retrieve the relevant question skeleton that best matches its semantic structure and intent.\nQuery:{query}",
    "skeleton": "{query}",
}
SEEDS_TOKEN = "relbench_seeds_placeholder"  # {seeds} while sqlglot parses the SQL; a table name, so it is not masked
# a masked number is printed as this number, then replaced: sqlglot's PostgreSQL printer reads number literals as numbers
NUMBER_SENTINEL = "918273645019"


def sql_template(sql, tables, columns):
    """The template of one SQL and how its literals were masked ("parse", or "tokens" where sqlglot cannot parse or
    print the PostgreSQL, e.g. a CTE named glob, a keyword in sqlglot's tokenizer)."""
    try:
        return parsed_template(sql, tables, columns), "parse"
    except Exception:  # noqa: BLE001
        return token_template(sql), "tokens"


def token_template(sql):
    """String and number literals masked token by token (no identifier masking, no normalisation)."""
    import sqlglot
    from sqlglot.tokens import TokenType

    src = sql.strip().rstrip(";").replace("{seeds}", SEEDS_TOKEN)
    for tok in sorted(sqlglot.tokenize(src, read="postgres"), key=lambda x: -x.start):
        if tok.token_type in (TokenType.STRING, TokenType.NUMBER):
            src = src[:tok.start] + ("string_rule" if tok.token_type == TokenType.STRING else "number_rule") + src[tok.end + 1:]
    return src.replace(SEEDS_TOKEN, "{seeds}")


def parsed_template(sql, tables, columns):
    """pdec/tecod_utils.py convert_sql_string_to_template and extract_sqlite_aliases, read and written as PostgreSQL;
    the SQL is first normalised as cli/commands.py process_data_command does (optimize_joins)."""
    from sqlglot import exp, parse_one
    from sqlglot.expressions import CTE, Alias, Subquery, Table
    from sqlglot.optimizer.optimize_joins import optimize_joins

    src = sql.strip().rstrip(";").replace("{seeds}", SEEDS_TOKEN)
    src = optimize_joins(parse_one(src, read="postgres")).sql(dialect="postgres")
    tree = parse_one(src, read="postgres")
    aliases = set()
    for node in tree.walk():
        if isinstance(node, Alias):
            aliases.add(node.alias.lower())
        elif isinstance(node, Table) and node.alias:
            aliases.add(node.alias.lower())
        elif isinstance(node, Subquery) and node.alias:
            aliases.add(node.alias.lower())
        elif isinstance(node, CTE):
            aliases.add(node.alias.lower())
    tables = {t.lower() for t in tables} | {SEEDS_TOKEN}
    columns = {c.lower() for c in columns}

    def mask(node):
        if isinstance(node, exp.Identifier):
            if node.name.lower() not in tables and node.name.lower() not in columns and node.name.lower() not in aliases:
                return exp.Literal.string("string_rule")
        if isinstance(node, exp.Literal):
            return exp.Literal.string("string_rule") if node.is_string else exp.Literal.number(NUMBER_SENTINEL)
        return node

    out = tree.transform(mask).sql(dialect="postgres").replace("'string_rule'", "string_rule")
    return out.replace(NUMBER_SENTINEL, "number_rule").replace(SEEDS_TOKEN, "{seeds}")


class Pool:
    def __init__(self, models):
        import torch
        from sentence_transformers import SentenceTransformer
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        torch.set_num_threads(int(os.environ.get("TECOD_THREADS", "16")))
        self.torch = torch
        self.emb = SentenceTransformer(os.path.join(models, "Qwen3-Embedding-4B"), device="cpu", local_files_only=True)
        nli = os.path.join(models, "Qwen3-Re4B-SQL-TeCoD-TMM")
        self.nli_model = AutoModelForSequenceClassification.from_pretrained(nli).to("cpu").eval()
        self.nli_tok = AutoTokenizer.from_pretrained(nli)
        self.examples = []  # {"text", "nlq_masked", "sql", "t_id"}
        self.vectors = []  # unit vectors of the masked questions
        self.templates = []  # template strings; the index is the template id

    def embed(self, texts, prompt):
        import numpy as np

        v = self.emb.encode([EMB_PROMPTS[prompt].format(query=t) for t in texts], convert_to_numpy=True, show_progress_bar=False)
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    def nli(self, premises, hypothesis):
        """nli.py NLI.__call__: one batch of (masked question, question) pairs, softmax over the labels."""
        import numpy as np

        if not premises:
            return []
        inputs = self.nli_tok([(p, hypothesis) for p in premises], return_tensors="pt", padding=True, truncation=True,
                              max_length=self.nli_model.config.max_position_embeddings)
        with self.torch.inference_mode():
            logits = self.nli_model(**inputs).logits
        prob = self.torch.nn.Softmax(dim=-1)(logits).cpu().to(self.torch.float32).numpy()
        prob = np.nan_to_num(prob, nan=0.0, posinf=1.0, neginf=0.0)
        return [{label: float(prob[j][i]) for i, label in self.nli_model.config.id2label.items()} for j in range(prob.shape[0])]

    def select(self, query):
        """services/tecod.py _template_selection_with_timing (method auto) over the current pool."""
        import numpy as np

        if not self.examples:
            return {"matched": False, "t_id": -1, "nli_label": "none", "entailment": 0.0, "cosine": 0.0, "template": None,
                    "icl": [], "pool_examples": 0, "pool_templates": 0}
        q = self.embed([query], "query")[0]
        cos = np.stack(self.vectors) @ q
        order = sorted(range(len(cos)), key=lambda i: -cos[i])[:VECTORSEARCH_TOP_K]  # stable: ties keep insertion order
        top = order[:NLI_TOP_K]
        probs = self.nli([self.examples[i]["nlq_masked"] for i in top], query)
        rows = [{**p, "nli_label": max(p, key=p.get), "id": i, "t_id": self.examples[i]["t_id"], "cosine": float(cos[i])}
                for p, i in zip(probs, top)]
        by_t = {}
        for r in rows:
            by_t.setdefault(r["t_id"], []).append(r)
        considered = sorted(((sum(r["entailment"] for r in g) / len(g), sum(r["cosine"] for r in g) / len(g), t)
                             for t, g in by_t.items()), key=lambda x: (-x[0], -x[1], self.templates[x[2]]))
        ent, cosine, t_id = considered[0]
        labels = [r["nli_label"] for r in by_t[t_id]]
        label = max(dict.fromkeys(labels), key=labels.count)  # value_counts: the most frequent label
        # ICL: the best example per template by cosine over all retrieved examples, three, the most similar last
        seen, icl = set(), []
        for i in order:
            if self.examples[i]["t_id"] not in seen:
                seen.add(self.examples[i]["t_id"])
                icl.append(i)
            if len(icl) == ICL_CNT:
                break
        icl = icl[::-1]
        matched = t_id >= 0 and label == "entailment"
        return {"matched": matched, "t_id": t_id, "nli_label": label, "entailment": ent, "cosine": cosine,
                "template": self.templates[t_id] if matched else None,
                "icl": [[self.examples[i]["text"], self.examples[i]["sql"]] for i in icl], "icl_ids": icl,
                "nli": [{k: r[k] for k in ("id", "t_id", "nli_label", "entailment", "cosine")} for r in rows],
                "pool_examples": len(self.examples), "pool_templates": len(self.templates)}

    def add(self, text, nlq_masked, sql, tables, columns):
        template, masking = sql_template(sql, tables, columns)
        new = template not in self.templates
        if new:
            self.templates.append(template)
        t_id = self.templates.index(template)
        self.examples.append({"text": text, "nlq_masked": nlq_masked, "sql": sql, "t_id": t_id})
        self.vectors.append(self.embed([nlq_masked], "skeleton")[0])
        return {"t_id": t_id, "template": template, "masking": masking, "new_template": new, "pool_examples": len(self.examples),
                "pool_templates": len(self.templates)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    a = ap.parse_args()
    out = os.fdopen(os.dup(1), "w")  # the protocol keeps the original stdout ...
    os.dup2(2, 1)  # ... and anything else written to file descriptor 1, Python or C, goes to the log
    sys.stdout = sys.stderr
    pool = Pool(a.models)

    def reply(v):
        out.write(json.dumps(v, ensure_ascii=False) + "\n")
        out.flush()

    reply({"ready": True, "nli_labels": list(pool.nli_model.config.id2label.values())})
    for line in sys.stdin:
        if not line.strip():
            continue
        req = json.loads(line)
        t0 = time.time()
        try:
            if req["op"] == "select":
                v = pool.select(req["query"])
            elif req["op"] == "add":
                v = pool.add(req["text"], req["nlq_masked"], req["sql"], req["tables"], req["columns"])
            elif req["op"] == "dump":
                v = {"examples": pool.examples, "templates": pool.templates}
            elif req["op"] == "template":  # smoke tests: the template of one SQL, no model
                v = dict(zip(("template", "masking"), sql_template(req["sql"], req["tables"], req["columns"])))
            else:
                v = {"error": f"unknown op {req['op']}"}
        except Exception as err:  # noqa: BLE001 - every failure goes back to the harness as a reply
            import traceback

            traceback.print_exc()
            v = {"error": f"{type(err).__name__}: {err}"}
        v["seconds"] = time.time() - t0
        reply(v)


if __name__ == "__main__":
    main()
