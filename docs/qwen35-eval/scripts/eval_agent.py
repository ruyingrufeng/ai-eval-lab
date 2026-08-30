#!/usr/bin/env python3
"""Qwen3.5-9B Agent 评测 harness
DSH 扮演"手"：执行 9B 决策的工具意图，原样回喂结果，不干预决策。
协议：模型输出一行 JSON 工具调用，或 FINAL_ANSWER: <回答> 结束。
指标：TTFT / prompt / decode / E2E / tool calls / 内存，逐测记录。
"""
import json, os, re, subprocess, sys, time, urllib.request, urllib.error

BASE_URL = os.environ.get("EVAL_URL", "http://127.0.0.1:8090/v1/chat/completions")
RESULTS = os.path.expanduser("~/llm-models/qwen35-eval/results")
TESTS = os.path.expanduser("~/llm-models/qwen35-eval/tests")
os.makedirs(RESULTS, exist_ok=True)

SYSTEM = """你是本机文件系统 Agent。回复必须严格以下面两种格式之一开头，一次一条，不要输出任何其他文字：
TOOL:list_dir <路径>
TOOL:read_file <路径>
TOOL:write_file <路径>|<内容>
TOOL:run_python <python代码一行>
ANSWER: <最终回答>
规则：必须真实调用工具获取信息，禁止编造。工具报错时分析后换方法重试，不要重复同一失败操作。"""


TOOL_WHITELIST = {"list_dir", "read_file", "write_file", "run_python"}

def tool_exec(tool, workdir):
    name = tool.get("tool")
    if name not in TOOL_WHITELIST:
        return f"未知工具 {name}，可用: {sorted(TOOL_WHITELIST)}"
    try:
        if name == "list_dir":
            p = tool["path"]
            return "\n".join(sorted(os.listdir(p)))
        if name == "read_file":
            p = tool["path"]
            with open(p, encoding="utf-8", errors="replace") as f:
                return f.read()[:8000]
        if name == "write_file":
            p, c = tool["path"], tool["content"]
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(c)
            return f"written: {p} ({len(c)} bytes)"
        if name == "run_python":
            code = tool["code"]
            r = subprocess.run(["python3", "-c", code], capture_output=True,
                               text=True, timeout=60, cwd=workdir)
            out = (r.stdout or "") + (("\n[stderr] " + r.stderr) if r.stderr else "")
            return f"exit={r.returncode}\n{out[:8000]}"
    except KeyError as e:
        return f"参数缺失: {e}"
    except FileNotFoundError as e:
        return f"ERROR: 文件或目录不存在: {e}"
    except subprocess.TimeoutExpired:
        return "ERROR: python 执行超时(60s)"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"

def llm_call(messages, max_tokens=100):
    """流式调用，返回 (text, usage, ttft_ms, decode_toks_per_s)"""
    payload = {"model": "qwen3.5-9b", "messages": messages,
               "temperature": 0.6, "top_p": 0.9, "max_tokens": max_tokens,
               "max_completion_tokens": max_tokens,
               "stream": True, "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(BASE_URL, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time(); ttft = None; text = ""; usage = {}
    with urllib.request.urlopen(req, timeout=300) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except Exception:
                continue
            if ttft is None and obj.get("choices") and obj["choices"][0].get("delta", {}).get("content"):
                ttft = time.time() - t0
            if obj.get("choices") and obj["choices"][0].get("delta", {}).get("content"):
                text += obj["choices"][0]["delta"]["content"]
            if obj.get("usage"):
                usage = obj["usage"]
    e2e = time.time() - t0
    pt = usage.get("prompt_tokens", 0); ct = usage.get("completion_tokens", 0)
    decode_s = max(e2e - (ttft or 0), 0.001)
    return text, {"prompt_tokens": pt, "completion_tokens": ct}, (ttft or e2e), (ct / decode_s if ct else 0)

def parse_action(text):
    """解析：TOOL:xxx args 或 ANSWER: 文本"""
    text = text.strip()
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("ANSWER:"):
            return ("answer", line[7:].strip())
        if line.upper().startswith("TOOL:"):
            body = line[5:].strip()
            parts = body.split(None, 1)
            if parts:
                name = parts[0].lower()
                if name in TOOL_WHITELIST:
                    arg = parts[1] if len(parts) > 1 else ""
                    if name in ("read_file", "list_dir"):
                        return ("tool", {"tool": name, "path": arg.strip()})
                    if name == "write_file":
                        if "|" in arg:
                            p, c = arg.split("|", 1)
                            return ("tool", {"tool": name, "path": p.strip(), "content": c})
                        return ("tool", {"tool": name, "path": arg.strip(), "content": ""})
                    if name == "run_python":
                        return ("tool", {"tool": name, "code": arg})
                    return ("tool", {"tool": name})
    return ("invalid", text[:200])

def snapshot_mem(label, log):
    try:
        rss = subprocess.run(["ps", "-Ao", "rss,comm"], capture_output=True, text=True).stdout
        total = sum(int(l.split()[0]) for l in rss.splitlines()
                    if "llama-server" in l) / 1048576
        sw = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout
        used = 0.0
        m = re.search(r"used = ([0-9.]+)([KMGT])", sw)
        if m:
            v = float(m.group(1))
            used = v * {"K": 1e-3, "M": 1, "G": 1e3, "T": 1e6}[m.group(2)] / 1024  # -> GB
        log.append({"label": label, "llama_rss_gb": round(total, 2), "swap_gb": round(used, 2)})
    except Exception:
        pass

def run_test(tid, prompt, workdir, max_steps=30, middle_prompt=None, middle_at=None):
    """跑单个测试。middle_prompt/middle_at 用于 T8 中途改目标。"""
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt}]
    log = {"tid": tid, "steps": [], "tool_calls": 0, "invalid": 0, "dup": 0,
           "answers": [], "mem": [], "tokens": {"prompt": 0, "completion": 0},
           "ttft_ms": [], "decode_tps": [], "start": time.time()}
    prev_tools = set()
    for step in range(max_steps):
        if middle_prompt and middle_at and step == middle_at:
            messages.append({"role": "user", "content": middle_prompt})
            log["steps"].append({"type": "user_mid", "content": middle_prompt})
        snapshot_mem(f"step{step}", log["mem"])
        text, usage, ttft, dts = llm_call(messages)
        log["tokens"]["prompt"] += usage["prompt_tokens"]
        log["tokens"]["completion"] += usage["completion_tokens"]
        log["ttft_ms"].append(round(ttft * 1000, 1))
        log["decode_tps"].append(round(dts, 1))
        kind, val = parse_action(text)
        log["steps"].append({"type": kind, "content": text[:2000],
                             "tokens": usage, "ttft_ms": round(ttft * 1000, 1),
                             "decode_tps": round(dts, 1)})
        if kind == "answer":
            log["answers"].append(val)
            log["final_answer"] = val
            break
        if kind == "tool":
            sig = json.dumps(val, sort_keys=True)[:120]
            if sig in prev_tools and val.get("tool") != "write_file":
                log["dup"] += 1
            prev_tools.add(sig)
            log["tool_calls"] += 1
            result = tool_exec(val, workdir)
            log["steps"].append({"type": "tool_result", "tool": val, "result": result[:2000]})
            messages.append({"role": "assistant", "content": json.dumps(val, ensure_ascii=False)})
            messages.append({"role": "user", "content": "工具结果:\n" + result})
        else:
            log["invalid"] += 1
            messages.append({"role": "assistant", "content": text[:500]})
            messages.append({"role": "user",
                             "content": "无法解析你的输出为工具调用或 FINAL_ANSWER。请只输出一行 JSON 工具调用，或 FINAL_ANSWER: 结束。"})
    log["end"] = time.time()
    log["e2e_s"] = round(log["end"] - log["start"], 1)
    log["steps_count"] = len(log["steps"])
    snapshot_mem("end", log["mem"])
    with open(os.path.join(RESULTS, f"{tid}.json"), "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    return log

def print_summary(log):
    l = log
    print(f"\n===== {l['tid']} =====")
    print(f"steps={l['steps_count']} tool_calls={l['tool_calls']} invalid={l['invalid']} dup={l['dup']} "
          f"E2E={l['e2e_s']}s")
    print(f"prompt_tokens={l['tokens']['prompt']} completion_tokens={l['tokens']['completion']} "
          f"avg_TTFT={sum(l['ttft_ms'])/max(len(l['ttft_ms']),1):.0f}ms "
          f"avg_decode={sum(l['decode_tps'])/max(len(l['decode_tps']),1):.1f}tok/s")
    if l.get("final_answer"):
        print(f"FINAL: {l['final_answer'][:500]}")

if __name__ == "__main__":
    # 单测模式：python3 eval_agent.py <tid> <prompt> <workdir> [max_steps]
    tid, prompt, wd = sys.argv[1], sys.argv[2], sys.argv[3]
    steps = int(sys.argv[4]) if len(sys.argv) > 4 else 30
    log = run_test(tid, prompt, wd, steps)
    print_summary(log)
