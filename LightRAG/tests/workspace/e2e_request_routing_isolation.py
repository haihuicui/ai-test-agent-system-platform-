"""双 workspace 隔离验证（LightRAG per-request 路由 backport）。

流程：
1. ws_alpha 入库文档 A（阿尔法协议 Foxconn-9000）
2. ws_beta 入库文档 B（贝塔登录 OAuth2-PKCE）
3. 各自轮询 pipeline_status 等处理完成
4. 交叉查询验证隔离：alpha 知 A 不知 B；beta 知 B 不知 A；默认库均不知
"""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:9622"

DOC_A = (
    "阿尔法项目（Project Alpha）的数据传输层统一使用 Foxconn-9000 私有协议。"
    "该协议基于 UDP 多播，默认端口 7788，密钥轮换周期为 4 小时。"
    "任何组件不得以 TCP 直连替代 Foxconn-9000 通道。"
)
DOC_B = (
    "贝塔项目（Project Beta）的登录接口采用 OAuth2-PKCE 授权码流程。"
    "客户端必须使用 S256 code_challenge，state 参数不少于 32 字节随机值。"
    "禁止回退到隐式（implicit）流程。"
)

Q_A = "阿尔法项目的数据传输用什么协议？默认端口是多少？"
Q_B = "贝塔项目的登录接口使用什么授权流程？"


def req(method, path, workspace=None, body=None, timeout=60):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if workspace:
        headers["LIGHTRAG-WORKSPACE"] = workspace
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read())


def wait_pipeline(workspace, label, max_wait=300):
    deadline = time.time() + max_wait
    while time.time() < deadline:
        st = req("GET", "/documents/pipeline_status", workspace=workspace)
        busy = st.get("busy") or st.get("scanning") or st.get("pending_enqueues")
        if not busy:
            print(f"[{label}] pipeline idle", flush=True)
            return True
        time.sleep(3)
    print(f"[{label}] pipeline 等待超时", flush=True)
    return False


def query(workspace, q, label):
    resp = req(
        "POST",
        "/query",
        workspace=workspace,
        body={"query": q, "mode": "hybrid"},
        timeout=180,
    )
    text = str(resp.get("response", ""))
    print(f"[{label}] {text[:150].replace(chr(10), ' ')}...", flush=True)
    return text


def main():
    print("=== 1. ws_alpha 入库文档 A ===", flush=True)
    print(req("POST", "/documents/text", workspace="ws_alpha", body={"text": DOC_A, "file_source": "alpha-protocol-spec.md"}), flush=True)
    print("=== 2. ws_beta 入库文档 B ===", flush=True)
    print(req("POST", "/documents/text", workspace="ws_beta", body={"text": DOC_B, "file_source": "beta-auth-spec.md"}), flush=True)

    print("=== 3. 等待处理完成 ===", flush=True)
    wait_pipeline("ws_alpha", "alpha")
    wait_pipeline("ws_beta", "beta")

    print("=== 4. 交叉查询验证 ===", flush=True)
    results = {}
    results["alpha问A(应知)"] = query("ws_alpha", Q_A, "alpha问A")
    results["alpha问B(应不知)"] = query("ws_alpha", Q_B, "alpha问B")
    results["beta问B(应知)"] = query("ws_beta", Q_B, "beta问B")
    results["beta问A(应不知)"] = query("ws_beta", Q_A, "beta问A")
    results["默认问A(应不知)"] = query(None, Q_A, "默认问A")
    results["默认问B(应不知)"] = query(None, Q_B, "默认问B")

    with open("verify_ws_result.txt", "w", encoding="utf-8") as f:
        for k, v in results.items():
            f.write(f"### {k}\n{v}\n\n")

    # 判定
    def knows(text, keyword):
        return keyword in text

    def ignorant(text):
        markers = ["不知道", "没有相关信息", "未提及", "无相关", "不清楚", "don't know", "no information", "not mentioned", "没有提到", "资料中未", "文档中未"]
        return any(m in text for m in markers) or not knows(text, "Foxconn") and not knows(text, "PKCE")

    a1 = knows(results["alpha问A(应知)"], "Foxconn-9000")
    a2 = not knows(results["alpha问B(应不知)"], "OAuth2") or ignorant(results["alpha问B(应不知)"])
    b1 = knows(results["beta问B(应知)"], "PKCE")
    b2 = not knows(results["beta问A(应不知)"], "Foxconn") or ignorant(results["beta问A(应不知)"])
    d1 = not knows(results["默认问A(应不知)"], "Foxconn")
    d2 = not knows(results["默认问B(应不知)"], "PKCE")

    print("\n=== 判定 ===", flush=True)
    print(f"alpha 知 A(Foxconn-9000): {'PASS' if a1 else 'FAIL'}", flush=True)
    print(f"alpha 不知 B(OAuth2): {'PASS' if a2 else 'FAIL'}", flush=True)
    print(f"beta 知 B(PKCE): {'PASS' if b1 else 'FAIL'}", flush=True)
    print(f"beta 不知 A(Foxconn): {'PASS' if b2 else 'FAIL'}", flush=True)
    print(f"默认库不知 A: {'PASS' if d1 else 'FAIL'}", flush=True)
    print(f"默认库不知 B: {'PASS' if d2 else 'FAIL'}", flush=True)
    overall = all([a1, a2, b1, b2, d1, d2])
    print(f"\nOVERALL: {'ALL PASS' if overall else 'SOME FAIL'}", flush=True)


main()
